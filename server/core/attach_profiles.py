"""
Attach household load/solar profiles to buses in the feeder network.

This module maps real household energy data (load consumption and solar generation)
onto specific buses in the IEEE 13-bus test feeder. The data loader is designed to
be dataset-agnostic — it expects a common schema and can work with Pecan Street,
REFIT, UK-DALE, or synthetic data by changing configuration.

Common schema expected:
    timestamp (datetime), household_id (str), load_kw (float), solar_kw (float)

Some households have solar panels (sellers), some don't (buyers only).
The mapping of households to buses is configurable and represents the physical
location of each household on the distribution network.
"""

import pandas as pd
import numpy as np
import pandapower as pp
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)

# Default household-to-bus mapping for the IEEE 13-bus feeder.
# Buses with solar panels are marked — these are potential sellers.
# This reflects a realistic suburban distribution: not every household has solar.
DEFAULT_HOUSEHOLD_BUS_MAP = {
    "HH_01": {"bus_id": 2,  "has_solar": True,  "solar_capacity_kw": 5.0},
    "HH_02": {"bus_id": 2,  "has_solar": False, "solar_capacity_kw": 0.0},
    "HH_03": {"bus_id": 4,  "has_solar": True,  "solar_capacity_kw": 8.0},
    "HH_04": {"bus_id": 5,  "has_solar": False, "solar_capacity_kw": 0.0},
    "HH_05": {"bus_id": 6,  "has_solar": True,  "solar_capacity_kw": 4.0},
    "HH_06": {"bus_id": 7,  "has_solar": True,  "solar_capacity_kw": 6.0},
    "HH_07": {"bus_id": 7,  "has_solar": False, "solar_capacity_kw": 0.0},
    "HH_08": {"bus_id": 8,  "has_solar": False, "solar_capacity_kw": 0.0},
    "HH_09": {"bus_id": 9,  "has_solar": True,  "solar_capacity_kw": 7.0},
    "HH_10": {"bus_id": 10, "has_solar": False, "solar_capacity_kw": 0.0},
    "HH_11": {"bus_id": 11, "has_solar": True,  "solar_capacity_kw": 5.0},
    "HH_12": {"bus_id": 12, "has_solar": False, "solar_capacity_kw": 0.0},
    "HH_13": {"bus_id": 9,  "has_solar": False, "solar_capacity_kw": 0.0},
}


