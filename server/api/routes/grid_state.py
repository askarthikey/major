"""
Grid state routes — current grid topology and state endpoints.

Imports of pandapower-dependent modules are lazy to allow the server
to start even if scipy/pandapower has DLL issues on this system.
"""

from fastapi import APIRouter, HTTPException
from typing import List

from api.schemas import GridStateResponse, TopologyResponse, HouseholdResponse

router = APIRouter(prefix="/grid", tags=["Grid"])


def _get_grid_modules():
    """Lazy import of pandapower-dependent modules."""
    try:
        from core.feeder_setup import create_ieee13_feeder, get_topology_for_visualization
        from core.run_powerflow import solve_power_flow, get_grid_state_snapshot
        from core.attach_profiles import get_households_summary
        from market.simulation_loop import get_simulation
        return {
            "create_feeder": create_ieee13_feeder,
            "get_topology": get_topology_for_visualization,
            "solve_pf": solve_power_flow,
            "get_snapshot": get_grid_state_snapshot,
            "get_households": get_households_summary,
            "get_simulation": get_simulation,
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Grid modules unavailable (pandapower/scipy issue): {e}"
        )


@router.get("/topology")
async def get_topology():
    """Get the static grid topology for visualization."""
    mods = _get_grid_modules()
    net = mods["create_feeder"]()
    topo = mods["get_topology"](net)
    return topo


@router.get("/state")
async def get_grid_state():
    """Get the current grid state (voltages, line loadings, violations)."""
    mods = _get_grid_modules()
    sim = mods["get_simulation"]()
    if sim and sim.last_grid_state:
        return sim.last_grid_state

    # No simulation running — compute a fresh snapshot
    net = mods["create_feeder"]()
    pf_result = mods["solve_pf"](net)
    if pf_result:
        return pf_result
    return {"buses": [], "lines": [], "converged": False}


@router.get("/households")
async def get_households():
    """Get the household-to-bus mapping summary."""
    mods = _get_grid_modules()
    return mods["get_households"]()
