"""
GNN inference wrapper for production use.

Loads a trained model checkpoint and provides a fast, simple interface
for the feasibility gate to call:

    inference_engine = GNNInferenceEngine("checkpoints/best_model.pt")
    result = inference_engine.predict(net, grid_state, trade)

Falls back to pandapower direct solving when no trained model is available.
"""

import torch
import numpy as np
import pandapower as pp
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from ml.gnn.model import create_model
from ml.utils.graph_features import create_pyg_data, build_edge_index, NUM_NODE_FEATURES
from core.run_powerflow import solve_power_flow, solve_with_trade_applied

logger = logging.getLogger(__name__)


class GNNInferenceEngine:
    """
    Production inference wrapper for the GNN feasibility model.

    Handles model loading, device management, and provides a clean API
    for the market engine's feasibility gate.
    """

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        device: str = "auto",
        threshold: float = 0.5,
    ):
        """
        Args:
            checkpoint_path: Path to the trained model checkpoint.
            device: Device for inference ("auto", "cuda", or "cpu").
            threshold: Classification threshold for feasibility.
        """
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.threshold = threshold
        self.model = None
        self.model_loaded = False

        if checkpoint_path and Path(checkpoint_path).exists():
            self._load_model(checkpoint_path)
        else:
            logger.warning(
                f"GNN model checkpoint not found at '{checkpoint_path}'. "
                "Falling back to pandapower direct solving."
            )

    def _load_model(self, checkpoint_path: str):
        """Load a trained model from checkpoint."""
        try:
            checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)

            model_type = checkpoint.get("model_type", "graphsage")
            output_mode = checkpoint.get("output_mode", "classification")
            hidden_dim = checkpoint.get("hidden_dim", 64)
            num_layers = checkpoint.get("num_layers", 3)

            self.model = create_model(
                model_type=model_type,
                output_mode=output_mode,
                hidden_dim=hidden_dim,
                num_layers=num_layers,
            )
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model = self.model.to(self.device)
            self.model.eval()
            self.model_loaded = True

            val_metrics = checkpoint.get("val_metrics", {})
            logger.info(
                f"GNN model loaded: {model_type}, "
                f"val_F1={val_metrics.get('f1', 'N/A')}, "
                f"device={self.device}"
            )
        except Exception as e:
            logger.error(f"Failed to load GNN model: {e}")
            self.model_loaded = False

    def predict(
        self,
        net: pp.pandapowerNet,
        bus_voltages: Dict[int, float],
        line_loadings: Dict[int, float],
        household_states: Dict[str, Dict],
        seller_bus: int,
        buyer_bus: int,
        amount_kw: float,
    ) -> Dict:
        """
        Predict trade feasibility.

        If the GNN model is loaded, uses it for fast inference.
        Otherwise, falls back to pandapower direct power flow solving.

        Args:
            net: pandapower network.
            bus_voltages: Current bus voltages (p.u.).
            line_loadings: Current line loadings (%).
            household_states: Current household states.
            seller_bus: Seller's bus ID.
            buyer_bus: Buyer's bus ID.
            amount_kw: Trade amount in kW.

        Returns:
            Dict with:
            - is_feasible: bool
            - confidence: float [0, 1]
            - check_method: "gnn" or "pandapower"
            - inference_time_ms: float
            - max_voltage_deviation: float
            - max_line_loading: float
        """
        if self.model_loaded:
            return self._predict_gnn(
                net, bus_voltages, line_loadings, household_states,
                seller_bus, buyer_bus, amount_kw,
            )
        else:
            return self._predict_pandapower(
                net, seller_bus, buyer_bus, amount_kw,
            )

    def _predict_gnn(
        self,
        net: pp.pandapowerNet,
        bus_voltages: Dict[int, float],
        line_loadings: Dict[int, float],
        household_states: Dict[str, Dict],
        seller_bus: int,
        buyer_bus: int,
        amount_kw: float,
    ) -> Dict:
        """Use the trained GNN for fast inference."""
        start_time = time.perf_counter()

        # Create PyG data object
        data = create_pyg_data(
            net=net,
            bus_voltages=bus_voltages,
            line_loadings=line_loadings,
            household_states=household_states,
            trade_seller_bus=seller_bus,
            trade_buyer_bus=buyer_bus,
            trade_amount_kw=amount_kw,
        )
        data = data.to(self.device)

        # Run inference
        with torch.no_grad():
            output = self.model(data)

        probability = float(output["probability"].cpu().item())
        inference_time_ms = (time.perf_counter() - start_time) * 1000

        result = {
            "is_feasible": probability >= self.threshold,
            "confidence": probability if probability >= self.threshold else (1 - probability),
            "probability": probability,
            "check_method": "gnn",
            "inference_time_ms": inference_time_ms,
            "max_voltage_deviation": 0.0,  # Not available from classification model
            "max_line_loading": 0.0,
        }

        # If regression model, also extract predicted values
        if "predicted_voltages" in output:
            pred_v = output["predicted_voltages"].cpu().numpy().flatten()
            result["max_voltage_deviation"] = float(np.max(np.abs(pred_v - 1.0)))
        if "predicted_loadings" in output:
            pred_l = output["predicted_loadings"].cpu().numpy().flatten()
            result["max_line_loading"] = float(np.max(pred_l) * 100)

        return result

    def _predict_pandapower(
        self,
        net: pp.pandapowerNet,
        seller_bus: int,
        buyer_bus: int,
        amount_kw: float,
    ) -> Dict:
        """Fallback: use pandapower direct power flow solving."""
        start_time = time.perf_counter()

        baseline_result, trade_result = solve_with_trade_applied(
            net, seller_bus, buyer_bus, amount_kw,
        )

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return {
            "is_feasible": trade_result.is_feasible,
            "confidence": 1.0,  # Ground truth is always 100% confident
            "probability": 1.0 if trade_result.is_feasible else 0.0,
            "check_method": "pandapower",
            "inference_time_ms": inference_time_ms,
            "max_voltage_deviation": trade_result.max_voltage_deviation,
            "max_line_loading": trade_result.max_line_loading,
            "voltage_violations": trade_result.voltage_violations,
            "line_violations": trade_result.line_violations,
        }

    def find_max_feasible_amount(
        self,
        net: pp.pandapowerNet,
        bus_voltages: Dict[int, float],
        line_loadings: Dict[int, float],
        household_states: Dict[str, Dict],
        seller_bus: int,
        buyer_bus: int,
        max_amount_kw: float,
        step_kw: float = 0.5,
    ) -> Optional[float]:
        """
        Binary search for the maximum feasible trade amount (for partial fills).

        If a trade at max_amount_kw is infeasible, this finds the largest amount
        that IS feasible, enabling the market to partially fill the trade
        instead of rejecting it entirely.

        Returns:
            Maximum feasible amount in kW, or None if no amount is feasible.
        """
        lo, hi = 0.0, max_amount_kw
        best_feasible = None

        while hi - lo > step_kw:
            mid = (lo + hi) / 2
            result = self.predict(
                net, bus_voltages, line_loadings, household_states,
                seller_bus, buyer_bus, mid,
            )
            if result["is_feasible"]:
                best_feasible = mid
                lo = mid
            else:
                hi = mid

        return best_feasible