def generate_synthetic_profiles(
    num_timesteps: int = 96,  # 24 hours at 15-min intervals
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic household load and solar generation profiles.

    Used as a fallback when real datasets are not yet available. The synthetic
    data follows realistic daily patterns:
    - Load: higher in morning (7-9) and evening (18-22), lower overnight
    - Solar: bell curve peaking at noon, zero at night

    Args:
        num_timesteps: Number of 15-minute intervals to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns: timestamp, household_id, load_kw, solar_kw
    """
    rng = np.random.default_rng(seed)

    timestamps = pd.date_range(
        start="2024-06-15 00:00",
        periods=num_timesteps,
        freq="15min",
    )

    records = []

    for hh_id, hh_config in DEFAULT_HOUSEHOLD_BUS_MAP.items():
        # Base load profile (kW) — realistic daily pattern
        base_load = np.zeros(num_timesteps)
        for t in range(num_timesteps):
            hour = (t * 15 / 60) % 24  # Convert timestep to hour of day

            # Overnight baseline (0-6): 0.3-0.8 kW
            if hour < 6:
                base_load[t] = 0.3 + rng.normal(0, 0.1)
            # Morning ramp (6-9): 1.0-2.5 kW
            elif hour < 9:
                base_load[t] = 1.0 + 1.5 * ((hour - 6) / 3) + rng.normal(0, 0.2)
            # Daytime (9-17): 0.8-1.5 kW (many people at work)
            elif hour < 17:
                base_load[t] = 0.8 + rng.normal(0, 0.2)
            # Evening peak (17-22): 2.0-4.0 kW (cooking, AC, entertainment)
            elif hour < 22:
                peak_factor = 1.0 - abs(hour - 19.5) / 2.5  # Peak at 7:30 PM
                base_load[t] = 2.0 + 2.0 * max(0, peak_factor) + rng.normal(0, 0.3)
            # Late evening (22-24): declining to baseline
            else:
                base_load[t] = 1.5 - 1.0 * ((hour - 22) / 2) + rng.normal(0, 0.15)

        # Add household-specific variation (±30%)
        household_factor = 0.7 + rng.random() * 0.6
        base_load = np.maximum(0.1, base_load * household_factor)

        # Solar generation profile (kW) — bell curve, zero at night
        solar_gen = np.zeros(num_timesteps)
        if hh_config["has_solar"]:
            capacity = hh_config["solar_capacity_kw"]
            for t in range(num_timesteps):
                hour = (t * 15 / 60) % 24
                if 6 <= hour <= 18:
                    # Solar bell curve centered at noon
                    solar_factor = np.cos((hour - 12) * np.pi / 12) * 0.5 + 0.5
                    # Add cloud variation (±20%)
                    cloud_factor = 0.8 + rng.random() * 0.4
                    solar_gen[t] = capacity * solar_factor * cloud_factor
                    solar_gen[t] = max(0, solar_gen[t])

        for t in range(num_timesteps):
            records.append({
                "timestamp": timestamps[t],
                "household_id": hh_id,
                "load_kw": round(float(base_load[t]), 3),
                "solar_kw": round(float(solar_gen[t]), 3),
            })

    df = pd.DataFrame(records)
    logger.info(
        f"Generated synthetic profiles: {len(DEFAULT_HOUSEHOLD_BUS_MAP)} households, "
        f"{num_timesteps} timesteps, {len(df)} total records"
    )
    return df


def load_profiles_from_csv(filepath: str) -> pd.DataFrame:
    """
    Load household profiles from a CSV file.

    Expected columns: timestamp, household_id, load_kw, solar_kw
    Adapts column names if they differ slightly (e.g., 'power_kw' → 'load_kw').

    Args:
        filepath: Path to the CSV file.

    Returns:
        DataFrame with standardized columns.
    """
    df = pd.read_csv(filepath, parse_dates=["timestamp"])

    # Standardize column names
    column_mapping = {
        "power_kw": "load_kw",
        "consumption_kw": "load_kw",
        "demand_kw": "load_kw",
        "generation_kw": "solar_kw",
        "pv_kw": "solar_kw",
        "solar_generation_kw": "solar_kw",
        "house_id": "household_id",
        "home_id": "household_id",
    }
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Fill missing solar column (for datasets without solar data)
    if "solar_kw" not in df.columns:
        df["solar_kw"] = 0.0

    required_cols = ["timestamp", "household_id", "load_kw", "solar_kw"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    logger.info(f"Loaded {len(df)} records from {filepath}")
    return df


def attach_profiles_to_network(
    net: pp.pandapowerNet,
    profiles: pd.DataFrame,
    timestep_idx: int,
    household_bus_map: Optional[Dict] = None,
) -> Dict[str, Dict]:
    """
    Attach load/solar profiles for a specific timestep to the pandapower network.

    This modifies the network's load values in-place to reflect the actual
    household consumption and solar generation at the given timestep.

    Args:
        net: pandapower network object.
        profiles: DataFrame with household load/solar time series.
        timestep_idx: Index of the timestep to apply.
        household_bus_map: Optional custom mapping; defaults to DEFAULT_HOUSEHOLD_BUS_MAP.

    Returns:
        Dict mapping household_id → {bus_id, load_kw, solar_kw, net_kw, surplus_kw}
    """
    if household_bus_map is None:
        household_bus_map = DEFAULT_HOUSEHOLD_BUS_MAP

    # Get unique timestamps and select the requested one
    timestamps = sorted(profiles["timestamp"].unique())
    if timestep_idx >= len(timestamps):
        raise IndexError(
            f"timestep_idx {timestep_idx} out of range (max {len(timestamps) - 1})"
        )
    target_time = timestamps[timestep_idx]

    # Filter profiles for this timestep
    step_data = profiles[profiles["timestamp"] == target_time]

    # Aggregate load/solar by bus
    bus_loads = {}  # bus_id → net power in MW (load - solar)
    household_states = {}

    for hh_id, hh_config in household_bus_map.items():
        bus_id = hh_config["bus_id"]
        hh_row = step_data[step_data["household_id"] == hh_id]

        if len(hh_row) == 0:
            load_kw = 1.0  # Default fallback
            solar_kw = 0.0
        else:
            load_kw = float(hh_row.iloc[0]["load_kw"])
            solar_kw = float(hh_row.iloc[0]["solar_kw"])

        net_kw = load_kw - solar_kw  # Positive = consuming, negative = generating surplus
        surplus_kw = max(0, solar_kw - load_kw)

        if bus_id not in bus_loads:
            bus_loads[bus_id] = 0.0
        bus_loads[bus_id] += net_kw

        household_states[hh_id] = {
            "bus_id": bus_id,
            "has_solar": hh_config["has_solar"],
            "load_kw": load_kw,
            "solar_kw": solar_kw,
            "net_kw": net_kw,
            "surplus_kw": surplus_kw,
        }

    # Update pandapower loads
    # Clear existing loads and set new ones based on aggregated bus values
    for load_idx in net.load.index:
        load_bus = net.load.at[load_idx, "bus"]
        if load_bus in bus_loads:
            # Convert kW to MW for pandapower
            net.load.at[load_idx, "p_mw"] = bus_loads[load_bus] / 1000.0
            # Keep reactive power proportional (assume power factor ~0.9)
            net.load.at[load_idx, "q_mvar"] = (bus_loads[load_bus] / 1000.0) * 0.484

    return household_states


def get_households_summary(household_bus_map: Optional[Dict] = None) -> List[Dict]:
    """Get a summary of all households and their bus assignments."""
    if household_bus_map is None:
        household_bus_map = DEFAULT_HOUSEHOLD_BUS_MAP

    return [
        {
            "household_id": hh_id,
            "bus_id": config["bus_id"],
            "has_solar": config["has_solar"],
            "solar_capacity_kw": config["solar_capacity_kw"],
        }
        for hh_id, config in household_bus_map.items()
    ]
