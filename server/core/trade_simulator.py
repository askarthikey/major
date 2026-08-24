"""
Trade simulator for GNN training data generation.

This is the data generation pipeline described in Section 7 of the plan.
It generates thousands of (grid_state, candidate_trade) → (feasible/infeasible,
voltage_deltas, loading_deltas) labeled examples by:

1. Loading the feeder with real/synthetic household profiles at various timesteps
2. Sampling random candidate trades (buyer-seller pairs, random amounts)
3. Running pandapower power flow for each candidate trade
4. Recording the ground-truth label (feasible/infeasible) and continuous values
5. Deliberately oversampling edge-case scenarios for class balance

Every label comes from pandapower's physics solver — the ground truth is real
physics, not a guess. Only the trade combinations are synthetic, which is
standard practice in safety-critical ML research.
"""

import pandapower as pp
import numpy as np
import pandas as pd
import json
import logging
import time
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from core.feeder_setup import create_ieee13_feeder
from core.attach_profiles import (
    generate_synthetic_profiles,
    attach_profiles_to_network,
    DEFAULT_HOUSEHOLD_BUS_MAP,
)
from core.run_powerflow import solve_power_flow, solve_with_trade_applied
from config.settings import settings

logger = logging.getLogger(__name__)


def get_solar_households() -> List[str]:
    """Get household IDs that have solar panels (potential sellers)."""
    return [
        hh_id for hh_id, config in DEFAULT_HOUSEHOLD_BUS_MAP.items()
        if config["has_solar"]
    ]


def get_non_solar_households() -> List[str]:
    """Get household IDs without solar panels (potential buyers)."""
    return [
        hh_id for hh_id, config in DEFAULT_HOUSEHOLD_BUS_MAP.items()
        if not config["has_solar"]
    ]


def sample_candidate_trade(
    household_states: Dict[str, Dict],
    rng: np.random.Generator,
    oversample_high_load: bool = False,
) -> Optional[Dict]:
    """
    Sample a random candidate trade between a solar household (seller)
    and a non-solar household (buyer).

    Args:
        household_states: Current state of all households
            {hh_id: {bus_id, load_kw, solar_kw, surplus_kw, ...}}
        rng: NumPy random generator.
        oversample_high_load: If True, bias toward larger trade amounts
            to generate more infeasible examples for class balance.

    Returns:
        Dict with trade parameters, or None if no valid trade is possible.
    """
    solar_hhs = [
        hh_id for hh_id, state in household_states.items()
        if state.get("has_solar", False) and state.get("surplus_kw", 0) > 0.1
    ]

    non_solar_hhs = [
        hh_id for hh_id, state in household_states.items()
        if not state.get("has_solar", False) and state.get("load_kw", 0) > 0.1
    ]

    if not solar_hhs or not non_solar_hhs:
        return None

    # Pick random seller and buyer
    seller_id = rng.choice(solar_hhs)
    buyer_id = rng.choice(non_solar_hhs)

    seller_state = household_states[seller_id]
    buyer_state = household_states[buyer_id]

    # Determine trade amount
    max_amount = seller_state["surplus_kw"]

    if oversample_high_load:
        # Bias toward larger amounts — multiply by 1.5-3x to push grid limits
        multiplier = 1.5 + rng.random() * 1.5
        trade_amount = max_amount * multiplier
    else:
        # Normal: random amount up to the seller's surplus
        trade_amount = rng.uniform(0.1, max(0.2, max_amount))

    trade_amount = round(trade_amount, 3)

    return {
        "seller_household_id": seller_id,
        "buyer_household_id": buyer_id,
        "seller_bus": seller_state["bus_id"],
        "buyer_bus": buyer_state["bus_id"],
        "amount_kw": trade_amount,
        "seller_surplus_kw": seller_state["surplus_kw"],
        "buyer_load_kw": buyer_state["load_kw"],
    }


