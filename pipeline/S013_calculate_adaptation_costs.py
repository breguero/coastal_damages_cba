"""
S013_calculate_adaptation_costs.py
breguero@ucsc.edu  12/18/2025

Calculate total costs of each adaptation measure per CBA study area and DEM
scenario, to be used in the CBA (S030).

Input files (from datadir_damages/<SITE>/adaptation_dimensions/):
    unitary_costs_2025_<SITE>.csv
    seawall_dimensions_<SITE>.csv
    reef_dimensions_<SITE>.csv        (optional)
    dune_dimensions_<SITE>.csv        (optional)
    nourishment_dimensions_<SITE>.csv (optional)

Output:
    all_adapt_costs_<SITE>.csv  — total adapt/maint/recon costs per area, dem, adapt
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from S000_project_config_cosmos_adapt import *
from aux_scripts.damage_calculation_tools import annual_expected_damage_dunes

# ---------------------------------------------------------------------------
# Config — edit these before running
# ---------------------------------------------------------------------------
SITE = 'site001_santacruz2'
#SITE = 'site004_venturanorth2'
#SITE = 'site002_halfmoonbay' 
print(f"SITE={SITE}")

# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------
dirout = project_root_directory / damage_folder_outputs / SITE / '012_damages' / 'adaptation_costs'
dirout.mkdir(parents=True, exist_ok=True)

dirdata_adapt   = datadir_damages / SITE / 'adaptation_dimensions'
dirdata_dune_vl = project_root_directory / damage_folder_outputs / SITE / '012_damages'

print(f"Output:               {dirout}")
print(f"Adaptation data:      {dirdata_adapt}")
print(f"Dune volume loss dir: {dirdata_dune_vl}")

# ---------------------------------------------------------------------------
# Adaptation scenario flags
# ---------------------------------------------------------------------------
adaptation_names  = get_adaptation_names(SITE)
has_dune          = 'dune'         in set(adaptation_names.values())
has_reef          = 'reef'         in set(adaptation_names.values())
has_nourishment   = 'nourishment'  in set(adaptation_names.values())

# ---------------------------------------------------------------------------
# Unitary costs table
# ---------------------------------------------------------------------------
csv_path = dirdata_adapt / f'unitary_costs_2025_{SITE}.csv'
if not csv_path.exists():
    raise FileNotFoundError(f"Unitary costs table not found: {csv_path}")
df_unit = pd.read_csv(csv_path)
print(f"Loaded unitary costs: {len(df_unit):,} rows")


def _unit(adapt_name: str, col: str) -> float:
    """Extract a scalar from the unitary-costs table."""
    rows = df_unit.loc[df_unit['adapt'] == adapt_name, col]
    if rows.empty:
        raise KeyError(f"No row for adapt='{adapt_name}' in unitary costs table.")
    return float(rows.values[0])


# ---------------------------------------------------------------------------
# Helper: ensure 'dem' column uses canonical string format ('dem020', …)
# ---------------------------------------------------------------------------
def _norm_dem(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['dem'] = df['dem'].map(normalize_dem)
    return df


# ---------------------------------------------------------------------------
# SEAWALLS
# ---------------------------------------------------------------------------
seawall_path = dirdata_adapt / f'seawall_dimensions_{SITE}.csv'
if not seawall_path.exists():
    raise FileNotFoundError(f"Seawall dimensions file not found: {seawall_path}")

seawall_dimensions = _norm_dem(pd.read_csv(seawall_path))

# Interpolate unit cost from two reference heights (5 ft and 15 ft)
ref = df_unit.loc[df_unit['adapt'].isin(['seawall_5ft', 'seawall_15ft'])].copy()
ref_x = np.sort(ref['ref_height'].astype(float).values)
ref_y = ref.sort_values('ref_height')['unitary_cost_2025'].astype(float).values

cost_per_unit = np.interp(seawall_dimensions['height'].values, ref_x, ref_y)
seawall_dimensions['cost_per_unit_2025'] = cost_per_unit

fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(seawall_dimensions['height'].values, cost_per_unit, marker='.', linestyle='None')
ax.set(xlabel='Height (m)', ylabel='Cost per unit (2025)',
       title=f'Seawall cost per unit vs height — {SITE}')
ax.grid(True)
plt.tight_layout()
fig_path = dirout / f'seawall_cost_per_unit_{SITE}.png'
plt.savefig(fig_path, dpi=150, bbox_inches='tight')
plt.show()
print(f"Saved seawall cost plot to {fig_path}")

seawall_maintenance_rate = _unit('seawall_5ft', 'maintenance')   # same rate for all heights
seawall_dimensions['adapt_cost'] = seawall_dimensions['cost_per_unit_2025'] * seawall_dimensions['length']
seawall_dimensions['maint_cost'] = seawall_dimensions['adapt_cost'] * seawall_maintenance_rate
seawall_dimensions['recon_cost'] = 0.0

seawall_costs = (
    seawall_dimensions
    .groupby(['cba_study_area', 'dem'], as_index=False)[['length', 'adapt_cost', 'maint_cost', 'recon_cost']]
    .sum()
    .assign(adapt='seawall')
)
print(f"Seawall costs: {len(seawall_costs):,} rows")

# ---------------------------------------------------------------------------
# REEFS
# ---------------------------------------------------------------------------
file_reefs = dirdata_adapt / f'reef_dimensions_{SITE}.csv'
if not has_reef or not file_reefs.exists():
    if has_reef:
        warnings.warn(f"Reef dimensions file not found: {file_reefs}. Reef costs set to zero.")
    reef_costs = pd.DataFrame(columns=['cba_study_area', 'dem', 'adapt_cost', 'maint_cost', 'recon_cost'])
else:
    reef_dimensions = _norm_dem(pd.read_csv(file_reefs))
    reef_dimensions['adapt_cost'] = reef_dimensions['length'] * _unit('reef', 'unitary_cost_2025')
    reef_dimensions['maint_cost'] = reef_dimensions['adapt_cost'] * _unit('reef', 'maintenance')
    reef_dimensions['recon_cost'] = 0.0
    reef_costs = (
        reef_dimensions
        .groupby(['cba_study_area', 'dem'], as_index=False)[['adapt_cost', 'maint_cost', 'recon_cost']]
        .sum()
        .assign(adapt='reef')
    )
    print(f"Reef costs: {len(reef_costs):,} rows")

# ---------------------------------------------------------------------------
# DUNES
# ---------------------------------------------------------------------------
file_dunes = dirdata_adapt / f'dune_dimensions_{SITE}.csv'
if not has_dune:
    print(f"Dune adaptation not configured for {SITE} — skipping.")
    dune_costs = pd.DataFrame(columns=['cba_study_area', 'dem', 'adapt_cost', 'maint_cost', 'recon_cost'])

elif not file_dunes.exists():
    warnings.warn(f"Dune dimensions file not found: {file_dunes}. Dune costs set to zero.")
    dune_costs = pd.DataFrame(columns=['cba_study_area', 'dem', 'adapt_cost', 'maint_cost', 'recon_cost'])

else:
    dune_dimensions = _norm_dem(pd.read_csv(file_dunes))

    # Load expected annual volume-loss ratio (output of S012)
    eav_path = dirdata_dune_vl / f"EAV_dune_volume_{SITE}.csv"
    if not eav_path.exists():
        warnings.warn(f"Dune volume-loss file not found: {eav_path}. Reconstruction costs set to zero.")
        dune_reconstruction = dune_dimensions.copy()
        dune_reconstruction['VDR'] = 0.0
    else:
        dune_loss_data = pd.read_csv(eav_path)
        dune_loss_data = _norm_dem(dune_loss_data)

        # cap at 100 % before converting to ratio
        dune_loss_data['EAV_pct_per_year'] = dune_loss_data['EAV_pct_per_year'].clip(upper=100)

        dune_reconstruction = dune_dimensions.merge(
            dune_loss_data[['cba_study_area', 'dem', 'adapt', 'EAV_pct_per_year']],
            on=['cba_study_area', 'dem', 'adapt'],
            how='left',
        ).rename(columns={'EAV_pct_per_year': 'VDR'})
        dune_reconstruction['VDR'] = dune_reconstruction['VDR'].fillna(0.0) / 100   # % → ratio

    unit_cost_dune  = _unit('dune', 'unitary_cost_2025')
    unit_maint_dune = _unit('dune', 'maintenance')

    dune_rows = []
    for (area, dem_val, adapt), g in dune_reconstruction.groupby(
        ['cba_study_area', 'dem', 'adapt'], observed=True
    ):
        length       = g['dune_length'].unique()[0]
        adapt_cost_i = unit_cost_dune  * length
        maint_cost_i = adapt_cost_i    * unit_maint_dune
        recon_cost_i = (1 + g['VDR'].values[0]) * adapt_cost_i * FACTOR_RECONSTRUCTION_DUNES
        dune_rows.append({
            'cba_study_area': area,
            'dem':            dem_val,
            'adapt':          adapt,
            'adapt_cost':     adapt_cost_i,
            'maint_cost':     maint_cost_i,
            'recon_cost':     recon_cost_i,
            'VDR':            g['VDR'].values[0],
        })

    dune_costs = pd.DataFrame(dune_rows)
    print(f"Dune costs: {len(dune_costs):,} rows")

# ---------------------------------------------------------------------------
# NOURISHMENT
# ---------------------------------------------------------------------------
file_nourishment = dirdata_adapt / f'nourishment_dimensions_{SITE}.csv'
if not file_nourishment.exists():
    warnings.warn(f"Nourishment dimensions file not found: {file_nourishment}. Nourishment costs set to zero.")
    nourishment_costs = pd.DataFrame(columns=['cba_study_area', 'dem', 'adapt_cost', 'maint_cost', 'recon_cost'])
else:
    nourishment_dimensions = _norm_dem(pd.read_csv(file_nourishment))
    nourishment_dimensions['adapt_cost'] = (
        nourishment_dimensions['Vol'] * _unit('nourishment', 'unitary_cost_2025')
    )
    nourishment_dimensions['maint_cost'] = (
        nourishment_dimensions['adapt_cost'] * _unit('nourishment', 'maintenance')
    )
    nourishment_dimensions['recon_cost'] = 0.0
    nourishment_costs = (
        nourishment_dimensions
        .groupby(['cba_study_area', 'dem'], as_index=False)[['adapt_cost', 'maint_cost', 'recon_cost']]
        .sum()
        .assign(adapt='nourishment')
    )
    print(f"Nourishment costs: {len(nourishment_costs):,} rows")

# ---------------------------------------------------------------------------
# Merge all adaptation costs
# ---------------------------------------------------------------------------
_COST_COLS = ['cba_study_area', 'dem', 'adapt', 'adapt_cost', 'maint_cost', 'recon_cost']

cost_frames = {
    'seawall':     seawall_costs,
    'reef':        reef_costs,
    'dune':        dune_costs,
    'nourishment': nourishment_costs,
}

# Validate: all non-empty frames must have the same row count
non_empty_counts = {k: len(v) for k, v in cost_frames.items() if len(v) > 0}
if len(set(non_empty_counts.values())) > 1:
    raise ValueError(
        f"Row count mismatch among non-empty cost DataFrames: {non_empty_counts}"
    )

parts = []
for adapt_name, df in cost_frames.items():
    if df.empty:
        continue
    df = df.copy()
    if 'recon_cost' not in df.columns:
        df['recon_cost'] = 0.0
    # ensure the adapt label column is set correctly
    df['adapt'] = adapt_name
    parts.append(df[_COST_COLS])

all_adapt_costs = (
    pd.concat(parts, ignore_index=True)
    .sort_values(['cba_study_area', 'adapt', 'dem'], ignore_index=True)
)

print(f"Combined adaptation costs: {len(all_adapt_costs):,} rows")
print(all_adapt_costs)


# map years 
# 'dem020' / 'dem050' / 'dem080'  →  year (most common in S022/S030)
all_adapt_costs['year'] = all_adapt_costs['dem'].map(dem_year_map)

out_path = dirout / f'all_adapt_costs_{SITE}.csv'
all_adapt_costs.to_csv(out_path, index=False)
print(f"\nSaved adaptation costs to: {out_path}")
print('\n \n S013 complete.\n \n ')
