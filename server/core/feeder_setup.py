"""
IEEE 13-Bus Test Feeder Construction using pandapower.

This module builds the IEEE 13-bus test feeder -- a standard benchmark network
used extensively in power systems research. It serves as the "MNIST of power
systems" -- a well-understood, community-validated topology for testing
distribution-level algorithms.

The feeder includes:
- 13 buses at 115 kV (HV), 4.16 kV (MV), and 0.48 kV (LV) levels
- Distribution lines with realistic impedance values and tight thermal ratings
- A substation transformer connecting to the external grid
- Thermal ratings on all lines (for congestion/overload detection)
- Voltage limits of +/-5% on all buses (standard North American practice)

Custom transformer and line parameters are used (via create_*_from_parameters)
to match the original IEEE 13-bus voltage levels (4.16 kV) rather than
pandapower's European standard types (20 kV). This ensures residential loads
(1-10 kW) create meaningful line utilization for GNN training.

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
    # Voltage levels: 115 kV (HV), 4.16 kV (MV distribution), 0.48 kV (LV)
    # These match the original IEEE 13-bus spec.
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
            max_vm_pu=1.05,  # +/-5% voltage limits
            min_vm_pu=0.95,
        )
        bus_ids.append(bus_id)

    # =========================================================================
    # EXTERNAL GRID (Slack bus -- represents the utility connection)
    # =========================================================================
    pp.create_ext_grid(
        net,
        bus=bus_ids[0],
        vm_pu=1.0,
        name="Utility Grid Connection",
    )

    # =========================================================================
    # TRANSFORMER (Substation HV -> MV)
    # =========================================================================
    # Custom parameters for 115 kV / 4.16 kV step-down.
    # Using create_transformer_from_parameters to support the original IEEE
    # 13-bus voltage levels, which don't have pandapower std_types.
    pp.create_transformer_from_parameters(
        net,
        hv_bus=bus_ids[0],
        lv_bus=bus_ids[1],
        sn_mva=5.0,        # 5 MVA rating (appropriate for ~13 residential loads)
        vn_hv_kv=115.0,
        vn_lv_kv=4.16,
        vkr_percent=1.0,    # Resistive component of short-circuit voltage
        vk_percent=3.0,     # Total short-circuit voltage
        pfe_kw=11.0,        # Iron losses
        i0_percent=0.3,     # No-load current
        name="Substation Transformer",
    )

    # =========================================================================
    # DISTRIBUTION LINES
    # =========================================================================
    # Using create_line_from_parameters for full control over impedance and
    # thermal ratings at the 4.16 kV level.
    #
    # Line thermal ratings (max_i_ka) are sized so that default IEEE loads
    # produce ~40-70% line utilization, leaving headroom for normal operation
    # but making it possible for large P2P trades to push lines over 100%.
    #
    # At 4.16 kV: total downstream load ~3.5 MW -> ~485 A on trunk lines.
    # Trunk lines rated at 0.500 kA (500A) -> default ~70% loaded.
    # Branch lines rated at 0.150-0.200 kA -> default ~40-80% loaded.

    line_specs = [
        # (from_bus, to_bus, length_km, r_ohm_per_km, x_ohm_per_km, max_i_ka, c_nf_per_km, name)
        # r=0.089, x=0.076 typical for 4.16 kV distribution cables (300 mm2 AL)
        (1, 2,  0.610, 0.089, 0.076, 0.700, 13.0, "Line_650-632"),   # Main trunk (feeds all)
        (2, 3,  0.152, 0.089, 0.076, 0.200, 13.0, "Line_632-633"),   # Branch to 633/634
        # Line_633-634 is modeled as a transformer, not a line
        (2, 5,  0.152, 0.089, 0.076, 0.200, 13.0, "Line_632-645"),   # Branch to 645/646
        (5, 6,  0.091, 0.089, 0.076, 0.150, 13.0, "Line_645-646"),   # Leaf branch
        (2, 7,  0.610, 0.089, 0.076, 0.550, 13.0, "Line_632-671"),   # Major trunk
        (7, 8,  0.001, 0.089, 0.076, 0.300, 13.0, "Line_671-692"),   # Switch
        (8, 9,  0.152, 0.089, 0.076, 0.250, 13.0, "Line_692-675"),   # Branch to 675
        (7, 10, 0.091, 0.089, 0.076, 0.120, 13.0, "Line_671-611"),   # Leaf branch
        (7, 11, 0.244, 0.089, 0.076, 0.120, 13.0, "Line_671-652"),   # Leaf branch
        (7, 12, 0.305, 0.089, 0.076, 0.120, 13.0, "Line_671-680"),   # Leaf branch
    ]

    for from_b, to_b, length, r, x, max_i, c_nf, name in line_specs:
        pp.create_line_from_parameters(
            net,
            from_bus=bus_ids[from_b],
            to_bus=bus_ids[to_b],
            length_km=length,
            r_ohm_per_km=r,
            x_ohm_per_km=x,
            c_nf_per_km=c_nf,
            max_i_ka=max_i,
            name=name,
        )

    # =========================================================================
    # Transformer between Bus 633 and Bus 634 (step-down to LV)
    # =========================================================================
    pp.create_transformer_from_parameters(
        net,
        hv_bus=bus_ids[3],
        lv_bus=bus_ids[4],
        sn_mva=0.5,        # 500 kVA
        vn_hv_kv=4.16,
        vn_lv_kv=0.48,
        vkr_percent=1.2,
        vk_percent=3.0,
        pfe_kw=1.5,
        i0_percent=0.4,
        name="Transformer_633-634",
    )

    # =========================================================================
    # DEFAULT LOADS (will be overridden by real household profiles)
    # =========================================================================
    # Based on the IEEE 13-bus standard load values. Each load bus represents
    # a cluster of households. The attach_profiles module replaces these with
    # real time-varying household load/solar data during simulation.
    #
    # At 4.16 kV these loads create meaningful line utilization (~15-60%),
    # leaving headroom for P2P trades but making violations achievable.

    default_loads = [
        # (bus_idx, p_mw, q_mvar, name)
        (2,  0.200, 0.116, "Load_632"),
        (4,  0.200, 0.145, "Load_634"),
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
        Dict mapping bus_id -> {name, vn_kv, max_vm_pu, min_vm_pu}
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
