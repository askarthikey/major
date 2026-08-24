"""
Grid state routes — current grid topology and state endpoints.
"""

from fastapi import APIRouter
from typing import List

from core.feeder_setup import create_ieee13_feeder, get_topology_for_visualization
from core.run_powerflow import solve_power_flow, get_grid_state_snapshot
from core.attach_profiles import get_households_summary
from market.simulation_loop import get_simulation
from api.schemas import GridStateResponse, TopologyResponse, HouseholdResponse

router = APIRouter(prefix="/grid", tags=["Grid"])

# Cache the topology (it doesn't change during simulation)
_topology_cache = None


@router.get("/topology", response_model=TopologyResponse)
async def get_grid_topology():
    """
    Get the IEEE 13-bus feeder topology for D3.js visualization.

    Returns nodes (buses) and edges (lines) with their properties.
    This is static data — the topology doesn't change during simulation.
    """
    global _topology_cache
    if _topology_cache is None:
        net = create_ieee13_feeder()
        _topology_cache = get_topology_for_visualization(net)
    return _topology_cache


@router.get("/state")
async def get_current_grid_state():
    """
    Get the current grid state (voltages, line loadings, violations).

    If a simulation is running, returns the latest state.
    Otherwise, runs a fresh power flow on the default network.
    """
    sim = get_simulation()
    if sim and sim.current_timestep > 0:
        # Use the simulation's current network state
        pf_result = solve_power_flow(sim.net)
        return get_grid_state_snapshot(sim.net, pf_result)
    else:
        # No simulation running — solve with default loads
        net = create_ieee13_feeder()
        pf_result = solve_power_flow(net)
        return get_grid_state_snapshot(net, pf_result)


@router.get("/households", response_model=List[HouseholdResponse])
async def get_households():
    """Get all household profiles and their bus assignments."""
    return get_households_summary()


@router.get("/history")
async def get_grid_history(limit: int = 50):
    """Get historical grid snapshots from MongoDB."""
    from ledger.database import mongodb

    cursor = mongodb.grid_snapshots.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)

    snapshots = await cursor.to_list(length=limit)
    return snapshots
