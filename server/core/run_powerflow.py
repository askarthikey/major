"""
Power flow solver wrapper around pandapower.

This is the ground-truth physics engine. pandapower solves the nonlinear
load-flow equations (based on Kirchhoff's laws and the power flow Jacobian)
to determine the actual voltage at every bus and current through every line
for a given set of loads and generators.

This module:
1. Runs the power flow solver with error handling
2. Extracts voltage and line loading results
3. Checks for constraint violations (voltage ±5%, line thermal limits)
4. Returns structured results used for:
   - GNN training label generation (ground truth)
   - Real-time grid state monitoring
   - Feasibility checking (when GNN is not yet trained)
"""

import warnings
warnings.filterwarnings("ignore", message="numba")

import pandapower as pp
import numpy as np
import logging
import time
from typing import Dict, Any, Tuple, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class PowerFlowResult:
    """Structured result from a power flow solution."""

    def __init__(
        self,
        converged: bool,
        bus_voltages: Dict[int, float],
        bus_voltages_kv: Dict[int, float],
        line_loadings: Dict[int, float],
        line_currents: Dict[int, float],
        voltage_violations: List[int],
        line_violations: List[int],
        solve_time_ms: float,
    ):
        self.converged = converged
        self.bus_voltages = bus_voltages           # bus_id → voltage in p.u.
        self.bus_voltages_kv = bus_voltages_kv     # bus_id → voltage in kV
        self.line_loadings = line_loadings         # line_id → loading %
        self.line_currents = line_currents         # line_id → current in kA
        self.voltage_violations = voltage_violations  # List of bus IDs with violations
        self.line_violations = line_violations        # List of line IDs with violations
        self.solve_time_ms = solve_time_ms

    @property
    def is_feasible(self) -> bool:
        """True if power flow converged and no violations exist."""
        return (
            self.converged
            and len(self.voltage_violations) == 0
            and len(self.line_violations) == 0
        )

    @property
    def max_voltage_deviation(self) -> float:
        """Maximum voltage deviation from 1.0 p.u. across all buses."""
        if not self.bus_voltages:
            return 0.0
        return max(abs(v - 1.0) for v in self.bus_voltages.values())

    @property
    def max_line_loading(self) -> float:
        """Maximum line loading percentage across all lines."""
        if not self.line_loadings:
            return 0.0
        return max(self.line_loadings.values())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "converged": self.converged,
            "is_feasible": self.is_feasible,
            "bus_voltages": self.bus_voltages,
            "bus_voltages_kv": self.bus_voltages_kv,
            "line_loadings": self.line_loadings,
            "line_currents": self.line_currents,
            "voltage_violations": self.voltage_violations,
            "line_violations": self.line_violations,
            "max_voltage_deviation": self.max_voltage_deviation,
            "max_line_loading": self.max_line_loading,
            "solve_time_ms": self.solve_time_ms,
        }


def solve_power_flow(
    net: pp.pandapowerNet,
    algorithm: str = "nr",  # Newton-Raphson (default, most robust)
    max_iteration: int = 50,
) -> PowerFlowResult:
    """
    Run pandapower power flow analysis on the network.

    This is the core physics solver — every result from this function is
    ground truth derived from the actual power flow equations. The GNN
    is trained to approximate this function's output, not to replace the
    physics, but to run faster than solving the full nonlinear system.

    Args:
        net: pandapower network with loads and generators set.
        algorithm: Solver algorithm ('nr' = Newton-Raphson, 'bfsw' = backward/forward sweep).
        max_iteration: Maximum solver iterations before declaring non-convergence.

    Returns:
        PowerFlowResult with voltages, loadings, violations, and timing.
    """
    start_time = time.perf_counter()

    try:
        pp.runpp(
            net,
            algorithm=algorithm,
            max_iteration=max_iteration,
            enforce_q_lims=False,
            calculate_voltage_angles=True,
        )
        converged = True
    except pp.LoadflowNotConverged:
        logger.warning("Power flow did not converge!")
        converged = False
    except Exception as e:
        logger.error(f"Power flow solver error: {e}")
        converged = False

    solve_time_ms = (time.perf_counter() - start_time) * 1000

    if not converged:
        return PowerFlowResult(
            converged=False,
            bus_voltages={},
            bus_voltages_kv={},
            line_loadings={},
            line_currents={},
            voltage_violations=[],
            line_violations=[],
            solve_time_ms=solve_time_ms,
        )

    # =========================================================================
    # Extract bus voltages
    # =========================================================================
    bus_voltages = {}
    bus_voltages_kv = {}
    voltage_violations = []

    for bus_idx in net.res_bus.index:
        vm_pu = float(net.res_bus.at[bus_idx, "vm_pu"])
        vn_kv = float(net.bus.at[bus_idx, "vn_kv"])
        bus_voltages[int(bus_idx)] = vm_pu
        bus_voltages_kv[int(bus_idx)] = vm_pu * vn_kv

        # Check voltage limits (±5%)
        if vm_pu > settings.voltage_tolerance_pu + 1.0 or vm_pu < 1.0 - settings.voltage_tolerance_pu:
            voltage_violations.append(int(bus_idx))

    # =========================================================================
    # Extract line loadings
    # =========================================================================
    line_loadings = {}
    line_currents = {}
    line_violations = []

    for line_idx in net.res_line.index:
        loading_pct = float(net.res_line.at[line_idx, "loading_percent"])
        current_ka = float(net.res_line.at[line_idx, "i_ka"])
        line_loadings[int(line_idx)] = loading_pct
        line_currents[int(line_idx)] = current_ka

        # Check thermal limit
        if loading_pct > settings.line_loading_limit_pct:
            line_violations.append(int(line_idx))

    result = PowerFlowResult(
        converged=converged,
        bus_voltages=bus_voltages,
        bus_voltages_kv=bus_voltages_kv,
        line_loadings=line_loadings,
        line_currents=line_currents,
        voltage_violations=voltage_violations,
        line_violations=line_violations,
        solve_time_ms=solve_time_ms,
    )

    logger.debug(
        f"Power flow solved in {solve_time_ms:.2f}ms — "
        f"feasible={result.is_feasible}, "
        f"max_v_dev={result.max_voltage_deviation:.4f}, "
        f"max_line_load={result.max_line_loading:.1f}%"
    )

    return result


