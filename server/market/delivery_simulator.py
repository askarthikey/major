"""
Simulated Physical Delivery & Metering for P2P Energy Trades.

When the feasibility gate approves a trade, the energy doesn't teleport
instantly. This module simulates the physical reality:

    MARKET LAYER       "200 kWh approved"
         ↓
    PHYSICAL LAYER     "100 kW dispatched over 2 hours"
         ↓
    MEASUREMENT LAYER  "197.5 kWh actually metered"

The simulation accounts for:
- Power-over-time dispatch (kW × hours = kWh)
- Solar intermittency (cloud cover variation)
- Inverter efficiency losses (~2-5%)
- Distribution line losses (~1-3%)

This is a simulation — no real hardware exists. The variation is
controlled and reproducible for demonstration purposes.
"""

import logging
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# --- Realistic variation parameters ---

# Solar intermittency: cloud cover causes small output variation per interval
SOLAR_INTERMITTENCY_RANGE = (0.985, 1.00)

# Inverter efficiency: modern inverters are 98.5-99.5% efficient
INVERTER_EFFICIENCY_RANGE = (0.985, 0.995)

# Line/distribution losses: 0.2-1% for local microgrid
LINE_LOSS_RANGE = (0.99, 0.998)

# Delivery duration constants
MIN_DELIVERY_HOURS = 0.25   # Minimum 15 minutes
MAX_DELIVERY_HOURS = 4.0    # Maximum 4 hours
KWH_PER_HOUR_BASE = 100.0  # Base dispatch rate (adjustable)


@dataclass
class DeliveryInterval:
    """A single time interval in the delivery schedule."""
    interval_index: int
    start_minutes: float
    end_minutes: float
    duration_minutes: float
    dispatch_kw: float
    scheduled_kwh: float
    actual_kwh: float
    solar_factor: float
    inverter_efficiency: float
    line_loss_factor: float
    cumulative_delivered_kwh: float


@dataclass
class DeliveryResult:
    """Complete result of a simulated physical delivery."""
    # Schedule
    scheduled_kwh: float
    dispatch_power_kw: float
    delivery_duration_hours: float
    num_intervals: int
    interval_duration_minutes: float

    # Actual metered
    actual_delivered_kwh: float
    delivery_efficiency: float  # actual / scheduled as fraction

    # Loss breakdown
    avg_solar_factor: float
    avg_inverter_efficiency: float
    avg_line_loss_factor: float

    # Status
    delivery_status: str  # "completed" or "under_delivered"
    discrepancy_kwh: float
    discrepancy_percent: float

    # Timeline
    delivery_start: str
    delivery_end: str
    intervals: List[Dict]

    def to_dict(self) -> Dict:
        """Convert to dictionary for MongoDB storage."""
        return {
            "scheduled_kwh": round(self.scheduled_kwh, 4),
            "dispatch_power_kw": round(self.dispatch_power_kw, 4),
            "delivery_duration_hours": round(self.delivery_duration_hours, 4),
            "num_intervals": self.num_intervals,
            "interval_duration_minutes": round(self.interval_duration_minutes, 2),
            "actual_delivered_kwh": round(self.actual_delivered_kwh, 4),
            "delivery_efficiency": round(self.delivery_efficiency, 4),
            "avg_solar_factor": round(self.avg_solar_factor, 4),
            "avg_inverter_efficiency": round(self.avg_inverter_efficiency, 4),
            "avg_line_loss_factor": round(self.avg_line_loss_factor, 4),
            "delivery_status": self.delivery_status,
            "discrepancy_kwh": round(self.discrepancy_kwh, 4),
            "discrepancy_percent": round(self.discrepancy_percent, 2),
            "delivery_start": self.delivery_start,
            "delivery_end": self.delivery_end,
            "intervals": self.intervals,
        }


