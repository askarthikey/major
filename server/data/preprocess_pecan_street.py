"""
Pecan Street ETL Preprocessing Pipeline.

Loads raw 15-minute residential data from Austin, California, and New York,
selects 13 target households (6 solar + 7 non-solar), computes true
household load (load_kw = grid + solar), cleans the data, and saves
a standardized parquet file for use by the simulation and ML pipeline.

Usage:
    cd server
    .venv\\Scripts\\python.exe data\\preprocess_pecan_street.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import time

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent
OUTPUT_DIR = DATA_DIR / "processed"

# Selected households (from exploration & quality check)
# Format: (dataid, location, has_solar, household_id)
SELECTED_HOUSEHOLDS = [
    # Solar households (6)
    (661,  "austin",     True,  "HH_01"),
    (4767, "austin",     True,  "HH_03"),
    (7536, "austin",     True,  "HH_05"),
    (950,  "newyork",    True,  "HH_06"),
    (142,  "newyork",    True,  "HH_09"),
    (5058, "newyork",    True,  "HH_11"),
    # Non-solar households (7)
    (5746, "austin",     False, "HH_02"),
    (7951, "austin",     False, "HH_04"),
    (9922, "austin",     False, "HH_07"),
    (3687, "california", False, "HH_08"),
    (558,  "newyork",    False, "HH_10"),
    (9053, "newyork",    False, "HH_12"),
    (8565, "austin",     False, "HH_13"),
]

# Map location name -> raw CSV path
LOCATION_FILES = {
    "austin": DATA_DIR / "15_minute_residential_data" / "15minute_data_austin" / "15minute_data_austin.csv",
    "california": DATA_DIR / "15_minute_residential_data" / "15minute_data_california" / "15minute_data_california.csv",
    "newyork": DATA_DIR / "15_minute_residential_data" / "15minute_data_newyork" / "15minute_data_newyork.csv",
}


# ──────────────────────────────────────────────────────────────────────
# ETL Functions
# ──────────────────────────────────────────────────────────────────────

def load_location_data(location: str, target_dataids: list[int]) -> pd.DataFrame:
    """
    Load raw CSV for a location, filtering only for target dataid values.
    Reads in chunks to keep memory usage under control (~400MB total across CSVs).
    """
    csv_path = LOCATION_FILES[location]
    if not csv_path.exists():
        print(f"  WARNING: {csv_path} not found, skipping location '{location}'")
        return pd.DataFrame()

    print(f"  Reading {csv_path.name} (filtering for dataids: {target_dataids})...")
    t0 = time.time()

    # Only load columns we need
    usecols = ["dataid", "local_15min", "grid", "solar"]
    chunks = []
    rows_scanned = 0

    for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=100_000):
        rows_scanned += len(chunk)
        filtered = chunk[chunk["dataid"].isin(target_dataids)]
        if len(filtered) > 0:
            chunks.append(filtered)

    if not chunks:
        print(f"  WARNING: No data found for dataids {target_dataids} in {location}")
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    elapsed = time.time() - t0
    print(f"  Loaded {len(df):,} rows from {rows_scanned:,} scanned ({elapsed:.1f}s)")
    return df


def compute_load_kw(df: pd.DataFrame, has_solar: bool) -> pd.DataFrame:
    """
    Derive true household load from grid and solar columns.

    For solar households:
        load_kw = max(0, grid + solar)
        solar_kw = max(0, solar)

    For non-solar households:
        load_kw = max(0, grid)
        solar_kw = 0.0

    The grid column represents net grid consumption:
        grid = load - solar  (positive = importing, negative = exporting)
    So: load = grid + solar
    """
    df = df.copy()

    if has_solar:
        df["solar"] = df["solar"].fillna(0.0)
        df["load_kw"] = (df["grid"] + df["solar"]).clip(lower=0.0)
        df["solar_kw"] = df["solar"].clip(lower=0.0)
    else:
        df["load_kw"] = df["grid"].clip(lower=0.0)
        df["solar_kw"] = 0.0

    return df


def clean_and_standardize(df: pd.DataFrame, household_id: str, location: str) -> pd.DataFrame:
    """
    Clean a single household's data:
    1. Parse timestamps to datetime (UTC)
    2. Sort by time
    3. Forward-fill then backward-fill small gaps
    4. Drop remaining NaN rows
    5. Standardize to output schema
    """
    df = df.copy()

    # Parse timestamps
    df["timestamp"] = pd.to_datetime(df["local_15min"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Remove duplicate timestamps (keep first)
    df = df.drop_duplicates(subset=["timestamp"], keep="first")

    # Fill small gaps (up to 4 consecutive = 1 hour)
    df["load_kw"] = df["load_kw"].ffill(limit=4).bfill(limit=4)
    df["solar_kw"] = df["solar_kw"].ffill(limit=4).bfill(limit=4)

    # Drop remaining NaN
    before = len(df)
    df = df.dropna(subset=["load_kw", "solar_kw"])
    dropped = before - len(df)
    if dropped > 0:
        print(f"    Dropped {dropped} NaN rows from {household_id}")

    # Final clip (safety)
    df["load_kw"] = df["load_kw"].clip(lower=0.0)
    df["solar_kw"] = df["solar_kw"].clip(lower=0.0)

    # Output schema
    result = pd.DataFrame({
        "timestamp": df["timestamp"],
        "household_id": household_id,
        "load_kw": df["load_kw"].round(4),
        "solar_kw": df["solar_kw"].round(4),
        "dataid": df["dataid"].astype(int),
        "location": location,
    })

    return result.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────
# Main Pipeline
# ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  PECAN STREET ETL PREPROCESSING")
    print("=" * 70)

    # Group selected households by location for efficient loading
    location_groups: dict[str, list[tuple]] = {}
    for dataid, location, has_solar, hh_id in SELECTED_HOUSEHOLDS:
        if location not in location_groups:
            location_groups[location] = []
        location_groups[location].append((dataid, has_solar, hh_id))

    all_profiles = []

    for location, households in location_groups.items():
        print(f"\n--- Processing {location.upper()} ---")
        target_dataids = [h[0] for h in households]

        # Load all target dataids from this location in one pass
        raw_df = load_location_data(location, target_dataids)
        if raw_df.empty:
            continue

        # Process each household
        for dataid, has_solar, hh_id in households:
            print(f"  {hh_id} (dataid={dataid}, solar={'yes' if has_solar else 'no'}):")
            hh_df = raw_df[raw_df["dataid"] == dataid].copy()

            if hh_df.empty:
                print(f"    WARNING: No data found for dataid {dataid}")
                continue

            # Compute load_kw and solar_kw
            hh_df = compute_load_kw(hh_df, has_solar)

            # Clean and standardize
            profile = clean_and_standardize(hh_df, hh_id, location)

            print(f"    Rows: {len(profile):,}")
            print(f"    Date range: {profile['timestamp'].min()} -> {profile['timestamp'].max()}")
            print(f"    load_kw:  mean={profile['load_kw'].mean():.3f}, max={profile['load_kw'].max():.3f}")
            print(f"    solar_kw: mean={profile['solar_kw'].mean():.3f}, max={profile['solar_kw'].max():.3f}")

            all_profiles.append(profile)

    if not all_profiles:
        print("\nERROR: No profiles were processed. Check data paths.")
        sys.exit(1)

    # Combine all households
    combined = pd.concat(all_profiles, ignore_index=True)

    # Summary
    print(f"\n{'='*70}")
    print(f"  OUTPUT SUMMARY")
    print(f"{'='*70}")
    print(f"Total rows: {len(combined):,}")
    print(f"Households: {combined['household_id'].nunique()}")
    print(f"Date range: {combined['timestamp'].min()} -> {combined['timestamp'].max()}")
    print(f"\nPer-household stats:")

    for hh_id in sorted(combined["household_id"].unique()):
        hh = combined[combined["household_id"] == hh_id]
        solar_tag = "*" if hh["solar_kw"].sum() > 0 else " "
        print(
            f"  {solar_tag} {hh_id}: {len(hh):>6,} rows, "
            f"load={hh['load_kw'].mean():.3f} kW avg, "
            f"solar={hh['solar_kw'].mean():.3f} kW avg, "
            f"loc={hh['location'].iloc[0]}"
        )

    # Save to parquet
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "profiles.parquet"
    combined.to_parquet(out_path, index=False, engine="pyarrow")
    file_size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nSaved to: {out_path}")
    print(f"File size: {file_size_mb:.2f} MB")
    print("Done!")


if __name__ == "__main__":
    main()
