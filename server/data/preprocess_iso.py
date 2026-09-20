"""
ISO Grid-Level Data Preprocessing.

Reads raw ISO grid load and solar production CSVs (5-minute resolution),
resamples to 15-minute intervals, and saves as parquet for the simulation.

Usage:
    cd server
    .venv\\Scripts\\python.exe data\\preprocess_iso.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

DATA_DIR = Path(__file__).parent
ISO_DIR = DATA_DIR / "iso"
OUTPUT_DIR = DATA_DIR / "processed"


def process_iso_file(csv_path: Path, value_col_rename: str) -> pd.DataFrame:
    """
    Load an ISO CSV, parse timestamps, resample from 5-min to 15-min intervals.

    Args:
        csv_path: Path to the ISO CSV file.
        value_col_rename: What to rename the value column to (e.g., 'grid_load_mw').

    Returns:
        DataFrame with columns: timestamp, <value_col_rename>
    """
    print(f"  Reading {csv_path.name}...")
    df = pd.read_csv(csv_path)

    # The first column is always the timestamp ('DateTime')
    ts_col = df.columns[0]
    val_col = df.columns[1]

    df["timestamp"] = pd.to_datetime(df[ts_col], utc=True)
    df[value_col_rename] = df[val_col].astype(float)

    # Sort by time and drop original columns
    df = df[["timestamp", value_col_rename]].sort_values("timestamp").reset_index(drop=True)

    # Report raw stats
    print(f"    Raw: {len(df):,} rows, {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"    Resolution: {df['timestamp'].diff().median()}")
    print(f"    {value_col_rename}: [{df[value_col_rename].min():.2f}, {df[value_col_rename].max():.2f}], mean={df[value_col_rename].mean():.2f}")

    # Resample from 5-min to 15-min intervals (mean aggregation)
    df = df.set_index("timestamp")
    df_15min = df.resample("15min").mean()

    # Drop any intervals with NaN (incomplete 5-min windows at edges)
    df_15min = df_15min.dropna()
    df_15min = df_15min.reset_index()

    print(f"    Resampled: {len(df_15min):,} rows at 15-min intervals")

    return df_15min


def main():
    print("=" * 70)
    print("  ISO GRID DATA PREPROCESSING")
    print("=" * 70)

    grid_load_path = ISO_DIR / "grid_load_iso.csv"
    solar_prod_path = ISO_DIR / "solar_production_iso.csv"

    if not grid_load_path.exists():
        print(f"ERROR: {grid_load_path} not found")
        sys.exit(1)
    if not solar_prod_path.exists():
        print(f"ERROR: {solar_prod_path} not found")
        sys.exit(1)

    # Process grid load
    print("\n--- Grid Load ---")
    grid_df = process_iso_file(grid_load_path, "grid_load_mw")

    # Process solar production
    print("\n--- Solar Production ---")
    solar_df = process_iso_file(solar_prod_path, "solar_production_mw")

    # Merge on timestamp
    print("\n--- Merging ---")
    merged = pd.merge(grid_df, solar_df, on="timestamp", how="inner")
    print(f"  Merged rows: {len(merged):,}")
    print(f"  Date range: {merged['timestamp'].min()} -> {merged['timestamp'].max()}")

    # Add derived columns useful for the simulation
    # Net load (grid load minus solar — what conventional generation must supply)
    merged["net_load_mw"] = merged["grid_load_mw"] - merged["solar_production_mw"]

    # Solar penetration ratio (what fraction of load is met by solar)
    merged["solar_penetration"] = (
        merged["solar_production_mw"] / merged["grid_load_mw"].clip(lower=0.01)
    ).clip(lower=0.0, upper=1.0)

    print(f"\n  Grid Load (MW):       mean={merged['grid_load_mw'].mean():.1f}, "
          f"peak={merged['grid_load_mw'].max():.1f}")
    print(f"  Solar Prod (MW):      mean={merged['solar_production_mw'].mean():.1f}, "
          f"peak={merged['solar_production_mw'].max():.1f}")
    print(f"  Net Load (MW):        mean={merged['net_load_mw'].mean():.1f}")
    print(f"  Solar Penetration:    mean={merged['solar_penetration'].mean():.2%}")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "iso_profiles.parquet"
    merged.to_parquet(out_path, index=False, engine="pyarrow")
    file_size_kb = out_path.stat().st_size / 1024
    print(f"\n  Saved to: {out_path}")
    print(f"  File size: {file_size_kb:.1f} KB")
    print("  Done!")


if __name__ == "__main__":
    main()
