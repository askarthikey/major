"""
Simulation loop — orchestrates full trading day simulation.

For each timestep (15-min intervals over 24 hours):
1. Load/update household profiles (or use forecasted values)
2. Run power flow to get baseline grid state
3. Households submit bids/asks based on their surplus/demand
4. Auction engine matches trades
5. Feasibility gate checks each matched trade
6. Execute/reject/partial-fill → log to MongoDB ledger
7. Push real-time updates via WebSocket

This is the main entry point for running the P2P trading simulation.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Awaitable
import uuid

import pandapower as pp

from core.feeder_setup import create_ieee13_feeder, get_topology_for_visualization
from core.attach_profiles import (
    generate_synthetic_profiles,
    load_real_profiles,
    attach_profiles_to_network,
    DEFAULT_HOUSEHOLD_BUS_MAP,
)
from core.run_powerflow import solve_power_flow, get_grid_state_snapshot
from market.auction_engine import (
    DoubleAuctionEngine,
    generate_orders_from_household_states,
)
from market.feasibility_gate import FeasibilityGate
from ml.gnn.inference import GNNInferenceEngine
from ledger.models import TradeRecord, SimulationState, TradeStatus
from ledger.hash_chain import append_trade
from ledger.database import mongodb
from config.settings import settings

logger = logging.getLogger(__name__)


class SimulationLoop:
    """
    Orchestrates the full P2P energy trading simulation.

    Manages the lifecycle of a simulation session: initialization,
    step-by-step execution, and cleanup.
    """

    def __init__(
        self,
        total_timesteps: int = 96,  # 24 hours at 15-min intervals
        speed_multiplier: float = 1.0,
        ws_broadcast: Optional[Callable[[Dict], Awaitable[None]]] = None,
    ):
        """
        Args:
            total_timesteps: Number of simulation timesteps.
            speed_multiplier: How fast to run (1.0 = real-time, 10.0 = 10x speed).
            ws_broadcast: Async function to broadcast updates via WebSocket.
        """
        self.total_timesteps = total_timesteps
        self.speed_multiplier = speed_multiplier
        self.ws_broadcast = ws_broadcast

        # Initialize components
        self.net = create_ieee13_feeder()

        # Prefer real Pecan Street profiles over synthetic
        real_profiles = load_real_profiles()
        if real_profiles is not None:
            self.profiles = real_profiles
            self.data_source = "pecan_street_real"
            logger.info("Using real Pecan Street household profiles")
        else:
            self.profiles = generate_synthetic_profiles(num_timesteps=total_timesteps)
            self.data_source = "synthetic"
            logger.info("Using synthetic household profiles (real data not found)")

        self.auction = DoubleAuctionEngine()
        self.gnn_engine = GNNInferenceEngine(checkpoint_path=settings.gnn_model_path)
        self.gate = FeasibilityGate(gnn_engine=self.gnn_engine)

        # State
        self.session_id = str(uuid.uuid4())[:8]
        self.current_timestep = 0
        self.is_running = False
        self.household_states: Dict[str, Dict] = {}

        # Aggregate stats
        self.state = SimulationState(
            session_id=self.session_id,
            total_timesteps=total_timesteps,
            speed_multiplier=speed_multiplier,
        )

    async def run(self):
        """Run the full simulation from start to finish."""
        self.is_running = True
        self.state.is_running = True
        self.state.start_time = datetime.utcnow()

        logger.info(f"Starting simulation session {self.session_id}: {self.total_timesteps} timesteps")

        try:
            for t in range(self.total_timesteps):
                if not self.is_running:
                    logger.info("Simulation stopped by user")
                    break

                await self.step(t)

                # Wait between timesteps (adjusted by speed multiplier)
                delay = (15 * 60) / self.speed_multiplier  # 15 min in real-time seconds
                delay = min(delay, 2.0)  # Cap at 2 seconds for demo purposes
                await asyncio.sleep(delay)

        except Exception as e:
            logger.error(f"Simulation error: {e}")
            raise
        finally:
            self.is_running = False
            self.state.is_running = False
            logger.info(f"Simulation {self.session_id} complete")

    async def step(self, timestep_idx: Optional[int] = None) -> Dict:
        """
        Execute a single simulation timestep.

        This is also exposed as an API endpoint for step-by-step manual control.

        Returns:
            Dict with timestep results (trades, grid state, stats).
        """
        if timestep_idx is None:
            timestep_idx = self.current_timestep

        step_start = time.time()

        # --- 1. Update household profiles ---
        self.household_states = attach_profiles_to_network(
            self.net, self.profiles, timestep_idx,
        )

        # --- 2. Run baseline power flow ---
        baseline_pf = solve_power_flow(self.net)
        if not baseline_pf.converged:
            logger.warning(f"Timestep {timestep_idx}: baseline power flow did not converge")
            return {"error": "power flow did not converge", "timestep": timestep_idx}

        grid_state = get_grid_state_snapshot(self.net, baseline_pf)

        # --- 3. Generate orders ---
        orders = generate_orders_from_household_states(self.household_states)

        # --- 4. Run auction ---
        self.auction.clear_order_books()
        matched_trades = self.auction.submit_bulk_orders(orders)

        # --- 5. Feasibility gate ---
        executed_trades = []
        rejected_trades = []

        for trade in matched_trades:
            trade_record = self.gate.check_trade(
                trade=trade,
                net=self.net,
                bus_voltages=baseline_pf.bus_voltages,
                line_loadings=baseline_pf.line_loadings,
                household_states=self.household_states,
            )
            trade_record.simulation_timestep = timestep_idx

            # --- 6. Log to ledger ---
            trade_dict = trade_record.model_dump()
            trade_dict["timestamp"] = datetime.utcnow()

            # Convert nested models to dicts for MongoDB
            if trade_dict.get("feasibility"):
                trade_dict["feasibility"] = trade_record.feasibility.model_dump()

            try:
                await append_trade(trade_dict)
            except Exception as e:
                logger.error(f"Failed to append trade to ledger: {e}")

            if trade_record.status in (TradeStatus.EXECUTED, TradeStatus.PARTIAL_FILL):
                executed_trades.append(trade_record)
                self.state.total_trades_executed += 1
                self.state.total_energy_traded_kwh += trade_record.amount_kwh
                self.state.total_revenue += trade_record.total_price
                if trade_record.status == TradeStatus.PARTIAL_FILL:
                    self.state.total_trades_partial += 1
            else:
                rejected_trades.append(trade_record)
                self.state.total_trades_rejected += 1
                self.state.total_violations_prevented += 1

        # Update state
        self.current_timestep = timestep_idx + 1
        self.state.current_timestep = self.current_timestep
        self.state.last_update = datetime.utcnow()

        # Build result
        step_time_ms = (time.time() - step_start) * 1000
        hour = (timestep_idx * 15 / 60) % 24

        result = {
            "timestep": timestep_idx,
            "simulation_time": f"{int(hour):02d}:{int((hour % 1) * 60):02d}",
            "grid_state": grid_state,
            "orders_submitted": len(orders),
            "trades_matched": len(matched_trades),
            "trades_executed": len(executed_trades),
            "trades_rejected": len(rejected_trades),
            "trades": [t.model_dump() for t in executed_trades + rejected_trades],
            "household_states": self.household_states,
            "auction_summary": self.auction.get_order_book_summary(),
            "gate_stats": self.gate.get_stats(),
            "aggregate_stats": self.state.model_dump(),
            "step_time_ms": round(step_time_ms, 2),
        }

        # --- 7. Broadcast via WebSocket ---
        if self.ws_broadcast:
            try:
                await self.ws_broadcast({
                    "type": "simulation_step",
                    "data": {
                        "timestep": timestep_idx,
                        "simulation_time": result["simulation_time"],
                        "trades_executed": len(executed_trades),
                        "trades_rejected": len(rejected_trades),
                        "grid_healthy": grid_state.get("is_feasible", True),
                        "total_energy_kwh": self.state.total_energy_traded_kwh,
                        "violations_prevented": self.state.total_violations_prevented,
                        "trades": [
                            {
                                "trade_id": t.trade_id,
                                "seller": t.seller_household_id,
                                "buyer": t.buyer_household_id,
                                "amount_kwh": t.amount_kwh,
                                "price": t.price_per_kwh,
                                "status": t.status,
                            }
                            for t in executed_trades + rejected_trades
                        ],
                        "grid_state": grid_state,
                    },
                })
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")

        logger.info(
            f"Timestep {timestep_idx} ({result['simulation_time']}): "
            f"{len(orders)} orders -> {len(matched_trades)} matched -> "
            f"{len(executed_trades)} executed, {len(rejected_trades)} rejected "
            f"({step_time_ms:.0f}ms)"
        )

        return result

    def stop(self):
        """Stop the simulation loop."""
        self.is_running = False

    def get_state(self) -> Dict:
        """Get current simulation state."""
        return self.state.model_dump()


# Global simulation instance (singleton for the API)
_simulation: Optional[SimulationLoop] = None


def get_simulation() -> Optional[SimulationLoop]:
    """Get the current simulation instance."""
    return _simulation


def create_simulation(**kwargs) -> SimulationLoop:
    """Create a new simulation instance."""
    global _simulation
    _simulation = SimulationLoop(**kwargs)
    return _simulation
