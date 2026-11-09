"""
Data exploration script — run this to understand the raw Pecan Street + ISO data.
Outputs a report of available households, solar status, date ranges, data quality.

Usage:
    cd server
    .venv/Scripts/python data/explore_data.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent

LOCATIONS = {
    "austin": {
        "data": DATA_DIR / "15_minute_residential_data" / "15minute_data_austin" / "15minute_data_austin.csv",
        "meta": DATA_DIR / "15_minute_residential_data" / "15minute_data_austin" / "metadata.csv",
    },
    "california": {
        "data": DATA_DIR / "15_minute_residential_data" / "15minute_data_california" / "15minute_data_california.csv",
        "meta": DATA_DIR / "15_minute_residential_data" / "15minute_data_california" / "metadata.csv",
    },
    "newyork": {
        "data": DATA_DIR / "15_minute_residential_data" / "15minute_data_newyork" / "15minute_data_newyork.csv",
        "meta": DATA_DIR / "15_minute_residential_data" / "15minute_data_newyork" / "metadata.csv",
    },
}


def explore_location(name, data_path, meta_path):
    """Explore a single location's data and metadata."""
    print(f"\n{'='*70}")
    print(f"  {name.upper()} DATASET")
    print(f"{'='*70}")

    # --- Metadata ---
    print(f"\n--- Metadata: {meta_path.name} ---")
    meta = pd.read_csv(meta_path)
    print(f"Total households in metadata: {len(meta)}")

    # Solar status
    solar_ids = []
    non_solar_ids = []
    if "pv" in meta.columns:
        solar_mask = meta["pv"].astype(str).str.strip().str.lower() == "yes"
        # Convert dataid to int for cross-referencing with data CSV
        solar_ids_raw = meta.loc[solar_mask, "dataid"].tolist()
        non_solar_ids_raw = meta.loc[~solar_mask, "dataid"].tolist()
        solar_ids = []
        for x in solar_ids_raw:
            try:
                solar_ids.append(int(x))
            except (ValueError, TypeError):
                pass
        non_solar_ids = []
        for x in non_solar_ids_raw:
            try:
                non_solar_ids.append(int(x))
            except (ValueError, TypeError):
                pass
        print(f"Households WITH solar (pv=yes): {len(solar_ids)}")
        print(f"  IDs: {solar_ids[:25]}")
        print(f"Households WITHOUT solar: {len(non_solar_ids)}")
        print(f"  IDs: {non_solar_ids[:25]}")
    else:
        print("WARNING: 'pv' column not found in metadata!")

    # --- Data ---
    print(f"\n--- Data: {data_path.name} ({data_path.stat().st_size / 1024 / 1024:.1f} MB) ---")
    
    # Read in chunks to handle large files
    all_dataids = set()
    total_rows = 0
    first_chunk = None
    
    for i, chunk in enumerate(pd.read_csv(data_path, chunksize=100000)):
        if i == 0:
            first_chunk = chunk
        total_rows += len(chunk)
        all_dataids.update(chunk["dataid"].unique())
    
    all_dataids = sorted(all_dataids)
    print(f"Columns: {list(first_chunk.columns[:20])}")
    print(f"Total columns: {len(first_chunk.columns)}")
    
    # Check key columns
    key_cols = ["dataid", "local_15min", "grid", "solar", "solar2", "leg1v", "leg2v"]
    for col in key_cols:
        if col in first_chunk.columns:
            non_null = first_chunk[col].notna().sum()
            pct = non_null / len(first_chunk) * 100
            print(f"  {col}: {non_null}/{len(first_chunk)} non-null ({pct:.1f}%)")
            if first_chunk[col].dtype in ["float64", "int64"] and non_null > 0:
                vals = first_chunk[col].dropna()
                print(f"    range: [{vals.min():.3f}, {vals.max():.3f}], mean={vals.mean():.3f}")
    
    print(f"\nTotal rows: {total_rows:,}")
    print(f"Unique dataids in data: {len(all_dataids)}")
    print(f"  IDs: {all_dataids}")
    
    # Cross-reference
    data_solar = sorted(set(all_dataids) & set(solar_ids))
    data_non_solar = sorted(set(all_dataids) & set(non_solar_ids))
    print(f"Data households WITH solar: {len(data_solar)} -> {data_solar}")
    print(f"Data households WITHOUT solar: {len(data_non_solar)} -> {data_non_solar}")
    
    # Date range
    timestamps = pd.to_datetime(first_chunk["local_15min"], utc=True)
    print(f"Date range (first chunk): {timestamps.min()} to {timestamps.max()}")
    
    return {
        "name": name,
        "total_rows": total_rows,
        "dataids": all_dataids,
        "solar_ids": data_solar,
        "non_solar_ids": data_non_solar,
    }


def explore_iso():
    """Explore the ISO grid-level data."""
    print(f"\n{'='*70}")
    print(f"  ISO GRID-LEVEL DATA")
    print(f"{'='*70}")
    
    for fname in ["grid_load_iso.csv", "solar_production_iso.csv"]:
        fpath = DATA_DIR / "iso" / fname
        if not fpath.exists():
            print(f"  {fname}: NOT FOUND")
            continue
        
        df = pd.read_csv(fpath)
        print(f"\n--- {fname} ({fpath.stat().st_size / 1024:.1f} KB) ---")
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        ts_col = df.columns[0]
        timestamps = pd.to_datetime(df[ts_col])
        print(f"Date range: {timestamps.min()} to {timestamps.max()}")
        
        val_col = df.columns[1] if len(df.columns) > 1 else None
        if val_col:
            vals = df[val_col].dropna()
            print(f"Values ({val_col}): [{vals.min():.2f}, {vals.max():.2f}], mean={vals.mean():.2f}")
        
        if len(timestamps) > 1:
            diffs = timestamps.diff().dropna()
            print(f"Resolution: {diffs.median()}")


def main():
    print("=" * 70)
    print("  PECAN STREET + ISO DATA EXPLORATION REPORT")
    print("=" * 70)
    
    results = {}
    for name, paths in LOCATIONS.items():
        if paths["data"].exists() and paths["meta"].exists():
            results[name] = explore_location(name, paths["data"], paths["meta"])
        else:
            print(f"\n  {name}: FILES NOT FOUND")
    
    explore_iso()
    
    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    
    all_solar = []
    all_non_solar = []
    for name, res in results.items():
        for did in res["solar_ids"]:
            all_solar.append({"dataid": did, "location": name})
        for did in res["non_solar_ids"]:
            all_non_solar.append({"dataid": did, "location": name})
    
    print(f"\nTotal solar households across all locations: {len(all_solar)}")
    print(f"Total non-solar households across all locations: {len(all_non_solar)}")
    print(f"Need: 6 solar + 7 non-solar = 13 total")
    
    print("\nSolar candidates:")
    for h in all_solar:
        print(f"  dataid={h['dataid']} ({h['location']})")
    
    print("\nNon-solar candidates:")
    for h in all_non_solar:
        print(f"  dataid={h['dataid']} ({h['location']})")


if __name__ == "__main__":
    main()
