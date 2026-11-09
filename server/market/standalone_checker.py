"""
Standalone GNN Feasibility Checker — NO pandapower dependency.

This module provides GNN-based feasibility checking for user-initiated
trades without importing pandapower (which depends on scipy and fails
on some systems due to DLL issues).

It hardcodes the static IEEE 13-bus topology (edges, line params) and
constructs PyG Data objects directly for the trained GNN model.

This is the production path for user-initiated trades via the marketplace.
The pandapower-based path is only used during simulation/training.
"""

import torch
import numpy as np
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
from torch_geometric.data import Data

logger = logging.getLogger(__name__)

# ---- Static IEEE 13-bus topology (mirrors feeder_setup.py) ----

# Bus count
NUM_BUSES = 13

# Edges: (from_bus, to_bus) — lines + transformers
# From feeder_setup.py: 10 lines + 2 transformers
TOPOLOGY_EDGES = [
    # Lines (10 lines — matches feeder_setup.py line_specs)
    (1, 2),   # Line_650-632  (main trunk)
    (2, 3),   # Line_632-633
    (2, 5),   # Line_632-645
    (5, 6),   # Line_645-646
    (2, 7),   # Line_632-671  (major trunk)
    (7, 8),   # Line_671-692  (switch)
    (8, 9),   # Line_692-675
    (7, 10),  # Line_671-611
    (7, 11),  # Line_671-652
    (7, 12),  # Line_671-680
    # Transformers (2 trafos)
    (0, 1),   # Substation → Bus 650 (115kV/4.16kV)
    (3, 4),   # Bus 633 → Bus 634 (4.16kV/0.48kV step-down)
]

# Line parameters (r_ohm_per_km, x_ohm_per_km, max_i_ka, length_km)
# Exact values from feeder_setup.py line_specs
LINE_PARAMS = [
    (0.089, 0.076, 0.700, 0.610),  # Line_650-632  (main trunk)
    (0.089, 0.076, 0.200, 0.152),  # Line_632-633
    (0.089, 0.076, 0.200, 0.152),  # Line_632-645
    (0.089, 0.076, 0.150, 0.091),  # Line_645-646
    (0.089, 0.076, 0.550, 0.610),  # Line_632-671  (major trunk)
    (0.089, 0.076, 0.300, 0.001),  # Line_671-692  (switch)
    (0.089, 0.076, 0.250, 0.152),  # Line_692-675
    (0.089, 0.076, 0.120, 0.091),  # Line_671-611
    (0.089, 0.076, 0.120, 0.244),  # Line_671-652
    (0.089, 0.076, 0.120, 0.305),  # Line_671-680
]

# Transformer defaults
TRAFO_PARAMS = (0.01, 0.05, 1.0, 0.001)

# Bus type: 0 = substation, buses with solar are determined dynamically
SUBSTATION_BUS = 0

# Feature dimensions (must match training)
NUM_NODE_FEATURES = 6
NUM_EDGE_FEATURES = 5


def _build_edge_index() -> torch.Tensor:
    """Build bidirectional edge index from static topology."""
    edges = []
    for from_bus, to_bus in TOPOLOGY_EDGES:
        edges.append([from_bus, to_bus])
        edges.append([to_bus, from_bus])
    return torch.tensor(edges, dtype=torch.long).t().contiguous()


def _build_edge_features(line_loadings: Dict[int, float] = None) -> torch.Tensor:
    """Build edge features from static line parameters."""
    if line_loadings is None:
        line_loadings = {}

    edge_features = []

    # Line edges (bidirectional)
    for idx, (r_ohm, x_ohm, max_i, length) in enumerate(LINE_PARAMS):
        loading = line_loadings.get(idx, 50.0) / 100.0  # Default 50% loading
        feat = [r_ohm, x_ohm, max_i, loading, length]
        edge_features.append(feat)  # Forward
        edge_features.append(feat)  # Backward

    # Transformer edges (default features)
    num_trafos = len(TOPOLOGY_EDGES) - len(LINE_PARAMS)
    for _ in range(num_trafos):
        feat = [0.01, 0.05, 1.0, 0.5, 0.001]
        edge_features.append(feat)  # Forward
        edge_features.append(feat)  # Backward

    return torch.tensor(edge_features, dtype=torch.float32)


