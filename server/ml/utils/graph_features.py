"""
Graph feature engineering for the GNN feasibility model.

Converts pandapower network state into PyTorch Geometric Data objects,
which is the input format for the GNN. Each Data object represents
the grid graph for one candidate trade evaluation:

Node features (per bus):
- Voltage (pre-trade, in p.u.)
- Net power injection/draw (kW)
- Bus type encoding (has_solar / no_solar / substation)
- Trade effect at this node (0 if not involved, ± trade amount if buyer/seller)

Edge features (per line):
- Line impedance (r_ohm_per_km, x_ohm_per_km)
- Thermal rating (max_i_ka)
- Current loading % (pre-trade)
- Line length (km)

The graph structure mirrors the physical electrical topology — edges
represent actual power lines, and the GNN must learn how power flows
propagate through this structure to predict voltage/loading impacts.
"""

import torch
import numpy as np
import pandapower as pp
from torch_geometric.data import Data
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# Bus type encoding
BUS_TYPE_SUBSTATION = 0
BUS_TYPE_NO_SOLAR = 1
BUS_TYPE_HAS_SOLAR = 2

# Number of features per node and edge
NUM_NODE_FEATURES = 6
NUM_EDGE_FEATURES = 5


def build_edge_index(net: pp.pandapowerNet) -> torch.Tensor:
    """
    Build the edge index tensor from the pandapower network topology.

    Creates bidirectional edges (power flows in both directions through lines)
    and includes transformer connections.

    Returns:
        Edge index tensor of shape [2, num_edges * 2] (bidirectional)
    """
    edges = []

    # Lines (distribution cables)
    for idx in net.line.index:
        from_bus = int(net.line.at[idx, "from_bus"])
        to_bus = int(net.line.at[idx, "to_bus"])
        # Bidirectional
        edges.append([from_bus, to_bus])
        edges.append([to_bus, from_bus])

    # Transformers (also physical connections)
    for idx in net.trafo.index:
        hv_bus = int(net.trafo.at[idx, "hv_bus"])
        lv_bus = int(net.trafo.at[idx, "lv_bus"])
        edges.append([hv_bus, lv_bus])
        edges.append([lv_bus, hv_bus])

    if not edges:
        return torch.zeros((2, 0), dtype=torch.long)

    edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    return edge_index


def build_node_features(
    net: pp.pandapowerNet,
    bus_voltages: Dict[int, float],
    household_states: Dict[str, Dict],
    trade_seller_bus: int,
    trade_buyer_bus: int,
    trade_amount_kw: float,
    solar_buses: Optional[set] = None,
) -> torch.Tensor:
    """
    Build node feature matrix for the GNN.

    Features per node:
    [0] voltage_pu       — Current voltage in per-unit
    [1] net_injection_kw — Net power injection (positive = generation)
    [2] bus_type          — Encoded bus type (0=substation, 1=no_solar, 2=has_solar)
    [3] trade_effect      — Trade's effect at this bus (+amount for seller, -amount for buyer, 0 otherwise)
    [4] is_trade_bus      — Binary flag (1 if this bus is involved in the trade)
    [5] normalized_trade  — Trade amount normalized by local capacity

    Args:
        net: pandapower network.
        bus_voltages: Dict of bus_id → voltage in p.u.
        household_states: Dict of household_id → state dict.
        trade_seller_bus: Bus ID of the trade seller.
        trade_buyer_bus: Bus ID of the trade buyer.
        trade_amount_kw: Trade amount in kW.
        solar_buses: Set of bus IDs with solar panels.
    """
    num_buses = len(net.bus)
    features = torch.zeros((num_buses, NUM_NODE_FEATURES), dtype=torch.float32)

    # Determine solar buses from household states
    if solar_buses is None:
        solar_buses = set()
        for hh_id, state in household_states.items():
            if state.get("has_solar", False):
                solar_buses.add(state["bus_id"])

    # Aggregate net injection per bus from household states
    bus_net_injection = {}
    for hh_id, state in household_states.items():
        bus_id = state["bus_id"]
        net_kw = state.get("solar_kw", 0) - state.get("load_kw", 0)
        bus_net_injection[bus_id] = bus_net_injection.get(bus_id, 0) + net_kw

    for bus_idx in net.bus.index:
        idx = int(bus_idx)

        # Feature 0: Voltage
        features[idx, 0] = bus_voltages.get(idx, 1.0)

        # Feature 1: Net injection (kW) — normalized
        net_inj = bus_net_injection.get(idx, 0)
        features[idx, 1] = net_inj / 10.0  # Normalize by 10 kW

        # Feature 2: Bus type
        if idx == 0:
            features[idx, 2] = BUS_TYPE_SUBSTATION / 2.0  # Normalize to [0, 1]
        elif idx in solar_buses:
            features[idx, 2] = BUS_TYPE_HAS_SOLAR / 2.0
        else:
            features[idx, 2] = BUS_TYPE_NO_SOLAR / 2.0

        # Feature 3: Trade effect
        if idx == trade_seller_bus:
            features[idx, 3] = trade_amount_kw / 10.0  # Positive for seller
        elif idx == trade_buyer_bus:
            features[idx, 3] = -trade_amount_kw / 10.0  # Negative for buyer
        else:
            features[idx, 3] = 0.0

        # Feature 4: Is trade bus (binary)
        features[idx, 4] = 1.0 if idx in (trade_seller_bus, trade_buyer_bus) else 0.0

        # Feature 5: Normalized trade amount
        features[idx, 5] = trade_amount_kw / 10.0

    return features