def solve_with_trade_applied(
    net: pp.pandapowerNet,
    seller_bus: int,
    buyer_bus: int,
    amount_kw: float,
) -> Tuple[PowerFlowResult, PowerFlowResult]:
    """
    Solve power flow before and after applying a candidate trade.

    This is the key function for generating GNN training labels:
    1. Solve power flow with current loads (baseline)
    2. Apply the trade (reduce seller load, increase buyer supply)
    3. Solve again (with-trade)
    4. Return both results for comparison

    The trade's physical effect:
    - Seller: reduces net injection at seller's bus by amount_kw
      (seller is exporting less surplus, since it's being consumed locally)
    - Buyer: reduces net draw at buyer's bus by amount_kw
      (buyer is consuming locally-sourced power instead of from the grid)

    Args:
        net: pandapower network with current loads set.
        seller_bus: Bus ID of the seller.
        buyer_bus: Bus ID of the buyer.
        amount_kw: Trade amount in kW.

    Returns:
        Tuple of (baseline_result, with_trade_result)
    """
    # Step 1: Baseline power flow (current state, no trade)
    baseline_result = solve_power_flow(net)

    # Step 2: Apply trade effects to loads
    # Save original load values for restoration
    original_loads = net.load["p_mw"].copy()
    original_q = net.load["q_mvar"].copy()

    amount_mw = amount_kw / 1000.0

    # Find loads at seller and buyer buses
    for load_idx in net.load.index:
        load_bus = net.load.at[load_idx, "bus"]

        if load_bus == buyer_bus:
            # Buyer's load decreases (receiving local power instead of grid power)
            net.load.at[load_idx, "p_mw"] -= amount_mw
            net.load.at[load_idx, "q_mvar"] -= amount_mw * 0.484

        elif load_bus == seller_bus:
            # Seller's net injection increases (exporting surplus to buyer)
            # In pandapower, negative load = generation
            net.load.at[load_idx, "p_mw"] -= amount_mw
            net.load.at[load_idx, "q_mvar"] -= amount_mw * 0.484

    # Step 3: Solve with trade applied
    trade_result = solve_power_flow(net)

    # Step 4: Restore original loads (don't permanently modify the network)
    net.load["p_mw"] = original_loads
    net.load["q_mvar"] = original_q

    return baseline_result, trade_result


def get_grid_state_snapshot(
    net: pp.pandapowerNet,
    pf_result: Optional[PowerFlowResult] = None,
) -> Dict[str, Any]:
    """
    Build a complete grid state snapshot suitable for API responses.

    Args:
        net: pandapower network.
        pf_result: Pre-computed power flow result (runs solver if None).

    Returns:
        Dict with bus states, line states, and aggregate metrics.
    """
    if pf_result is None:
        pf_result = solve_power_flow(net)

    if not pf_result.converged:
        return {"error": "Power flow did not converge", "converged": False}

    buses = []
    for bus_idx in net.bus.index:
        vm_pu = pf_result.bus_voltages.get(int(bus_idx), 1.0)
        buses.append({
            "bus_id": int(bus_idx),
            "name": net.bus.at[bus_idx, "name"],
            "voltage_pu": vm_pu,
            "voltage_kv": pf_result.bus_voltages_kv.get(int(bus_idx), 0),
            "is_violation": int(bus_idx) in pf_result.voltage_violations,
        })

    lines = []
    for line_idx in net.line.index:
        lines.append({
            "line_id": int(line_idx),
            "from_bus": int(net.line.at[line_idx, "from_bus"]),
            "to_bus": int(net.line.at[line_idx, "to_bus"]),
            "name": net.line.at[line_idx, "name"],
            "loading_percent": pf_result.line_loadings.get(int(line_idx), 0),
            "current_ka": pf_result.line_currents.get(int(line_idx), 0),
            "is_violation": int(line_idx) in pf_result.line_violations,
        })

    return {
        "converged": True,
        "is_feasible": pf_result.is_feasible,
        "buses": buses,
        "lines": lines,
        "max_voltage_deviation": pf_result.max_voltage_deviation,
        "max_line_loading": pf_result.max_line_loading,
        "num_voltage_violations": len(pf_result.voltage_violations),
        "num_line_violations": len(pf_result.line_violations),
        "solve_time_ms": pf_result.solve_time_ms,
    }