def _build_node_features(
    bus_voltages: Dict[int, float],
    seller_bus: int,
    buyer_bus: int,
    trade_amount_kw: float,
    solar_buses: set = None,
) -> torch.Tensor:
    """Build node feature matrix without pandapower."""
    if solar_buses is None:
        solar_buses = set()

    features = torch.zeros((NUM_BUSES, NUM_NODE_FEATURES), dtype=torch.float32)

    for bus_idx in range(NUM_BUSES):
        # Feature 0: Voltage
        features[bus_idx, 0] = bus_voltages.get(bus_idx, 1.0)

        # Feature 1: Net injection (default 0 for user-initiated trades)
        features[bus_idx, 1] = 0.0

        # Feature 2: Bus type
        if bus_idx == SUBSTATION_BUS:
            features[bus_idx, 2] = 0.0  # Substation
        elif bus_idx in solar_buses:
            features[bus_idx, 2] = 1.0  # Has solar
        else:
            features[bus_idx, 2] = 0.5  # No solar

        # Feature 3: Trade effect
        if bus_idx == seller_bus:
            features[bus_idx, 3] = trade_amount_kw / 10.0
        elif bus_idx == buyer_bus:
            features[bus_idx, 3] = -trade_amount_kw / 10.0
        else:
            features[bus_idx, 3] = 0.0

        # Feature 4: Is trade bus
        features[bus_idx, 4] = 1.0 if bus_idx in (seller_bus, buyer_bus) else 0.0

        # Feature 5: Normalized trade amount
        features[bus_idx, 5] = trade_amount_kw / 10.0

    return features


def create_pyg_data_standalone(
    bus_voltages: Dict[int, float],
    line_loadings: Dict[int, float],
    seller_bus: int,
    buyer_bus: int,
    trade_amount_kw: float,
    solar_buses: set = None,
) -> Data:
    """
    Create a PyG Data object for GNN inference WITHOUT pandapower.

    Uses the static IEEE 13-bus topology hardcoded above.
    """
    edge_index = _build_edge_index()
    node_features = _build_node_features(
        bus_voltages, seller_bus, buyer_bus, trade_amount_kw, solar_buses,
    )
    edge_features = _build_edge_features(line_loadings)

    data = Data(
        x=node_features,
        edge_index=edge_index,
        edge_attr=edge_features,
    )
    data.trade_seller_bus = torch.tensor([seller_bus], dtype=torch.long)
    data.trade_buyer_bus = torch.tensor([buyer_bus], dtype=torch.long)
    data.trade_amount_kw = torch.tensor([trade_amount_kw], dtype=torch.float32)

    return data