def build_edge_features(
    net: pp.pandapowerNet,
    line_loadings: Dict[int, float],
) -> torch.Tensor:
    """
    Build edge feature matrix for the GNN.

    Features per edge:
    [0] impedance_r     — Resistance (ohm/km), normalized
    [1] impedance_x     — Reactance (ohm/km), normalized
    [2] thermal_rating  — Max current (kA), normalized
    [3] current_loading — Current loading percentage, normalized
    [4] length_km       — Line length, normalized

    Note: Edge features are duplicated for bidirectional edges and
    transformer edges get default impedance values.
    """
    edge_features = []

    # Line edges (bidirectional)
    for idx in net.line.index:
        r_ohm = float(net.line.at[idx, "r_ohm_per_km"]) if "r_ohm_per_km" in net.line.columns else 0.1
        x_ohm = float(net.line.at[idx, "x_ohm_per_km"]) if "x_ohm_per_km" in net.line.columns else 0.1
        max_i = float(net.line.at[idx, "max_i_ka"]) if "max_i_ka" in net.line.columns else 0.5
        length = float(net.line.at[idx, "length_km"])
        loading = line_loadings.get(int(idx), 0) / 100.0  # Normalize to [0, 1]

        feat = [r_ohm, x_ohm, max_i, loading, length]
        edge_features.append(feat)  # Forward
        edge_features.append(feat)  # Backward

    # Transformer edges (default features)
    for idx in net.trafo.index:
        feat = [0.01, 0.05, 1.0, 0.5, 0.001]  # Approximate transformer impedance
        edge_features.append(feat)  # Forward
        edge_features.append(feat)  # Backward

    if not edge_features:
        return torch.zeros((0, NUM_EDGE_FEATURES), dtype=torch.float32)

    return torch.tensor(edge_features, dtype=torch.float32)


def create_pyg_data(
    net: pp.pandapowerNet,
    bus_voltages: Dict[int, float],
    line_loadings: Dict[int, float],
    household_states: Dict[str, Dict],
    trade_seller_bus: int,
    trade_buyer_bus: int,
    trade_amount_kw: float,
    is_feasible: Optional[bool] = None,
    target_voltages: Optional[Dict[int, float]] = None,
    target_loadings: Optional[Dict[int, float]] = None,
) -> Data:
    """
    Create a PyTorch Geometric Data object for a single candidate trade evaluation.

    This is the main entry point for converting a grid state + candidate trade
    into the format the GNN expects.

    Args:
        net: pandapower network.
        bus_voltages: Pre-trade bus voltages in p.u.
        line_loadings: Pre-trade line loadings in %.
        household_states: Current household states.
        trade_seller_bus: Seller's bus ID.
        trade_buyer_bus: Buyer's bus ID.
        trade_amount_kw: Trade amount in kW.
        is_feasible: Ground-truth feasibility label (None for inference).
        target_voltages: Post-trade voltages for regression target.
        target_loadings: Post-trade line loadings for regression target.

    Returns:
        PyG Data object ready for GNN input.
    """
    edge_index = build_edge_index(net)
    node_features = build_node_features(
        net, bus_voltages, household_states,
        trade_seller_bus, trade_buyer_bus, trade_amount_kw,
    )
    edge_features = build_edge_features(net, line_loadings)

    data = Data(
        x=node_features,
        edge_index=edge_index,
        edge_attr=edge_features,
    )

    # Add trade metadata
    data.trade_seller_bus = torch.tensor([trade_seller_bus], dtype=torch.long)
    data.trade_buyer_bus = torch.tensor([trade_buyer_bus], dtype=torch.long)
    data.trade_amount_kw = torch.tensor([trade_amount_kw], dtype=torch.float32)

    # Add labels (for training)
    if is_feasible is not None:
        data.y = torch.tensor([float(is_feasible)], dtype=torch.float32)

    # Add regression targets (post-trade values)
    if target_voltages is not None:
        num_buses = len(net.bus)
        voltage_targets = torch.zeros(num_buses, dtype=torch.float32)
        for bus_id, v in target_voltages.items():
            if bus_id < num_buses:
                voltage_targets[bus_id] = v
        data.target_voltages = voltage_targets

    if target_loadings is not None:
        num_lines = len(net.line)
        loading_targets = torch.zeros(num_lines, dtype=torch.float32)
        for line_id, l in target_loadings.items():
            if line_id < num_lines:
                loading_targets[line_id] = l / 100.0  # Normalize
        data.target_loadings = loading_targets

    return data