class DeliverySimulator:
    """
    Simulates the physical delivery of energy for an approved trade.

    Models the fact that energy is delivered as power over time,
    not as an instantaneous kWh teleportation. Applies realistic
    variation factors to produce metered values that differ slightly
    from the scheduled amount.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Args:
            seed: Optional random seed for reproducible simulations.
        """
        self.rng = random.Random(seed)

    def simulate_delivery(
        self,
        scheduled_kwh: float,
        seller_bus: int,
        buyer_bus: int,
        start_time: Optional[datetime] = None,
    ) -> DeliveryResult:
        """
        Simulate the physical delivery of scheduled energy.

        Converts the scheduled kWh into a power dispatch schedule,
        simulates delivery over multiple time intervals with realistic
        variation, and returns the metered actual delivery.

        Args:
            scheduled_kwh: Amount of energy approved by feasibility gate (kWh).
            seller_bus: Seller's bus ID (affects line loss calculation).
            buyer_bus: Buyer's bus ID (affects line loss calculation).
            start_time: When delivery starts. Defaults to now.

        Returns:
            DeliveryResult with scheduled, dispatched, and metered values.
        """
        if start_time is None:
            start_time = datetime.utcnow()

        # --- 1. Calculate dispatch schedule ---
        # Energy = Power × Time → determine power and duration
        delivery_hours = self._calculate_delivery_duration(scheduled_kwh)
        dispatch_kw = scheduled_kwh / delivery_hours

        # --- 2. Break into intervals ---
        # Use 15-minute intervals (matching the grid simulation timestep)
        interval_minutes = 15.0
        num_intervals = max(1, math.ceil(delivery_hours * 60 / interval_minutes))

        # Adjust interval duration so total matches delivery_hours exactly
        actual_interval_minutes = (delivery_hours * 60) / num_intervals
        kwh_per_interval = scheduled_kwh / num_intervals

        # --- 3. Simulate each interval with variation ---
        intervals: List[DeliveryInterval] = []
        cumulative_kwh = 0.0
        total_solar = 0.0
        total_inverter = 0.0
        total_line = 0.0

        for i in range(num_intervals):
            # Solar intermittency — varies per interval (simulates clouds)
            solar_factor = self.rng.uniform(*SOLAR_INTERMITTENCY_RANGE)

            # Inverter efficiency — relatively stable but not perfect
            inverter_eff = self.rng.uniform(*INVERTER_EFFICIENCY_RANGE)

            # Line losses — depends on electrical distance between buses
            bus_distance_factor = self._estimate_line_loss_factor(seller_bus, buyer_bus)
            line_loss = bus_distance_factor

            # Actual delivered for this interval
            combined_factor = solar_factor * inverter_eff * line_loss
            actual_interval_kwh = kwh_per_interval * combined_factor
            cumulative_kwh += actual_interval_kwh

            total_solar += solar_factor
            total_inverter += inverter_eff
            total_line += line_loss

            interval = DeliveryInterval(
                interval_index=i,
                start_minutes=i * actual_interval_minutes,
                end_minutes=(i + 1) * actual_interval_minutes,
                duration_minutes=actual_interval_minutes,
                dispatch_kw=dispatch_kw,
                scheduled_kwh=round(kwh_per_interval, 4),
                actual_kwh=round(actual_interval_kwh, 4),
                solar_factor=round(solar_factor, 4),
                inverter_efficiency=round(inverter_eff, 4),
                line_loss_factor=round(line_loss, 4),
                cumulative_delivered_kwh=round(cumulative_kwh, 4),
            )
            intervals.append(interval)

        # --- 4. Compute final metered values ---
        actual_delivered = cumulative_kwh
        efficiency = actual_delivered / scheduled_kwh if scheduled_kwh > 0 else 0
        discrepancy = scheduled_kwh - actual_delivered
        discrepancy_pct = (discrepancy / scheduled_kwh * 100) if scheduled_kwh > 0 else 0

        # Under-delivery threshold: >3% discrepancy
        delivery_status = "under_delivered" if discrepancy_pct > 3.0 else "completed"

        end_time = start_time + timedelta(hours=delivery_hours)

        result = DeliveryResult(
            scheduled_kwh=scheduled_kwh,
            dispatch_power_kw=dispatch_kw,
            delivery_duration_hours=delivery_hours,
            num_intervals=num_intervals,
            interval_duration_minutes=actual_interval_minutes,
            actual_delivered_kwh=round(actual_delivered, 4),
            delivery_efficiency=efficiency,
            avg_solar_factor=total_solar / num_intervals,
            avg_inverter_efficiency=total_inverter / num_intervals,
            avg_line_loss_factor=total_line / num_intervals,
            delivery_status=delivery_status,
            discrepancy_kwh=round(discrepancy, 4),
            discrepancy_percent=round(discrepancy_pct, 2),
            delivery_start=start_time.isoformat(),
            delivery_end=end_time.isoformat(),
            intervals=[
                {
                    "index": iv.interval_index,
                    "start_min": round(iv.start_minutes, 2),
                    "end_min": round(iv.end_minutes, 2),
                    "dispatch_kw": round(iv.dispatch_kw, 2),
                    "scheduled_kwh": iv.scheduled_kwh,
                    "actual_kwh": iv.actual_kwh,
                    "solar_factor": iv.solar_factor,
                    "inverter_eff": iv.inverter_efficiency,
                    "line_loss": iv.line_loss_factor,
                    "cumulative_kwh": iv.cumulative_delivered_kwh,
                }
                for iv in intervals
            ],
        )

        logger.info(
            f"Delivery simulated: {scheduled_kwh:.3f} kWh scheduled → "
            f"{actual_delivered:.3f} kWh delivered "
            f"({efficiency:.1%} efficiency, {delivery_status}) "
            f"over {delivery_hours:.2f}h at {dispatch_kw:.1f} kW"
        )

        return result

    def _calculate_delivery_duration(self, kwh: float) -> float:
        """
        Calculate how long the delivery takes based on energy amount.

        Uses a simple model: duration scales with energy amount,
        clamped between MIN and MAX delivery hours.

        Small trades (<10 kWh): ~15-30 minutes
        Medium trades (10-100 kWh): ~30 min to 2 hours
        Large trades (>100 kWh): ~2-4 hours
        """
        # Base: 1 hour per 100 kWh
        hours = kwh / KWH_PER_HOUR_BASE

        # Add some natural variation (±10%)
        hours *= self.rng.uniform(0.9, 1.1)

        # Clamp to realistic range
        return max(MIN_DELIVERY_HOURS, min(MAX_DELIVERY_HOURS, hours))

    def _estimate_line_loss_factor(self, seller_bus: int, buyer_bus: int) -> float:
        """
        Estimate line loss factor based on bus distance.

        Buses that are electrically farther apart have higher losses.
        Since this is a simulation, we approximate distance by bus ID
        difference (buses closer in ID tend to be electrically closer
        in the IEEE 13-bus feeder).
        """
        bus_diff = abs(seller_bus - buyer_bus)
        # More distant buses → slightly higher losses
        # Scale: adjacent buses ~0.1% loss, far buses ~1% loss
        max_loss = 0.010
        min_loss = 0.001
        loss_fraction = min(1.0, bus_diff / 12.0)  # Normalize to 13-bus system
        loss = min_loss + (max_loss - min_loss) * loss_fraction

        # Add small random variation
        loss *= self.rng.uniform(0.8, 1.2)
        loss = min(loss, 0.015)  # Cap at 1.5%

        return 1.0 - loss


# --- Singleton instance ---
_simulator: Optional[DeliverySimulator] = None


def get_delivery_simulator() -> DeliverySimulator:
    """Get or create the singleton delivery simulator."""
    global _simulator
    if _simulator is None:
        _simulator = DeliverySimulator()
    return _simulator
