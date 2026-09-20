"""Quick check of solar data quality for candidate households."""
import pandas as pd

print("=== SOLAR DATA QUALITY CHECK ===\n")

# California: only 1 solar household (9836) — check if solar column has data
df = pd.read_csv(r'data/15_minute_residential_data/california/15minute_data_california.csv', 
                 usecols=['dataid','grid','solar'])
hh = df[df['dataid']==9836]
solar_nn = hh['solar'].notna().sum()
solar_mean = hh['solar'].dropna().mean() if solar_nn > 0 else 0
print(f"California 9836: {len(hh)} rows, solar_non_null={solar_nn}, solar_mean={solar_mean:.3f} kW")
print()

# Austin: check top solar households
print("--- Austin Solar Households ---")
df2 = pd.read_csv(r'data/15_minute_residential_data/austin/15minute_data_austin.csv', 
                  usecols=['dataid','grid','solar'])
for did in [661, 2335, 2361, 3039, 3538, 4031, 4767, 7536, 9160]:
    hh = df2[df2['dataid']==did]
    solar_nn = hh['solar'].notna().sum()
    solar_mean = hh['solar'].dropna().mean() if solar_nn > 0 else 0
    grid_nn = hh['grid'].notna().sum()
    grid_mean = hh['grid'].dropna().mean() if grid_nn > 0 else 0
    print(f"  {did}: {len(hh)} rows, grid_mean={grid_mean:.3f}kW(nn={grid_nn}), solar_mean={solar_mean:.3f}kW(nn={solar_nn})")

# Austin: check non-solar households
print("\n--- Austin Non-Solar Households ---")
for did in [5746, 7901, 7951, 8386, 8565, 9922]:
    hh = df2[df2['dataid']==did]
    grid_nn = hh['grid'].notna().sum()
    grid_mean = hh['grid'].dropna().mean() if grid_nn > 0 else 0
    print(f"  {did}: {len(hh)} rows, grid_mean={grid_mean:.3f}kW(nn={grid_nn})")

# New York: check solar households
print("\n--- New York Solar Households ---")
df3 = pd.read_csv(r'data/15_minute_residential_data/newyork/15minute_data_newyork.csv', 
                  usecols=['dataid','grid','solar'])
for did in [27, 142, 387, 950, 1222, 3000, 5058, 5587]:
    hh = df3[df3['dataid']==did]
    solar_nn = hh['solar'].notna().sum()
    solar_mean = hh['solar'].dropna().mean() if solar_nn > 0 else 0
    grid_nn = hh['grid'].notna().sum()
    grid_mean = hh['grid'].dropna().mean() if grid_nn > 0 else 0
    print(f"  {did}: {len(hh)} rows, grid_mean={grid_mean:.3f}kW(nn={grid_nn}), solar_mean={solar_mean:.3f}kW(nn={solar_nn})")

# New York: check non-solar households
print("\n--- New York Non-Solar Households ---")
for did in [558, 2358, 4550, 9053]:
    hh = df3[df3['dataid']==did]
    grid_nn = hh['grid'].notna().sum()
    grid_mean = hh['grid'].dropna().mean() if grid_nn > 0 else 0
    print(f"  {did}: {len(hh)} rows, grid_mean={grid_mean:.3f}kW(nn={grid_nn})")
