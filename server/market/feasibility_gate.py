"""
GNN Feasibility Gate — the core innovation.

This module wraps the trained GNN (or pandapower fallback) and provides
the decision layer between the market engine's economic matching and
trade execution. Every matched trade must pass through this gate:

1. FEASIBLE → execute the trade as matched
2. INFEASIBLE → reject the trade (grid violation predicted)
3. PARTIAL FILL → reduce trade quantity until feasible (binary search)

The partial-fill option is a cheap, high-value novelty point:
instead of binary reject/accept, the gate finds the maximum safe
trade amount, recovering economic value while maintaining safety.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
import uuid

import pandapower as pp

from market.auction_engine import MatchedTrade
from ml.gnn.inference import GNNInferenceEngine
from ledger.models import TradeRecord, TradeStatus, FeasibilityResult
from config.settings import settings

logger = logging.getLogger(__name__)


class FeasibilityGate:
    """
    GNN-based feasibility gate for matched trades.

    Checks whether executing a matched trade would cause grid violations
    (voltage outside ±5%, line loading over thermal limit) and decides
    whether to execute, reject, or partially fill the trade.
    """

    def __init__(
        self,
        gnn_engine: Optional[GNNInferenceEngine] = None,
        enable_partial_fill: bool = True,
        partial_fill_min_kwh: float = 0.1,
    ):
        """
        Args:
            gnn_engine: Pre-initialized GNN inference engine.
            enable_partial_fill: If True, attempt partial fills for infeasible trades.
            partial_fill_min_kwh: Minimum kWh for a partial fill to be worth executing.
        """
        if gnn_engine is None:
            gnn_engine = GNNInferenceEngine(
                checkpoint_path=settings.gnn_model_path,
            )
        self.gnn = gnn_engine
        self.enable_partial_fill = enable_partial_fill
        self.partial_fill_min_kwh = partial_fill_min_kwh

        # Statistics
        self.stats = {
            "total_checked": 0,
            "total_feasible": 0,
            "total_infeasible": 0,
            "total_partial_fill": 0,
            "violations_prevented": 0,
        }

    def check_trade(
        self,
        trade: MatchedTrade,
        net: pp.pandapowerNet,
        bus_voltages: Dict[int, float],
        line_loadings: Dict[int, float],
        household_states: Dict[str, Dict],
    ) -> TradeRecord:
        """
        Check a matched trade for grid feasibility and return a TradeRecord.

        This is the main entry point called by the simulation loop for every
        trade matched by the auction engine.

        Args:
            trade: Matched trade from the auction engine.
            net: pandapower network.
            bus_voltages: Current bus voltages (p.u.).
            line_loadings: Current line loadings (%).
            household_states: Current household states.

        Returns:
            TradeRecord with status set to EXECUTED, REJECTED, or PARTIAL_FILL.
        """
        self.stats["total_checked"] += 1

        # Run feasibility check
        result = self.gnn.predict(
            net=net,
            bus_voltages=bus_voltages,
            line_loadings=line_loadings,
            household_states=household_states,
            seller_bus=trade.seller_bus,
            buyer_bus=trade.buyer_bus,
            amount_kw=trade.amount_kwh * 4,  # Convert kWh (15-min) to kW
        )

        feasibility = FeasibilityResult(
            is_feasible=result["is_feasible"],
            confidence=result.get("confidence", 1.0),
            max_voltage_deviation=result.get("max_voltage_deviation", 0.0),
            max_line_loading=result.get("max_line_loading", 0.0),
            violated_buses=result.get("voltage_violations", []),
            violated_lines=result.get("line_violations", []),
            check_method=result.get("check_method", "pandapower"),
        )

        if result["is_feasible"]:
            # FEASIBLE — execute the trade as matched
            self.stats["total_feasible"] += 1
            status = TradeStatus.EXECUTED
            final_amount = trade.amount_kwh
            logger.debug(f"Trade {trade.trade_id}: FEASIBLE (executing)")

        elif self.enable_partial_fill:
            # INFEASIBLE — try partial fill
            self.stats["violations_prevented"] += 1
            max_feasible = self._find_partial_fill(
                trade, net, bus_voltages, line_loadings, household_states,
            )

            if max_feasible and max_feasible >= self.partial_fill_min_kwh:
                self.stats["total_partial_fill"] += 1
                status = TradeStatus.PARTIAL_FILL
                final_amount = max_feasible
                feasibility.suggested_max_amount_kwh = max_feasible
                logger.info(
                    f"Trade {trade.trade_id}: PARTIAL FILL "
                    f"({trade.amount_kwh:.3f} → {max_feasible:.3f} kWh)"
                )
            else:
                self.stats["total_infeasible"] += 1
                status = TradeStatus.REJECTED
                final_amount = 0.0
                logger.info(f"Trade {trade.trade_id}: REJECTED (no viable partial fill)")
        else:
            # INFEASIBLE — hard reject (no partial fill)
            self.stats["total_infeasible"] += 1
            self.stats["violations_prevented"] += 1
            status = TradeStatus.REJECTED
            final_amount = 0.0
            logger.info(f"Trade {trade.trade_id}: REJECTED")

        # Create trade record
        trade_record = TradeRecord(
            trade_id=trade.trade_id,
            timestamp=datetime.utcnow(),
            buyer_bus=trade.buyer_bus,
            seller_bus=trade.seller_bus,
            buyer_household_id=trade.buyer_order.household_id,
            seller_household_id=trade.seller_order.household_id,
            amount_kwh=final_amount,
            price_per_kwh=trade.clearing_price,
            total_price=round(final_amount * trade.clearing_price, 4),
            original_amount_kwh=trade.amount_kwh if status == TradeStatus.PARTIAL_FILL else None,
            status=status,
            feasibility=feasibility,
        )

        return trade_record

    def _find_partial_fill(
        self,
        trade: MatchedTrade,
        net: pp.pandapowerNet,
        bus_voltages: Dict[int, float],
        line_loadings: Dict[int, float],
        household_states: Dict[str, Dict],
    ) -> Optional[float]:
        """
        Binary search for the maximum feasible trade amount.

        Returns the largest kWh amount that passes the feasibility check,
        or None if even the minimum amount is infeasible.
        """
        max_feasible = self.gnn.find_max_feasible_amount(
            net=net,
            bus_voltages=bus_voltages,
            line_loadings=line_loadings,
            household_states=household_states,
            seller_bus=trade.seller_bus,
            buyer_bus=trade.buyer_bus,
            max_amount_kw=trade.amount_kwh * 4,  # Convert kWh to kW
            step_kw=0.2,
        )

        if max_feasible is not None:
            return max_feasible / 4  # Convert kW back to kWh (15-min interval)
        return None

    def get_stats(self) -> Dict:
        """Get gate statistics."""
        total = max(1, self.stats["total_checked"])
        return {
            **self.stats,
            "feasibility_rate": round(self.stats["total_feasible"] / total, 4),
            "rejection_rate": round(self.stats["total_infeasible"] / total, 4),
            "partial_fill_rate": round(self.stats["total_partial_fill"] / total, 4),
        }

    def reset_stats(self):
        """Reset gate statistics."""
        self.stats = {k: 0 for k in self.stats}
