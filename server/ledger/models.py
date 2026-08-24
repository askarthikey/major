"""
Pydantic models for MongoDB document schemas.
These serve as both validation schemas and documentation of the data structure.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class TradeStatus(str, Enum):
    """Status of a trade in the system."""
    PENDING = "pending"           # Matched by auction, awaiting feasibility check
    FEASIBLE = "feasible"         # Passed GNN feasibility gate
    INFEASIBLE = "infeasible"     # Failed feasibility gate — would cause grid violation
    EXECUTED = "executed"         # Successfully executed
    PARTIAL_FILL = "partial_fill" # Partially filled (reduced quantity to maintain feasibility)
    REJECTED = "rejected"         # Rejected after feasibility check


class FeasibilityResult(BaseModel):
    """Result from the GNN feasibility gate check."""
    is_feasible: bool
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence score")
    max_voltage_deviation: float = Field(description="Maximum voltage deviation in p.u.")
    max_line_loading: float = Field(description="Maximum line loading percentage")
    violated_buses: List[int] = Field(default_factory=list, description="Bus IDs with voltage violations")
    violated_lines: List[int] = Field(default_factory=list, description="Line IDs with thermal violations")
    suggested_max_amount_kwh: Optional[float] = Field(
        default=None,
        description="If infeasible, the max trade amount that would be feasible (for partial fill)",
    )
    check_method: str = Field(
        default="pandapower",
        description="Method used: 'gnn' or 'pandapower' (fallback)",
    )


class TradeRecord(BaseModel):
    """A single trade record in the ledger."""
    trade_id: str = Field(description="Unique trade identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Participants
    buyer_bus: int = Field(description="Bus ID of the buyer")
    seller_bus: int = Field(description="Bus ID of the seller")
    buyer_household_id: str = Field(description="Household ID of the buyer")
    seller_household_id: str = Field(description="Household ID of the seller")
    
    # Trade details
    amount_kwh: float = Field(gt=0, description="Energy amount in kWh")
    price_per_kwh: float = Field(gt=0, description="Clearing price per kWh")
    total_price: float = Field(description="Total trade value")
    original_amount_kwh: Optional[float] = Field(
        default=None,
        description="Original amount before partial fill adjustment",
    )
    
    # Status and feasibility
    status: TradeStatus = Field(default=TradeStatus.PENDING)
    feasibility: Optional[FeasibilityResult] = None
    
    # Hash chain (tamper-evidence)
    prev_hash: str = Field(default="", description="SHA-256 hash of the previous trade record")
    this_hash: str = Field(default="", description="SHA-256 hash of this trade record's content")
    
    # Metadata
    simulation_timestep: int = Field(default=0, description="Simulation timestep index")
    
    class Config:
        use_enum_values = True


class BusState(BaseModel):
    """State of a single bus in the grid."""
    bus_id: int
    voltage_pu: float = Field(description="Voltage in per-unit")
    voltage_kv: float = Field(description="Voltage in kV")
    net_injection_kw: float = Field(description="Net power injection in kW (positive = generation)")
    has_solar: bool = Field(default=False)
    load_kw: float = Field(default=0.0, description="Current load in kW")
    solar_generation_kw: float = Field(default=0.0, description="Current solar generation in kW")
    is_violation: bool = Field(default=False, description="True if voltage is out of ±5% bounds")


class LineState(BaseModel):
    """State of a single line in the grid."""
    line_id: int
    from_bus: int
    to_bus: int
    loading_percent: float = Field(description="Line loading as percentage of thermal limit")
    current_ka: float = Field(description="Current in kA")
    is_violation: bool = Field(default=False, description="True if loading exceeds thermal limit")


class GridSnapshot(BaseModel):
    """Complete snapshot of the grid state at a point in time."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    simulation_timestep: int
    buses: List[BusState]
    lines: List[LineState]
    total_load_kw: float
    total_generation_kw: float
    num_voltage_violations: int = 0
    num_line_violations: int = 0
    is_healthy: bool = Field(
        default=True,
        description="True if no violations exist anywhere in the grid",
    )


class HouseholdProfile(BaseModel):
    """Profile of a household connected to the grid."""
    household_id: str
    bus_id: int
    has_solar: bool = Field(default=False)
    solar_capacity_kw: float = Field(default=0.0, description="Installed solar panel capacity")
    avg_daily_load_kwh: float = Field(default=0.0)
    current_load_kw: float = Field(default=0.0)
    current_solar_kw: float = Field(default=0.0)
    surplus_kw: float = Field(default=0.0, description="Available surplus for selling")


class Bid(BaseModel):
    """A bid or ask in the auction."""
    household_id: str
    bus_id: int
    is_buy: bool = Field(description="True for buy bid, False for sell ask")
    quantity_kwh: float = Field(gt=0)
    price_per_kwh: float = Field(gt=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SimulationState(BaseModel):
    """Current state of the simulation engine."""
    session_id: str
    is_running: bool = Field(default=False)
    current_timestep: int = Field(default=0)
    total_timesteps: int = Field(default=96, description="Default: 96 steps = 24h at 15min intervals")
    speed_multiplier: float = Field(default=1.0)
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    
    # Aggregate stats
    total_trades_executed: int = 0
    total_trades_rejected: int = 0
    total_trades_partial: int = 0
    total_energy_traded_kwh: float = 0.0
    total_violations_prevented: int = 0
    total_revenue: float = 0.0
