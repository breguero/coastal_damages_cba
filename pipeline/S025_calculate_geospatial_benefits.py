"""
S025_calculate_geospatial_benefits.py
breguero@ucsc.edu

For each (DEM, RP, adaptation) flood map, compute per-building benefits as:
    benefit = tot_cost(no_adaptation) - tot_cost(adaptation)

Reads:   *_damages_and_roads_indirects.gpkg  (output of S021)
Writes:  *_benefits.gpkg                     (one file per non-baseline map)
         BENEFIT_SUMMARY_<SITE>.csv           (total benefits per map)
"""

import re
from pathlib import Path

import pandas as pd
import geopandas as gpd

from S000_project_config_cosmos_adapt import *

# ---------------------------------------------------------------------------
# Config — edit these before running
# ---------------------------------------------------------------------------
SITE = 'site001_santacruz2'
MODE = '002'   # 001: hydro only  002: morphodynamic  003: hydro/no DEM  004: morpho/no DEM

print(f"SITE={SITE}  MODE={MODE}")

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
dirdata = (
    project_root_directory / damage_folder_outputs / SITE
    / '012_damages' / 'indirect_damages' / f'flood_map_{MODE}'
)
input_files = sorted(dirdata.glob('*damages*.gpkg'))

if not input_files:
    raise FileNotFoundError(f"No damage gpkg files found in: {dirdata}")

# ---------------------------------------------------------------------------
# Process each adaptation scenario file
# ---------------------------------------------------------------------------
summary_rows = []

for adaptation_file in input_files:
    filename = adaptation_file.stem

    # skip the no-adaptation baseline; it is used as the reference, not a target
    if 'adapt000' in filename:
        continue

    # derive the matching no-adaptation file name
    no_adapt_name = re.sub(r'adapt\d{3}', 'adapt000', filename)
    no_adapt_path = dirdata / f'{no_adapt_name}.gpkg'

    if not no_adapt_path.exists():
        print(f"WARNING: no-adaptation baseline not found for '{filename}' — skipping.")
        continue

    damages_adapt    = gpd.read_file(adaptation_file)
    damages_no_adapt = gpd.read_file(no_adapt_path)

    # vectorised benefit calculation via merge (replaces slow row-by-row loop)
    adapt_costs = (
        damages_adapt[['fid_building', 'tot_cost']]
        .rename(columns={'tot_cost': 'tot_cost_adapt'})
    )
    damages_no_adapt = damages_no_adapt.merge(adapt_costs, on='fid_building', how='left')

    # buildings flooded under no_adapt but absent in adapt → full avoided damage
    damages_no_adapt['tot_cost_adapt'] = damages_no_adapt['tot_cost_adapt'].fillna(0.0)
    damages_no_adapt['benefits'] = damages_no_adapt['tot_cost'] - damages_no_adapt['tot_cost_adapt']
    damages_no_adapt = damages_no_adapt.drop(columns=['tot_cost_adapt'])

    total_benefits = damages_no_adapt['benefits'].sum()
    print(f"{adaptation_file.name}: total benefits = ${total_benefits:,.0f}")

    # write per-building benefits gpkg
    fileout = dirdata / adaptation_file.name.replace('damages_and_roads_indirects', 'benefits')
    damages_no_adapt.to_file(fileout, driver='GPKG')

    summary_rows.append({
        'filename':       adaptation_file.name,
        'total_benefits': total_benefits,
        'n_buildings':    len(damages_no_adapt),
    })

# ---------------------------------------------------------------------------
# Export summary table
# ---------------------------------------------------------------------------
dirout = (
    project_root_directory / damage_folder_outputs / SITE
    / '012_damages' / 'aed_cba_results' / f'flood_map_{MODE}'
)
dirout.mkdir(parents=True, exist_ok=True)

summary_df   = pd.DataFrame(summary_rows)
summary_path = dirout / f"BENEFIT_SUMMARY_{SITE}.csv"
summary_df.to_csv(summary_path, index=False)
print(f"\nBenefit summary written to: {summary_path}")
print('All benefits calculated and saved.')
