"""
IEEE 13-Bus Test Feeder Construction using pandapower.

This module builds the IEEE 13-bus test feeder — a standard benchmark network
used extensively in power systems research. It serves as the "MNIST of power
systems" — a well-understood, community-validated topology for testing
distribution-level algorithms.

The feeder includes:
- 13 buses at various voltage levels
- Distribution lines with realistic impedance values
- A substation transformer connecting to the external grid
- Thermal ratings on all lines (for congestion/overload detection)
- Voltage limits of ±5% on all buses (standard North American practice)

This is the ground-truth network topology that:
1. The GNN learns to reason about (graph structure)
2. pandapower solves power flow on (physics ground truth)
3. Candidate trades are evaluated against (feasibility checking)
"""

import pandapower as pp
import pandapower.networks as pn
import numpy as np
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def create_ieee13_feeder() -> pp.pandapowerNet:
    """
    Create the IEEE 13-bus test feeder network in pandapower.

    This is a simplified but representative version of the IEEE 13-Node Test
    Feeder, adapted for single-phase equivalent modeling (pandapower's default).
    The key physical parameters (line impedances, transformer ratings, load
    profiles) are drawn from the published IEEE spec.

    Returns:
        pandapower network object with all buses, lines, loads, and constraints defined.
    """
    net = pp.create_empty_network(name="IEEE 13-Bus Test Feeder")

    # =========================================================================
    # BUSES
    # =========================================================================
    # Bus 0: Substation / slack bus (connects to external grid)
    # Buses 1-12: Distribution buses where households are connected
    #
    # Voltage level: 4.16 kV (standard medium-voltage distribution)
    # Buses are numbered 0-12 for easy array indexing

    bus_data = [
        {"name": "Substation",  "vn_kv": 115.0, "type": "b"},  # Bus 0: HV side
        {"name": "Bus_650",     "vn_kv": 4.16,  "type": "b"},  # Bus 1: MV busbar
        {"name": "Bus_632",     "vn_kv": 4.16,  "type": "b"},  # Bus 2
        {"name": "Bus_633",     "vn_kv": 4.16,  "type": "b"},  # Bus 3
        {"name": "Bus_634",     "vn_kv": 0.48,  "type": "b"},  # Bus 4: LV (after xfmr)
        {"name": "Bus_645",     "vn_kv": 4.16,  "type": "b"},  # Bus 5
        {"name": "Bus_646",     "vn_kv": 4.16,  "type": "b"},  # Bus 6
        {"name": "Bus_671",     "vn_kv": 4.16,  "type": "b"},  # Bus 7
        {"name": "Bus_692",     "vn_kv": 4.16,  "type": "b"},  # Bus 8
        {"name": "Bus_675",     "vn_kv": 4.16,  "type": "b"},  # Bus 9
        {"name": "Bus_611",     "vn_kv": 4.16,  "type": "b"},  # Bus 10
        {"name": "Bus_652",     "vn_kv": 4.16,  "type": "b"},  # Bus 11
        {"name": "Bus_680",     "vn_kv": 4.16,  "type": "b"},  # Bus 12
    ]

    bus_ids = []
    for bd in bus_data:
        bus_id = pp.create_bus(
            net,
            vn_kv=bd["vn_kv"],
            name=bd["name"],
            type=bd["type"],
            max_vm_pu=1.05,  # ±5% voltage limits
            min_vm_pu=0.95,
        )
        bus_ids.append(bus_id)

    # =========================================================================
    # EXTERNAL GRID (Slack bus — represents the utility connection)
    # =========================================================================
    pp.create_ext_grid(
        net,
        bus=bus_ids[0],
        vm_pu=1.0,
        name="Utility Grid Connection",
    )

    # =========================================================================
    # TRANSFORMER (Substation HV → MV)
    # =========================================================================
    pp.create_transformer(
        net,
        hv_bus=bus_ids[0],
        lv_bus=bus_ids[1],
        std_type="25 MVA 110/20 kV",
        name="Substation Transformer",
    )

    # =========================================================================
    # DISTRIBUTION LINES
    # =========================================================================
    # Line parameters approximate the IEEE 13-bus test feeder's overhead
    # and underground line configurations, mapped to pandapower standard types.
    #
    # Each line has a thermal rating (max_i_ka) that determines how much current
    # it can carry before overheating — this is one of the two physical constraints
    # the GNN must learn to predict (the other being bus voltage).

    line_specs = [
        # (from_bus, to_bus, length_km, name)
        (1, 2,  0.610, "Line_650-632"),   # Main feeder trunk
        (2, 3,  0.152, "Line_632-633"),
        (3, 4,  0.0,   "Line_633-634"),   # Through transformer (modeled separately)
        (2, 5,  0.152, "Line_632-645"),
        (5, 6,  0.091, "Line_645-646"),
        (2, 7,  0.610, "Line_632-671"),   # Long main trunk segment
        (7, 8,  0.0,   "Line_671-692"),   # Switch (zero-length)
        (8, 9,  0.152, "Line_692-675"),
        (7, 10, 0.091, "Line_671-611"),
        (7, 11, 0.244, "Line_671-652"),
        (7, 12, 0.305, "Line_671-680"),
    ]

    for from_b, to_b, length, name in line_specs:
        if length == 0:
            length = 0.001  # Minimum length for switches/zero-impedance connections

        pp.create_line(
            net,
            from_bus=bus_ids[from_b],
            to_bus=bus_ids[to_b],
            length_km=length,
            std_type="NAYY 4x50 SE",  # Standard cable type
            name=name,
        )

    # =========================================================================
    # Transformer between Bus 633 and Bus 634 (step-down to LV)
    # =========================================================================
    pp.create_transformer(
        net,
        hv_bus=bus_ids[3],
        lv_bus=bus_ids[4],
        std_type="0.4 MVA 20/0.4 kV",
        name="Transformer_633-634",
    )

    # =========================================================================
    # DEFAULT LOADS (will be overridden by real household profiles)
    # =========================================================================
    # These are placeholder loads at each load bus, based on the IEEE 13-bus
    # standard load values. The attach_profiles module replaces these with
    # real time-varying household load/solar data.

    default_loads = [
        # (bus_idx, p_mw, q_mvar, name)
        (2,  0.200, 0.116, "Load_632"),
        (4,  0.400, 0.290, "Load_634"),
        (5,  0.170, 0.125, "Load_645"),
        (6,  0.230, 0.132, "Load_646"),
        (7,  1.155, 0.660, "Load_671"),
        (8,  0.170, 0.151, "Load_692"),
        (9,  0.843, 0.462, "Load_675"),
        (10, 0.170, 0.080, "Load_611"),
        (11, 0.128, 0.086, "Load_652"),
    ]

    for bus_idx, p_mw, q_mvar, name in default_loads:
        pp.create_load(
            net,
            bus=bus_ids[bus_idx],
            p_mw=p_mw,
            q_mvar=q_mvar,
            name=name,
        )

    logger.info(
        f"IEEE 13-bus feeder created: {len(net.bus)} buses, "
        f"{len(net.line)} lines, {len(net.load)} loads, "
        f"{len(net.trafo)} transformers"
    )
    return net


