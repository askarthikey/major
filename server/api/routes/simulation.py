"""
Simulation control routes — start, stop, step, status.
"""

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks

from market.simulation_loop import get_simulation, create_simulation, SimulationLoop
from api.schemas import (
    SimulationStartRequest,
    SimulationStepRequest,
    SimulationStateResponse,
    SimulationStepResponse,
)
from api.routes.websocket import broadcast_message

router = APIRouter(prefix="/simulation", tags=["Simulation"])


@router.post("/start")
async def start_simulation(
    request: SimulationStartRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a new simulation session.

    The simulation runs in the background, pushing updates via WebSocket.
    """
    sim = get_simulation()
    if sim and sim.is_running:
        raise HTTPException(status_code=409, detail="Simulation already running")

    sim = create_simulation(
        total_timesteps=request.total_timesteps,
        speed_multiplier=request.speed_multiplier,
        ws_broadcast=broadcast_message,
    )

    # Run simulation in background
    background_tasks.add_task(sim.run)

    return {
        "status": "started",
        "session_id": sim.session_id,
        "total_timesteps": request.total_timesteps,
        "speed_multiplier": request.speed_multiplier,
    }


@router.post("/stop")
async def stop_simulation():
    """Stop the running simulation."""
    sim = get_simulation()
    if not sim or not sim.is_running:
        raise HTTPException(status_code=404, detail="No simulation running")

    sim.stop()
    return {"status": "stopping", "session_id": sim.session_id}


@router.post("/step")
async def step_simulation(request: SimulationStepRequest = SimulationStepRequest()):
    """
    Execute a single simulation timestep.

    Used for manual step-by-step control (debugging, demos).
    """
    sim = get_simulation()
    if sim is None:
        # Create a new simulation for manual stepping
        sim = create_simulation(ws_broadcast=broadcast_message)

    if sim.is_running:
        raise HTTPException(
            status_code=409,
            detail="Cannot step while simulation is running continuously. Stop it first.",
        )

    timestep_idx = request.timestep_idx or sim.current_timestep
    result = await sim.step(timestep_idx)

    return result


@router.get("/status", response_model=SimulationStateResponse)
async def get_simulation_status():
    """Get current simulation state and aggregate stats."""
    sim = get_simulation()
    if sim is None:
        return SimulationStateResponse(
            session_id="none",
            is_running=False,
            current_timestep=0,
            total_timesteps=96,
            speed_multiplier=1.0,
            total_trades_executed=0,
            total_trades_rejected=0,
            total_trades_partial=0,
            total_energy_traded_kwh=0,
            total_violations_prevented=0,
            total_revenue=0,
        )

    return sim.get_state()


@router.post("/reset")
async def reset_simulation():
    """Reset the simulation to initial state."""
    sim = get_simulation()
    if sim and sim.is_running:
        sim.stop()
        await asyncio.sleep(0.5)  # Wait for graceful stop

    # Create fresh simulation
    create_simulation(ws_broadcast=broadcast_message)
    return {"status": "reset"}