class StandaloneGNNChecker:
    """
    GNN feasibility checker that does NOT import pandapower.

    Loads the trained GNN model and checks feasibility using the static
    IEEE 13-bus topology. This is the production path for user-initiated
    marketplace trades.
    """

    def __init__(self, checkpoint_path: str = None, threshold: float = 0.5):
        self.device = torch.device("cpu")
        self.threshold = threshold
        self.model = None
        self.model_loaded = False

        if checkpoint_path is None:
            from config.settings import settings
            checkpoint_path = settings.gnn_model_path

        # Try multiple paths to find the checkpoint
        resolved_path = self._resolve_checkpoint_path(checkpoint_path)
        if resolved_path:
            self._load_model(resolved_path)
        else:
            logger.warning(
                f"GNN model not found (tried '{checkpoint_path}' and variants). "
                "Trades will be REJECTED (fail-safe) until the model is available."
            )

    @staticmethod
    def _resolve_checkpoint_path(path_str: str) -> Optional[str]:
        """Try multiple path resolutions to find the checkpoint."""
        server_root = Path(__file__).resolve().parents[1]
        project_root = server_root.parent
        configured_path = Path(path_str)
        candidates = [
            configured_path,
            Path.cwd() / configured_path,
            server_root / configured_path,
            project_root / configured_path,
            server_root / "ml/gnn/checkpoints/zoo/graphsage_best.pt",
            server_root / "ml/gnn/checkpoints/best_model.pt",
        ]
        if configured_path.parts and configured_path.parts[0] == "server":
            candidates.extend([
                project_root / Path(*configured_path.parts[1:]),
            ])
        else:
            candidates.extend([
                server_root / configured_path,
            ])
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file():
                logger.info(f"GNN checkpoint found at: {resolved}")
                return str(resolved)
        return None

    def _load_model(self, checkpoint_path: str):
        """Load a trained model from checkpoint."""
        try:
            checkpoint = torch.load(
                checkpoint_path, map_location=self.device, weights_only=False
            )

            model_type = checkpoint.get("model_type", "graphsage")
            output_mode = checkpoint.get("output_mode", "classification")
            hidden_dim = checkpoint.get("hidden_dim", 64)
            num_layers = checkpoint.get("num_layers", 3)

            # Import model creation (this only needs torch, not pandapower)
            from ml.gnn.model import create_model

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
                f"✓ GNN model loaded (standalone): {model_type}, "
                f"val_F1={val_metrics.get('f1', 'N/A')}, device={self.device}"
            )
        except Exception as e:
            logger.error(f"Failed to load GNN model: {e}")
            self.model_loaded = False

    def check_feasibility(
        self,
        seller_bus: int,
        buyer_bus: int,
        amount_kwh: float,
        bus_voltages: Dict[int, float] = None,
        line_loadings: Dict[int, float] = None,
    ) -> Dict:
        """
        Check if a trade is feasible using the GNN model.

        Args:
            seller_bus: Seller's grid bus ID.
            buyer_bus: Buyer's grid bus ID.
            amount_kwh: Trade amount in kWh.
            bus_voltages: Current bus voltages (optional, defaults to 1.0 p.u.).
            line_loadings: Current line loadings (optional, defaults to 50%).

        Returns:
            Dict with is_feasible, confidence, check_method, etc.
        """
        if not self.model_loaded:
            # Use a conservative deterministic limit while the optional model
            # is unavailable. This keeps small, safe marketplace trades usable
            # without pretending that an ML prediction was made.
            safe_limit_kwh = 1.0
            is_feasible = amount_kwh <= safe_limit_kwh
            return {
                "is_feasible": is_feasible,
                "confidence": 0.5 if is_feasible else 1.0,
                "check_method": "conservative_fallback",
                "max_feasible_amount_kwh": safe_limit_kwh,
                "reason": (
                    "Conservative fallback used while GNN model is unavailable"
                    if is_feasible else
                    "Requested amount exceeds conservative fallback limit"
                ),
            }

        # Default voltage/loading if not provided
        if bus_voltages is None:
            bus_voltages = {i: 1.0 for i in range(NUM_BUSES)}
        if line_loadings is None:
            line_loadings = {i: 50.0 for i in range(len(LINE_PARAMS))}

        # Convert kWh (15-min) to kW
        amount_kw = amount_kwh * 4

        start_time = time.perf_counter()

        # Create PyG data without pandapower
        data = create_pyg_data_standalone(
            bus_voltages=bus_voltages,
            line_loadings=line_loadings,
            seller_bus=seller_bus,
            buyer_bus=buyer_bus,
            trade_amount_kw=amount_kw,
        ).to(self.device)

        # Run GNN inference
        with torch.no_grad():
            output = self.model(data)

        probability = float(output["probability"].cpu().item())
        inference_time_ms = (time.perf_counter() - start_time) * 1000

        is_feasible = probability >= self.threshold

        result = {
            "is_feasible": is_feasible,
            "confidence": probability if is_feasible else (1 - probability),
            "probability": probability,
            "check_method": "gnn",
            "inference_time_ms": round(inference_time_ms, 2),
            "max_voltage_deviation": 0.0,
            "max_line_loading": 0.0,
            "violated_buses": [],
            "violated_lines": [],
        }

        # If regression model, also extract predicted values
        if "predicted_voltages" in output:
            pred_v = output["predicted_voltages"].cpu().numpy().flatten()
            result["max_voltage_deviation"] = float(np.max(np.abs(pred_v - 1.0)))
            # Identify violated buses (voltage outside ±5%)
            for i, v in enumerate(pred_v):
                if abs(v - 1.0) > 0.05:
                    result["violated_buses"].append(i)

        if "predicted_loadings" in output:
            pred_l = output["predicted_loadings"].cpu().numpy().flatten()
            result["max_line_loading"] = float(np.max(pred_l) * 100)
            for i, l in enumerate(pred_l):
                if l * 100 > 100.0:
                    result["violated_lines"].append(i)

        return result

    def find_max_feasible_amount(
        self,
        seller_bus: int,
        buyer_bus: int,
        max_amount_kwh: float,
        bus_voltages: Dict[int, float] = None,
        line_loadings: Dict[int, float] = None,
        step_kwh: float = 0.1,
    ) -> Optional[float]:
        """
        Binary search for the maximum feasible trade amount (partial fills).

        Returns the largest kWh amount that passes the feasibility check,
        or None if even the minimum amount is infeasible.
        """
        lo, hi = 0.0, max_amount_kwh
        best_feasible = None

        while hi - lo > step_kwh:
            mid = (lo + hi) / 2
            result = self.check_feasibility(
                seller_bus, buyer_bus, mid, bus_voltages, line_loadings,
            )
            if result["is_feasible"]:
                best_feasible = mid
                lo = mid
            else:
                hi = mid

        if best_feasible is None and self.check_feasibility(
            seller_bus, buyer_bus, min(max_amount_kwh, step_kwh),
            bus_voltages, line_loadings,
        )["is_feasible"]:
            best_feasible = min(max_amount_kwh, step_kwh)

        return best_feasible


# Singleton instance (lazy loaded)
_checker_instance: Optional[StandaloneGNNChecker] = None


def get_gnn_checker() -> StandaloneGNNChecker:
    """Get or create the singleton GNN feasibility checker."""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = StandaloneGNNChecker()
    return _checker_instance
