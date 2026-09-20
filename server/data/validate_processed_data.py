"""
Validate processed Pecan Street and ISO data.

Checks:
1. All 13 households present in profiles.parquet
2. No NaN / negative values
3. Reasonable value ranges
4. Per-household summary stats

Usage:
    cd server
    .venv\\Scripts\\python.exe data\\validate_processed_data.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

DATA_DIR = Path(__file__).parent
PROCESSED_DIR = DATA_DIR / "processed"

EXPECTED_HOUSEHOLDS = [f"HH_{i:02d}" for i in range(1, 14)]
SOLAR_HOUSEHOLDS = {"HH_01", "HH_03", "HH_05", "HH_06", "HH_09", "HH_11"}


def validate_profiles():
    """Validate the household profiles parquet."""
    print("=" * 70)
    print("  VALIDATING profiles.parquet")
    print("=" * 70)

    path = PROCESSED_DIR / "profiles.parquet"
    if not path.exists():
        print(f"FAIL: {path} does not exist!")
        return False

    df = pd.read_parquet(path)
    print(f"Loaded {len(df):,} rows, {df.shape[1]} columns")
    print(f"Columns: {list(df.columns)}")
    all_pass = True

    # --- Check 1: All 13 households ---
    present = sorted(df["household_id"].unique())
    missing = [h for h in EXPECTED_HOUSEHOLDS if h not in present]
    if missing:
        print(f"FAIL: Missing households: {missing}")
        all_pass = False
    else:
        print(f"PASS: All {len(EXPECTED_HOUSEHOLDS)} households present")

    # --- Check 2: No NaN values ---
    nan_counts = df[["load_kw", "solar_kw"]].isna().sum()
    if nan_counts.any():
        print(f"FAIL: NaN values found: {dict(nan_counts[nan_counts > 0])}")
        all_pass = False
    else:
        print("PASS: No NaN values in load_kw/solar_kw")

    # --- Check 3: Non-negative values ---
    neg_load = (df["load_kw"] < 0).sum()
    neg_solar = (df["solar_kw"] < 0).sum()
    if neg_load > 0 or neg_solar > 0:
        print(f"FAIL: Negative values: load_kw={neg_load}, solar_kw={neg_solar}")
        all_pass = False
    else:
        print("PASS: All load_kw and solar_kw values >= 0")

    # --- Check 4: Solar households have solar generation ---
    for hh in SOLAR_HOUSEHOLDS:
        hh_data = df[df["household_id"] == hh]
        solar_mean = hh_data["solar_kw"].mean()
        if solar_mean < 0.01:
            print(f"FAIL: Solar household {hh} has near-zero solar (mean={solar_mean:.4f})")
            all_pass = False
        else:
            print(f"PASS: {hh} has solar generation (mean={solar_mean:.3f} kW)")

    # --- Check 5: Non-solar households have zero solar ---
    non_solar = set(EXPECTED_HOUSEHOLDS) - SOLAR_HOUSEHOLDS
    for hh in sorted(non_solar):
        hh_data = df[df["household_id"] == hh]
        solar_sum = hh_data["solar_kw"].sum()
        if solar_sum > 0.001:
            print(f"WARN: Non-solar household {hh} has solar_kw sum={solar_sum:.3f}")
        else:
            print(f"PASS: {hh} has zero solar generation")

    # --- Check 6: Reasonable load ranges ---
    print(f"\n--- Per-household Statistics ---")
    print(f"{'HH':<8} {'Rows':>7} {'Load Mean':>10} {'Load Max':>10} {'Solar Mean':>10} {'Solar Max':>10} {'Location'}")
    print("-" * 75)
    for hh in sorted(df["household_id"].unique()):
        hh_data = df[df["household_id"] == hh]
        solar_tag = "*" if hh in SOLAR_HOUSEHOLDS else " "
        print(
            f"{solar_tag}{hh:<7} {len(hh_data):>7,} "
            f"{hh_data['load_kw'].mean():>10.3f} "
            f"{hh_data['load_kw'].max():>10.3f} "
            f"{hh_data['solar_kw'].mean():>10.3f} "
            f"{hh_data['solar_kw'].max():>10.3f} "
            f"{hh_data['location'].iloc[0]}"
        )

    # --- Check 7: Timestamp sanity ---
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    print(f"\nTimestamp range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

    # Check 15-min intervals for each household
    for hh in sorted(df["household_id"].unique()):
        hh_data = df[df["household_id"] == hh].sort_values("timestamp")
        diffs = hh_data["timestamp"].diff().dropna()
        median_diff = diffs.median()
        non_15min = (diffs != pd.Timedelta(minutes=15)).sum()
        if non_15min > 0:
            print(f"  {hh}: {non_15min} non-15-min gaps (median interval: {median_diff})")
        else:
            print(f"  {hh}: All intervals are 15 minutes")

    return all_pass


def validate_iso():
    """Validate the ISO profiles parquet."""
    print(f"\n{'='*70}")
    print("  VALIDATING iso_profiles.parquet")
    print(f"{'='*70}")

    path = PROCESSED_DIR / "iso_profiles.parquet"
    if not path.exists():
        print(f"FAIL: {path} does not exist!")
        return False

    df = pd.read_parquet(path)
    print(f"Loaded {len(df):,} rows, {df.shape[1]} columns")
    print(f"Columns: {list(df.columns)}")
    all_pass = True

    # No NaN
    nan_counts = df.isna().sum()
    has_nan = nan_counts[nan_counts > 0]
    if len(has_nan) > 0:
        print(f"FAIL: NaN values: {dict(has_nan)}")
        all_pass = False
    else:
        print("PASS: No NaN values")

    # Reasonable ranges
    print(f"\n  Grid Load (MW):    [{df['grid_load_mw'].min():.1f}, {df['grid_load_mw'].max():.1f}], mean={df['grid_load_mw'].mean():.1f}")
    print(f"  Solar Prod (MW):   [{df['solar_production_mw'].min():.1f}, {df['solar_production_mw'].max():.1f}], mean={df['solar_production_mw'].mean():.1f}")
    print(f"  Net Load (MW):     [{df['net_load_mw'].min():.1f}, {df['net_load_mw'].max():.1f}]")
    print(f"  Solar Penetration: [{df['solar_penetration'].min():.2%}, {df['solar_penetration'].max():.2%}]")

    # Timestamp checks
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    diffs = df["timestamp"].sort_values().diff().dropna()
    median_diff = diffs.median()
    if median_diff == pd.Timedelta(minutes=15):
        print(f"PASS: ISO data is at 15-min intervals (median: {median_diff})")
    else:
        print(f"WARN: Unexpected ISO interval (median: {median_diff})")

    print(f"  Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    return all_pass


def main():
    print("=" * 70)
    print("  DATA VALIDATION REPORT")
    print("=" * 70)

    profiles_ok = validate_profiles()
    iso_ok = validate_iso()

    print(f"\n{'='*70}")
    print(f"  OVERALL RESULT")
    print(f"{'='*70}")
    if profiles_ok and iso_ok:
        print("  ALL CHECKS PASSED")
    else:
        print("  SOME CHECKS FAILED - review output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