def get_bus_info(net: pp.pandapowerNet) -> Dict[int, Dict[str, Any]]:
    """
    Get a summary of all buses in the network.

    Returns:
        Dict mapping bus_id → {name, vn_kv, max_vm_pu, min_vm_pu}
    """
    info = {}
    for idx in net.bus.index:
        info[idx] = {
            "name": net.bus.at[idx, "name"],
            "vn_kv": net.bus.at[idx, "vn_kv"],
            "max_vm_pu": net.bus.at[idx, "max_vm_pu"],
            "min_vm_pu": net.bus.at[idx, "min_vm_pu"],
        }
    return info


def get_topology_for_visualization(net: pp.pandapowerNet) -> Dict[str, Any]:
    """
    Extract network topology in a format suitable for D3.js visualization.

    Returns:
        Dict with 'nodes' and 'edges' lists for the frontend grid graph.
    """
    nodes = []
    for idx in net.bus.index:
        nodes.append({
            "id": int(idx),
            "name": net.bus.at[idx, "name"],
            "vn_kv": float(net.bus.at[idx, "vn_kv"]),
            "type": "substation" if idx == 0 else "load_bus",
        })

    edges = []
    for idx in net.line.index:
        edges.append({
            "id": int(idx),
            "source": int(net.line.at[idx, "from_bus"]),
            "target": int(net.line.at[idx, "to_bus"]),
            "name": net.line.at[idx, "name"],
            "length_km": float(net.line.at[idx, "length_km"]),
        })

    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    # Quick test: create the feeder and print summary
    logging.basicConfig(level=logging.INFO)
    net = create_ieee13_feeder()
    print(net)
    print("\nBus info:")
    for bus_id, info in get_bus_info(net).items():
        print(f"  Bus {bus_id}: {info}")