def generate_training_data(
    num_samples: int = 20000,
    num_timesteps: int = 96,
    oversample_ratio: float = 0.3,
    seed: int = 42,
    output_dir: Optional[str] = None,
    profiles: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Generate the full GNN training dataset.

    For each sample:
    1. Pick a random timestep
    2. Attach household profiles to the feeder
    3. Sample a random candidate trade
    4. Run power flow with the trade applied
    5. Record the ground-truth label and continuous values

    Args:
        num_samples: Total number of labeled examples to generate.
        num_timesteps: Number of timesteps in the profile data.
        oversample_ratio: Fraction of samples where we deliberately
            push toward high-load scenarios for class balance.
        seed: Random seed for reproducibility.
        output_dir: Directory to save the output (default: data/synthetic_trades/).
        profiles: Pre-loaded profiles DataFrame (generates synthetic if None).

    Returns:
        DataFrame with all training examples.
    """
    rng = np.random.default_rng(seed)

    # Create network
    net = create_ieee13_feeder()

    # Load or generate profiles
    if profiles is None:
        profiles = generate_synthetic_profiles(num_timesteps=num_timesteps, seed=seed)

    logger.info(f"Generating {num_samples} training examples...")
    start_time = time.time()

    records = []
    feasible_count = 0
    infeasible_count = 0

    for i in range(num_samples):
        if (i + 1) % 1000 == 0:
            elapsed = time.time() - start_time
            logger.info(
                f"Progress: {i+1}/{num_samples} "
                f"({elapsed:.1f}s, feasible={feasible_count}, infeasible={infeasible_count})"
            )

        # Pick random timestep
        timestep_idx = rng.integers(0, num_timesteps)

        # Attach profiles for this timestep
        household_states = attach_profiles_to_network(net, profiles, timestep_idx)

        # Should we oversample high-load scenarios?
        oversample = rng.random() < oversample_ratio

        # Sample a candidate trade
        trade = sample_candidate_trade(household_states, rng, oversample_high_load=oversample)
        if trade is None:
            continue

        # Run power flow with trade applied
        try:
            baseline_result, trade_result = solve_with_trade_applied(
                net,
                seller_bus=trade["seller_bus"],
                buyer_bus=trade["buyer_bus"],
                amount_kw=trade["amount_kw"],
            )
        except Exception as e:
            logger.warning(f"Power flow error at sample {i}: {e}")
            continue

        if not baseline_result.converged or not trade_result.converged:
            continue

        # Compute deltas (change caused by the trade)
        voltage_deltas = {
            bus: trade_result.bus_voltages.get(bus, 1.0) - baseline_result.bus_voltages.get(bus, 1.0)
            for bus in baseline_result.bus_voltages
        }
        loading_deltas = {
            line: trade_result.line_loadings.get(line, 0) - baseline_result.line_loadings.get(line, 0)
            for line in baseline_result.line_loadings
        }

        is_feasible = trade_result.is_feasible
        if is_feasible:
            feasible_count += 1
        else:
            infeasible_count += 1

        record = {
            "sample_id": i,
            "timestep_idx": timestep_idx,
            "seller_bus": trade["seller_bus"],
            "buyer_bus": trade["buyer_bus"],
            "amount_kw": trade["amount_kw"],
            "seller_surplus_kw": trade["seller_surplus_kw"],
            "buyer_load_kw": trade["buyer_load_kw"],
            "is_feasible": is_feasible,
            "oversampled": oversample,
            # Baseline grid state
            "baseline_max_v_dev": baseline_result.max_voltage_deviation,
            "baseline_max_line_load": baseline_result.max_line_loading,
            # With-trade grid state
            "trade_max_v_dev": trade_result.max_voltage_deviation,
            "trade_max_line_load": trade_result.max_line_loading,
            "num_voltage_violations": len(trade_result.voltage_violations),
            "num_line_violations": len(trade_result.line_violations),
            # Deltas (changes caused by the trade)
            "max_voltage_delta": max(abs(v) for v in voltage_deltas.values()) if voltage_deltas else 0,
            "max_loading_delta": max(abs(v) for v in loading_deltas.values()) if loading_deltas else 0,
            # Per-bus and per-line details (stored as JSON strings for the DataFrame)
            "voltage_deltas_json": json.dumps({str(k): round(v, 6) for k, v in voltage_deltas.items()}),
            "loading_deltas_json": json.dumps({str(k): round(v, 4) for k, v in loading_deltas.items()}),
            "bus_voltages_json": json.dumps({str(k): round(v, 6) for k, v in trade_result.bus_voltages.items()}),
            "line_loadings_json": json.dumps({str(k): round(v, 4) for k, v in trade_result.line_loadings.items()}),
            "solve_time_ms": trade_result.solve_time_ms,
        }
        records.append(record)

    df = pd.DataFrame(records)

    # Save to disk
    if output_dir is None:
        output_dir = str(settings.data_synthetic_dir)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    output_path = Path(output_dir) / "training_data.parquet"
    df.to_parquet(output_path, index=False)

    csv_path = Path(output_dir) / "training_data.csv"
    df.to_csv(csv_path, index=False)

    elapsed = time.time() - start_time
    logger.info(
        f"Training data generation complete: {len(df)} samples in {elapsed:.1f}s\n"
        f"  Feasible: {feasible_count} ({feasible_count/max(1,len(df))*100:.1f}%)\n"
        f"  Infeasible: {infeasible_count} ({infeasible_count/max(1,len(df))*100:.1f}%)\n"
        f"  Saved to: {output_path}"
    )

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Generate a small test batch first
    print("Generating test batch (500 samples)...")
    df = generate_training_data(num_samples=500, seed=42)
    print(f"\nDataset shape: {df.shape}")
    print(f"\nClass distribution:")
    print(df["is_feasible"].value_counts())
    print(f"\nSample record:")
    print(df.iloc[0].to_dict())
