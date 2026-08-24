"""
Pydantic request/response schemas for the API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# --- Request Schemas ---

class SimulationStartRequest(BaseModel):
    total_timesteps: int = Field(default=96, ge=1, le=960)
    speed_multiplier: float = Field(default=1.0, ge=0.1, le=100.0)


class SimulationStepRequest(BaseModel):
    timestep_idx: Optional[int] = None


# --- Response Schemas ---

class TradeResponse(BaseModel):
    trade_id: str
    timestamp: datetime
    buyer_bus: int
    seller_bus: int
    buyer_household_id: str
    seller_household_id: str
    amount_kwh: float
    price_per_kwh: float
    total_price: float
    status: str
    feasibility: Optional[Dict[str, Any]] = None


class GridStateResponse(BaseModel):
    converged: bool
    is_feasible: bool
    buses: List[Dict[str, Any]]
    lines: List[Dict[str, Any]]
    max_voltage_deviation: float
    max_line_loading: float
    num_voltage_violations: int
    num_line_violations: int
    solve_time_ms: float


class TopologyResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class SimulationStateResponse(BaseModel):
    session_id: str
    is_running: bool
    current_timestep: int
    total_timesteps: int
    speed_multiplier: float
    total_trades_executed: int
    total_trades_rejected: int
    total_trades_partial: int
    total_energy_traded_kwh: float
    total_violations_prevented: int
    total_revenue: float


class SimulationStepResponse(BaseModel):
    timestep: int
    simulation_time: str
    orders_submitted: int
    trades_matched: int
    trades_executed: int
    trades_rejected: int
    step_time_ms: float
    aggregate_stats: Dict[str, Any]
    grid_state: Dict[str, Any]
    trades: List[Dict[str, Any]]


class TradeStatsResponse(BaseModel):
    total_trades: int
    total_executed: int
    total_rejected: int
    total_partial: int
    total_energy_kwh: float
    total_revenue: float
    avg_price: float
    violations_prevented: int


class HouseholdResponse(BaseModel):
    household_id: str
    bus_id: int
    has_solar: bool
    solar_capacity_kw: float


class ChainVerificationResponse(BaseModel):
    valid: bool
    total_records: int
    records_checked: int
    first_broken_at: Optional[int] = None
    errors: List[str]


class HealthResponse(BaseModel):
    status: str
    version: str
    mongodb_connected: bool
    gnn_model_loaded: bool
    simulation_running: bool
