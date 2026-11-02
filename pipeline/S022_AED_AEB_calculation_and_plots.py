#################################################################################################################
#   S022_AED_calculation_and_plots.py
#   breguero@ucsc.edu 01/06/2026
#
#   Script description:
#   calculate AED by loading the damages files for each rp, dem, adapt scenario
#   sums by cba_study_area and then calculates AED
#   creates plots of AED results
#
#   input: e.g. site001_dem050_rp100_adapt031_mode001_hmax_damages_indirects.csv
#   output: 
#       Tables with all the total sums from all damages for each rp, dem, adapt scenario
#           e.g. site001_santacruz_all_damages.csv
#       AED tables for each adaptation scenario - csv files
#           e.g. AED_site001_santacruz_reef.csv
#       AEB tables for each adaptation scenario - csv files 
# ###############################################################################################################

import pandas as pd
from aux_scripts.damage_calculation_tools import *
import numpy as np
import os
from itertools import product, cycle, islice
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import plotly.graph_objects as go
from matplotlib.ticker import FuncFormatter

from S000_project_config_cosmos_adapt import *
from pathlib import Path

plt.rcParams.update({
    'font.size': 16,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans', 'Liberation Sans']
})

import geopandas as gpd

from aux_scripts.plot_utils import (
    style_matplotlib_axes,
    damage_formatter,
    plot_matplotlib_adaptation,
    format_plotly_axes,
    add_plotly_rp_vlines,
    get_plotly_annotation_offset,
    add_plotly_year_annotations,
    add_plotly_adaptation_annotations,
    ADAPTATION_COLORS,
    RISK_DAMAGE_COLORS,
)

# ------------------------- Config -------------------------
##These are the four sites we want to run in general for Cosmos Adapts:
    # SITE = 'site001_santacruz' #site_001, site_002? site is the parent dir so you don't need {site}_NSI folder***
    # SITE = 'site002_halfmoonbay' 
    # SITE = 'site003_venturanorth'
#SITE = 'site001_santacruz2'
#SITE = 'site001_santacruz' #for testing only, comment out when running from terminal
SITE = RUN_SITE  # set with COSMOS_SITE or run_pipeline.py --site
#SITE = 'site003_venturanorth'
#SITE = 'site004_venturanorth2'
# Mode (runs)  	
#   001: hydrodynamic only / DEM = 1, morpho = 0 
#   002: morphodynamic update enabled / DEM = 1, morpho = 1 
#   003: hydro without DEM change (bathy use dem020) / DEM = 0, morpho = 0 
#   004: morpho without DEM change (bathy use dem020) / DEM = 0, morpho = 1 	
MODE = RUN_MODE  # set with COSMOS_MODE or run_pipeline.py --mode (see 000_scenario_convention_dictionary)
# ----------------------------------------------------

# ------------------------- DUNE config  ----------------------------------------------------
ACTIVATE_DUNE_RECONSTRUCTION = False
print(f"ACTIVATE_DUNE_RECONSTRUCTION = {ACTIVATE_DUNE_RECONSTRUCTION}")
if ACTIVATE_DUNE_RECONSTRUCTION:
    dunemode = 'dune1'  
else:
    dunemode = 'dune0'  
# -------------------------- DISCOUNTING --------------
DISCOUNTING = RUN_DISCOUNT_RATE  # set with COSMOS_DISCOUNT_RATE (default 0.03)
print(f"Using discount rate: {DISCOUNTING*100:.2f}%" )
# --------------------------- CHECK REGION --------------
if SITE not in ['site001_santacruz2','site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', 'site004_venturanorth2']:
    raise ValueError(f"region_name {SITE} not recognized. Please choose from 'site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', or 'site004_venturanorth2'.")    
# ----------------------------------------------------

# DIRECTORIES AND FILES
dirout = output_root / SITE / '012_damages' / 'aed_cba_results' / f'flood_map_{MODE}' 
if not dirout.exists():
    dirout.mkdir(parents=True, exist_ok=True) 
print(f"Output directory: {dirout}")

dirdata_flood_damages= output_root / SITE / '012_damages' / 'indirect_damages' / f'flood_map_{MODE}'
print(f"Flood maps directory: {dirdata_flood_damages}")

# load areas 
clipped_buildings_directory = output_root / SITE / '011_Joined_NSI_to_Buildings' 
#buildings_file = datadir_damages / SITE / 'exposure' / 'buildings_with_cba_study_areas.gpkg'
buildings_file = clipped_buildings_directory / 'buildings_with_cba_study_areas.gpkg' 
ALL_DAMAGESs = gpd.read_file(buildings_file)['cba_study_area'].unique()
print(f"Reference areas ({len(ALL_DAMAGESs)}): {ALL_DAMAGESs}")

# --------------------------------------------------------------
#   AED CALCULATION
#   read processed damages for each RP and calculate AED 
# --------------------------------------------------------------

# loop over adaptation scenarios, rp, dem years
adaptation_names = get_adaptation_names(SITE)
if not adaptation_names:
    raise ValueError(f"No adaptation scenarios found for SITE={SITE}. adaptation_names is empty. Check configuration or input data.")

site_number = SITE.split('_')[0] # extract site number from region name, e.g. site001

ALL_DAMAGES = [] 
missing_files = []
for adaptkey in adaptation_names:
    print(f"{adaptkey} -> {adaptation_names[adaptkey]}")
    # loop over return periods and dem years
    for rp, dem in product(RP_list, DEM_list):
        # load damages (indirects has both direct and indirect damages summed together, so we don't need to load direct damages separately)
        filename = f"{site_number}_{dem}_rp{rp:03d}_adapt{adaptkey}_mode{MODE}_hmax_damages_and_roads_indirects.csv"
        full_path = os.path.join(dirdata_flood_damages, filename)
        if not os.path.exists(full_path):
            print(f"MISSING: {filename}")
            missing_files.append(filename)
            continue
        damages_csv = pd.read_csv(full_path)
        
        print(f"Loaded damages data from: {filename} (shape={damages_csv.shape})")
        print(damages_csv.head())

        damages_df = damages_csv.groupby('cba_study_area')[['tot_cost', 'population', 'building_count']].sum().reset_index()
        
        # ensure all areas present, filling only numeric outputs with 0
        damages_df = damages_df.set_index('cba_study_area') \
                       .reindex(ALL_DAMAGESs) \
                       .reset_index()
        damages_df[['tot_cost', 'population', 'building_count']] = damages_df[['tot_cost', 'population', 'building_count']].fillna(0)
        damages_df['rp'] = rp
        damages_df['dem'] = dem
        damages_df['adapt'] = adaptation_names[adaptkey]
        damages_df['tot_cost'] = damages_df['tot_cost'].round(1)
        
        ALL_DAMAGES.append(damages_df) # return periods 
        
# concatenate all damages for the current adaptation scenario
ALLD_BY_CBA_STUDY_AREA = pd.concat(ALL_DAMAGES , ignore_index=True)
print(ALLD_BY_CBA_STUDY_AREA)

ALLD_BY_CBA_STUDY_AREA['year'] = ALLD_BY_CBA_STUDY_AREA['dem'].map(dem_year_map)

# export missing files list
if missing_files:
    # raise an error listing missing files instead of continuing
    raise FileNotFoundError(f"Missing input files detected: {missing_files}")
else:
    print("No missing files detected.")
    
# export to csv
ALLD_BY_CBA_STUDY_AREA.to_csv(dirout / f"ALLD_BY_CBA_STUDY_AREA_{SITE}.csv", index=False)  

# --------------------------------------------------------------------------------------------
# sum for all the cba_study_areas to get total damages for each rp, dem, adapt scenario and export to csv
# --------------------------------------------------------------------------------------------
ALL_DAMAGES = ALLD_BY_CBA_STUDY_AREA.copy()
ALL_DAMAGES = (
    ALL_DAMAGES.groupby(['rp', 'dem', 'adapt'], as_index=False)[['tot_cost', 'population', 'building_count']]
    .sum()
    .rename(columns={'tot_cost': 'total_damage'})
)
ALL_DAMAGES['year'] = ALL_DAMAGES['dem'].map(dem_year_map)
ALL_DAMAGES.to_csv(dirout / f"ALLD_totals_{SITE}.csv", index=False)

# -----------------------------------------------------------------------------------------------------
# AED calculation 
AED_RESULTS = [] 
for study_area in ALLD_BY_CBA_STUDY_AREA['cba_study_area'].unique():
    for dem_val in ALLD_BY_CBA_STUDY_AREA['dem'].unique():
        print(dem_val) 
        damages_area = ALLD_BY_CBA_STUDY_AREA[(ALLD_BY_CBA_STUDY_AREA['cba_study_area'] == study_area) & 
                                           (ALLD_BY_CBA_STUDY_AREA['dem'] == dem_val)]
        
        # subset for each adaptation scenario in this study area and dem
        for adapt in damages_area['adapt'].unique():
            da_adapt = damages_area[damages_area['adapt'] == adapt].copy()

            if not da_adapt.empty:
                # simple summary: total damage for this study area, adaptation, and dem
                return_periods = da_adapt['rp'].values

                # losses 
                values = da_adapt['tot_cost'].values 
                aed = annual_expected_damage_numint(values, return_periods) # Set figures to 0 to avoid plotting

                #aed_population computation:
                values_population = da_adapt['population'].values
                aed_population = annual_expected_damage_numint(values_population, return_periods)

                #aed_number_of_buildings computation:
                values_building_count = da_adapt['building_count'].values
                aed_building_count = annual_expected_damage_numint(values_building_count, return_periods)
                
                # TO DO - here fit pdf for EAV calculation and compare with numerical integration 
                # aed = annual_expected_damage_fit(values, return_periods)

                # TO DO - Value at risk calculation 
                #var = value_at_risk_calc(values, return_periods)

                if aed < 0: aed = 0
                if aed_population < 0: aed_population = 0
                if aed_building_count < 0: aed_building_count = 0
            else: 
                aed = np.nan 
                aed_population = np.nan 
                aed_building_count = np.nan 
                
            AED_RESULTS.append({
                    'cba_study_area': study_area,
                    'dem': dem_val,
                    'adapt': adapt,
                    'aed': aed,
                    'aed_population': aed_population,
                    'aed_building_count': aed_building_count
                })
            
# AED_RESULTS was built as a list of dicts; convert to a DataFrame instead of pd.concat
AED_RESULTS = pd.DataFrame(AED_RESULTS)
print(AED_RESULTS)

AED_RESULTS.to_csv(dirout  / f"AED_byarea_{SITE}.csv", index=False) 
# Aggregate across all cba_study_area and append total sums
AED_RESULTS_SUM = AED_RESULTS.groupby(['dem', 'adapt'], as_index=False)[['aed', 'aed_population', 'aed_building_count']].sum()

# export aed_df to csv
AED_RESULTS_SUM.to_csv( dirout  / f"AED_totals_{SITE}.csv", index=False) # CHECK THIS 
# -----------------------------------------------------------------------------------------------------

# -----------------------------------------------------------------------------------------------------
# AEB CALCULATION
#
# Approach: compute benefit(rp) = damage_no_adapt(rp) - damage_adapt(rp) for every return period,
# then integrate those per-RP differences over exceedance probabilities (same trapezoidal rule used
# for AED). This is methodologically equivalent to AED_no_adapt - AED_adapt but produces an
# intermediate per-RP benefit table that can be directly compared with S025 geospatial benefits.
# -----------------------------------------------------------------------------------------------------

AEB_RESULTS  = []
BENEFIT_BY_RP = []  # per-RP benefit differences before integration

for study_area in ALLD_BY_CBA_STUDY_AREA['cba_study_area'].unique():
    for dem_val in ALLD_BY_CBA_STUDY_AREA['dem'].unique():

        area_dem = ALLD_BY_CBA_STUDY_AREA[
            (ALLD_BY_CBA_STUDY_AREA['cba_study_area'] == study_area) &
            (ALLD_BY_CBA_STUDY_AREA['dem'] == dem_val)
        ]

        # no-adaptation baseline indexed by return period
        no_adapt_by_rp = (
            area_dem[area_dem['adapt'] == 'no_adaptation']
            .set_index('rp')[['tot_cost', 'population', 'building_count']]
        )
        if no_adapt_by_rp.empty:
            print(f"WARNING: no no_adaptation baseline for {study_area}, {dem_val} — skipping.")
            continue

        # pull AED reference values for this area/dem from AED_RESULTS
        aed_ref = (
            AED_RESULTS[
                (AED_RESULTS['cba_study_area'] == study_area) &
                (AED_RESULTS['dem'] == dem_val)
            ]
            .set_index('adapt')
        )
        aed0_row  = aed_ref.loc['no_adaptation'] if 'no_adaptation' in aed_ref.index else None

        for adapt in area_dem['adapt'].unique():
            adapt_by_rp = (
                area_dem[area_dem['adapt'] == adapt]
                .set_index('rp')[['tot_cost', 'population', 'building_count']]
            )

            # align on return periods present in both scenarios
            common_rps = sorted(set(no_adapt_by_rp.index) & set(adapt_by_rp.index))
            if not common_rps:
                print(f"WARNING: no common RPs for {study_area}, {dem_val}, {adapt} — skipping.")
                continue

            # per-RP benefit differences
            for rp in common_rps:
                b      = no_adapt_by_rp.loc[rp, 'tot_cost']      - adapt_by_rp.loc[rp, 'tot_cost']
                b_pop  = no_adapt_by_rp.loc[rp, 'population']    - adapt_by_rp.loc[rp, 'population']
                b_bld  = no_adapt_by_rp.loc[rp, 'building_count']- adapt_by_rp.loc[rp, 'building_count']
                BENEFIT_BY_RP.append({
                    'cba_study_area':         study_area,
                    'dem':                    dem_val,
                    'adapt':                  adapt,
                    'rp':                     rp,
                    'benefit':                b,
                    'damage_no_adapt':        no_adapt_by_rp.loc[rp, 'tot_cost'],
                    'damage_adapt':           adapt_by_rp.loc[rp, 'tot_cost'],
                    'benefit_population':     b_pop,
                    'benefit_building_count': b_bld,
                })

            # integrate per-RP benefits over exceedance probabilities → AEB
            benefit_vals = [
                no_adapt_by_rp.loc[rp, 'tot_cost']       - adapt_by_rp.loc[rp, 'tot_cost']
                for rp in common_rps
            ]
            benefit_pop_vals = [
                no_adapt_by_rp.loc[rp, 'population']     - adapt_by_rp.loc[rp, 'population']
                for rp in common_rps
            ]
            benefit_bld_vals = [
                no_adapt_by_rp.loc[rp, 'building_count'] - adapt_by_rp.loc[rp, 'building_count']
                for rp in common_rps
            ]

            aeb       = max(annual_expected_damage_numint(benefit_vals,     common_rps), 0)
            aeb_pop   = max(annual_expected_damage_numint(benefit_pop_vals,  common_rps), 0)
            aeb_build = max(annual_expected_damage_numint(benefit_bld_vals,  common_rps), 0)

            # AED reference values (for context columns and aeb2 calculation)
            adapt_aed_row = aed_ref.loc[adapt] if adapt in aed_ref.index else None
            aed       = adapt_aed_row['aed']               if adapt_aed_row is not None else np.nan
            aed_pop   = adapt_aed_row['aed_population']    if adapt_aed_row is not None else np.nan
            aed_build = adapt_aed_row['aed_building_count']if adapt_aed_row is not None else np.nan
            aed0      = aed0_row['aed']                    if aed0_row is not None else np.nan
            aed0_pop  = aed0_row['aed_population']         if aed0_row is not None else np.nan
            aed0_bld  = aed0_row['aed_building_count']     if aed0_row is not None else np.nan

            # aeb2: AED difference method (AED_no_adapt - AED_adapt)
            aeb2       = max(aed0      - aed,       0) if not (np.isnan(aed0)     or np.isnan(aed))       else np.nan
            aeb2_pop   = max(aed0_pop  - aed_pop,   0) if not (np.isnan(aed0_pop) or np.isnan(aed_pop))   else np.nan
            aeb2_build = max(aed0_bld  - aed_build, 0) if not (np.isnan(aed0_bld) or np.isnan(aed_build)) else np.nan

            AEB_RESULTS.append({
                'cba_study_area':               study_area,
                'dem':                          dem_val,
                'adapt':                        adapt,
                'aeb':                          aeb,
                'aeb2':                         aeb2,
                'aed':                          aed,
                'aed_wo_adapt':                 aed0,
                'aeb_population':               aeb_pop,
                'aeb2_population':              aeb2_pop,
                'aed_population':               aed_pop,
                'aed_population_wo_adapt':      aed0_pop,
                'aeb_building_count':           aeb_build,
                'aeb2_building_count':          aeb2_build,
                'aed_building_count':           aed_build,
                'aed_building_count_wo_adapt':  aed0_bld,
            })

# --- per-RP benefit table ---
BENEFIT_BY_RP = pd.DataFrame(BENEFIT_BY_RP)
BENEFIT_BY_RP['year'] = BENEFIT_BY_RP['dem'].map(dem_year_map)
BENEFIT_BY_RP.to_csv(dirout / f"BENEFIT_BY_RP_byarea_{SITE}.csv", index=False)
print(BENEFIT_BY_RP)

# --- AEB table ---
AEB_RESULTS = pd.DataFrame(AEB_RESULTS)
AEB_RESULTS['year'] = AEB_RESULTS['dem'].map(dem_year_map)
AEB_RESULTS.to_csv(dirout / f"AEB_byarea_{SITE}.csv", index=False)
print(AEB_RESULTS)

# Aggregate across all cba_study_areas
# AEB_RESULTS_SUM = AEB_RESULTS.groupby(['dem', 'adapt'], as_index=False)[[
#     'aeb', 'aeb2', 'aed', 'aed_wo_adapt',
#     'aeb_population', 'aeb2_population', 'aed_population', 'aed_population_wo_adapt',
#     'aeb_building_count', 'aeb2_building_count', 'aed_building_count', 'aed_building_count_wo_adapt',
# ]].sum()
AEB_RESULTS_SUM = AEB_RESULTS.groupby(['dem', 'adapt'], as_index=False)[[
    'aeb', 'aed', 'aed_wo_adapt',
    'aeb_population', 'aed_population', 'aed_population_wo_adapt',
    'aeb_building_count', 'aed_building_count', 'aed_building_count_wo_adapt',
]].sum()
AEB_RESULTS_SUM['year'] = AEB_RESULTS_SUM['dem'].map(dem_year_map)
AEB_RESULTS_SUM.to_csv(dirout / f"AEB_totals_{SITE}.csv", index=False)
# -----------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------
# EXPORT SPATIAL RESULTS FOR EACH CBA STUDY UNIT FOR THE NO ADAPTATION SCENARIO (to be used for mapping in ArcGIS)
# --------------------------------------------------------------------------------------------
no_adapt_spatial = ALLD_BY_CBA_STUDY_AREA[ALLD_BY_CBA_STUDY_AREA['adapt'] == 'no_adaptation'].copy()
no_adapt_spatial = no_adapt_spatial[no_adapt_spatial['rp'] == 100].copy() # subset by rp 
no_adapt_spatial = no_adapt_spatial.drop(columns=['population', 'building_count', 'adapt'])

cba_areas_file_path = project_root_directory / datadir_damages / SITE / 'cba_study_areas' / 'cba_study_area.gpkg'
cba_areas = gpd.read_file(cba_areas_file_path)

# Pivot no_adapt_spatial to add a column for each dem value with tot_cost
dem_costs = no_adapt_spatial.pivot_table(
    index='cba_study_area', 
    columns='dem', 
    values='tot_cost', 
    aggfunc='first'
)
dem_costs = dem_costs.reset_index()

# Merge dem costs into cba_areas
cba_areas = cba_areas.merge(dem_costs, left_on='cba_study_area', right_on='cba_study_area', how='left')
cba_areas.plot(column='dem020') 

# Export to file
output_file = dirout / f"no_adaptation_rp100_damages_by_cba_study_area_{SITE}.gpkg"
cba_areas.to_file(output_file, driver='GPKG')
print(f"Exported no adaptation spatial damage results to: {output_file}")


# ###############################################################################################################
#  FIGURES 
# ###############################################################################################################
ymin, ymax = ALL_DAMAGES['total_damage'].min(), ALL_DAMAGES['total_damage'].max() + 10_000_000

# ###############################################################################################################
# Define colors for matplotlib

# Define colors for plotly (since cm.get_cmap returns matplotlib colors, convert to hex)
plotly_colors = [cm.tab10(i / len(adaptation_names)) for i in range(len(adaptation_names))]
plotly_colors = [f'rgb({int(c[0]*255)},{int(c[1]*255)},{int(c[2]*255)})' for c in plotly_colors]

adaptation_colors = ADAPTATION_COLORS
risk_damage_colors = RISK_DAMAGE_COLORS

# ###############################################################################################################
# figures CHANGES IN RISK 
# ###############################################################################################################

#ALL_DAMAGES_YEAR = ALL_DAMAGES[ALL_DAMAGES['adapt'] == 'no_adaptation'].groupby(['rp', 'year'])['total_damage'].sum().reset_index()
ALL_DAMAGES_BASELINE = ALL_DAMAGES[ALL_DAMAGES['adapt'] == 'no_adaptation']

# #####################################
# Matplotlib plot - total study area
# #####################################
fig, ax = plt.subplots(figsize=(10, 6))
colors = (['red','blue', 'black', ] * ((len(ALL_DAMAGES_BASELINE['year'].unique()) + 2) // 3))[:len(ALL_DAMAGES_BASELINE['year'].unique())]

#           2085 / 2055 / 2025
base_year = 2025
base_data = ALL_DAMAGES_BASELINE[ALL_DAMAGES_BASELINE['year'] == base_year].set_index('rp')['total_damage']

for idx, year in enumerate(sorted(ALL_DAMAGES_BASELINE['year'].unique(), reverse=True)):
    year_data = ALL_DAMAGES_BASELINE[ALL_DAMAGES_BASELINE['year'] == year]

    ax.plot(year_data['rp'], year_data['total_damage'], marker='o', label=str(year), color=colors[idx])
    if year != base_year:
        for _, row in year_data.iterrows():
            rp, damage = row['rp'], row['total_damage']
            base_damage = base_data.get(rp, None)
            if base_damage and base_damage > 0:
                increase_pct = 100 * (damage - base_damage) / base_damage
                ax.annotate(f"{increase_pct:.1f}%", (rp, damage), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=16, color=colors[idx])

ax.set_xlabel('Return Period [years]')
ax.set_ylabel('Total Damage [US$]')
ax.set_title('Total Damage vs Return Period by Year')
ax.legend(title='Year')
ax.set_xticks([5, 20, 50, 100]); ax.set_xticklabels([5, 20, 50, 100])

# Format y-axis as millions
ax.yaxis.set_major_formatter(
    FuncFormatter(lambda x, pos: f'{x/1e6:.0f}M')
)

# Disable scientific notation
#ax.ticklabel_format(axis='y', style='plain')

# Hide offset text (e.g., ×10^7)
#ax.yaxis.get_offset_text().set_visible(False)
#ax.grid(axis='y', linestyle='--', alpha=0.7)
#ax.grid(axis='x', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.savefig(dirout / f"total_damage_by_year_{SITE}_matplotlib.png")
plt.savefig(dirout / f"total_damage_by_year_{SITE}_matplotlib.pdf")
plt.show()

# #####################################
# Plotly version - Total study area
# #####################################

fig = go.Figure()
base_year = 2025
base_data = ALL_DAMAGES_BASELINE[ALL_DAMAGES_BASELINE['year'] == base_year].set_index('rp')['total_damage']
for idx, year in enumerate(sorted(ALL_DAMAGES_BASELINE['year'].unique(), reverse=True)):
    year_data = ALL_DAMAGES_BASELINE[ALL_DAMAGES_BASELINE['year'] == year]

    color = risk_damage_colors.get(str(year), plotly_colors[idx % len(plotly_colors)])
    fig.add_trace(go.Scatter(x=year_data['rp'], y=year_data['total_damage'], mode='lines+markers', name=str(year), line=dict(color=color)))
    if year != base_year:
        add_plotly_year_annotations(fig, year_data, base_data, color, year, site=SITE)

#add_plotly_rp_vlines(fig, ALL_DAMAGES['rp'].unique(), ymin, ymax)
fig.update_layout(
    title='Total Damage vs Return Period by Year',
    xaxis_title='Return Period [years]',
    yaxis_title='Total Damage [US$]',
    legend_title='Year',
    font=dict(family='Arial', size=16, color='black'),
    plot_bgcolor='white',
    paper_bgcolor='white'
)
format_plotly_axes(fig)
fig.write_html(dirout / f"total_damage_by_year_{SITE}_plotly.html")
write_image_safe(fig, dirout / f"total_damage_by_year_{SITE}_plotly.png")
write_image_safe(fig, dirout / f"total_damage_by_year_{SITE}_plotly.pdf")
if not BATCH_RUN: fig.show()

# ###############################################################################################################
#### Figures per cba_study_area ##########

# Repeat the same year-vs-rp figure for each cba_study_area
per_area_dir = dirout / "damages_no_adapt_by_cba_study_area"
per_area_dir.mkdir(parents=True, exist_ok=True)

for study_area in sorted(ALLD_BY_CBA_STUDY_AREA['cba_study_area'].dropna().unique()):
    study_area_data = ALLD_BY_CBA_STUDY_AREA[ALLD_BY_CBA_STUDY_AREA['cba_study_area'] == study_area].copy()
    #study_area_data['year'] = study_area_data['dem'].map(dem_year_map)

    study_area_year = (
        study_area_data[study_area_data['adapt'] == 'no_adaptation']
        .groupby(['rp', 'year'])['tot_cost']
        .sum()
        .reset_index()
        .rename(columns={'tot_cost': 'total_damage'})
    )

    if study_area_year.empty:
        print(f"Skipping {study_area}: no no_adaptation data available for year-vs-rp plot.")
        continue

    safe_study_area = str(study_area).replace(' ', '_').replace('/', '_')

    # #####################################
    # Matplotlib plot per study area
    # #####################################

    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('white')
    style_matplotlib_axes(ax)

    base_year = 2025
    base_data = study_area_year[study_area_year['year'] == base_year].set_index('rp')['total_damage']
    for idx, year in enumerate(sorted(study_area_year['year'].unique(), reverse=True)):
        year_data = study_area_year[study_area_year['year'] == year]
        
        ax.plot(year_data['rp'], year_data['total_damage'], marker='o', label=str(year), color=colors[idx])
        if year != base_year:
            for _, row in year_data.iterrows():
                rp, damage = row['rp'], row['total_damage']
                base_damage = base_data.get(rp, None)
                if base_damage and base_damage > 0:
                    increase_pct = 100 * (damage - base_damage) / base_damage
                    ax.annotate(
                        f"{increase_pct:.1f}%",
                        (rp, damage),
                        textcoords="offset points",
                        xytext=(0, 10),
                        ha='center',
                        fontsize=16,
                        color=colors[idx],
                    )

    ax.set_xlabel('Return Period [years]', fontsize=16)
    ax.set_ylabel('Total Damage [US$]', fontsize=16)
    ax.set_xticks([5, 20, 50, 100]); ax.set_xticklabels([5, 20, 50, 100])
    ax.set_title(f'Total Damage vs Return Period by Year - {study_area}', fontsize=16)
    ax.tick_params(axis='both', labelsize=16)
    ax.legend(title='Year', fontsize=16, title_fontsize=16)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{x/1e6:.0f}M'))
    ax.yaxis.get_offset_text().set_visible(False)
    #ax.grid(axis='y', color='lightgray', linestyle='--', linewidth=0.5)
    #ax.grid(axis='y', linestyle='--', alpha=0.3)
    #ax.grid(False)

    plt.tight_layout()
    plt.savefig(
        per_area_dir / f"total_damage_by_year_{safe_study_area}_{SITE}_matplotlib.png",
        dpi=300,
        facecolor='white',
        edgecolor='white',
        transparent=False)
    plt.savefig(
        per_area_dir / f"total_damage_by_year_{safe_study_area}_{SITE}_matplotlib.pdf",
        facecolor='white',
        edgecolor='white',
        transparent=False)
    plt.show()

    # #####################################
    # Plotly version per study area
    # #####################################

    fig = go.Figure()
    base_data = study_area_year[study_area_year['year'] == base_year].set_index('rp')['total_damage']
    for idx, year in enumerate(sorted(study_area_year['year'].unique(), reverse=True)):
        year_data = study_area_year[study_area_year['year'] == year]

        color = plotly_colors[idx % len(plotly_colors)]
        fig.add_trace(
            go.Scatter(
                x=year_data['rp'],
                y=year_data['total_damage'],
                mode='lines+markers',
                name=str(year),
                line=dict(color=color),
            )
        )
        if year != base_year:
            add_plotly_year_annotations(fig, year_data, base_data, color, year)
    #add_plotly_rp_vlines(fig, ALL_DAMAGES['rp'].unique(), ymin, ymax)
    fig.update_layout(
        title=f'Total Damage vs Return Period by Year - {study_area}',
        xaxis_title='Return Period [years]',
        yaxis_title='Total Damage [US$]',
        legend_title='Year',
        font=dict(family='Arial', size=16, color='black'),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    format_plotly_axes(fig)
    fig.write_html(per_area_dir / f"total_damage_by_year_{safe_study_area}_{SITE}_plotly.html")
    write_image_safe(fig, per_area_dir / f"total_damage_by_year_{safe_study_area}_{SITE}_plotly.png")
    write_image_safe(fig, per_area_dir / f"total_damage_by_year_{safe_study_area}_{SITE}_plotly.pdf")


# ###############################################################################################################
# figures ADAPTATION 
# ###############################################################################################################

# Matplotlib figures - adaptation
# plot_matplotlib_adaptation and damage_formatter are imported from aux_scripts.plot_utils

# Plots for each year
num_adaptations = len(ALLD_BY_CBA_STUDY_AREA['adapt'].unique())
colors = [plt.get_cmap('tab10')(i / max(num_adaptations - 1, 1)) for i in range(num_adaptations)]

for year in sorted(ALL_DAMAGES['year'].unique()):
    year_label = f"{int(year)}"
    fig, ax = plt.subplots(figsize=(10, 6))
    no_adapt_year = {row['rp']: row['total_damage'] for _, row in ALL_DAMAGES[(ALL_DAMAGES['adapt'] == 'no_adaptation') & (ALL_DAMAGES['year'] == year)].iterrows()}
    for idx, adapt in enumerate(adaptation_names.values()):
        scenario_data = ALL_DAMAGES[(ALL_DAMAGES['adapt'] == adapt) & (ALL_DAMAGES['year'] == year)]
        marker = 's' if adapt == 'no_adaptation' else 'o'
        plot_matplotlib_adaptation(ax, scenario_data, no_adapt_year, adapt, idx, colors, marker, year=year, site=SITE)

    # for rp_value in sorted(ALL_DAMAGES['rp'].unique()):
    #     ax.axvline(x=rp_value, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Return Period [years]')
    ax.set_ylabel('Total Damage [US$]')
    ax.set_title(f'Total Damage vs Return Period by Adaptation Scenario (Year={year})')
    ax.legend(title=f'Adaptation - {year}', bbox_to_anchor=(1.05, 1), loc='upper left')
    #ax.grid(axis='y', linestyle='--', alpha=0.7)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks([5, 20, 50, 100]); ax.set_xticklabels([5, 20, 50, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(damage_formatter))
    #ax.ticklabel_format(axis='y', style='plain')

    plt.tight_layout()
    plt.savefig(dirout / f"total_damage_by_adaptation_{year_label}_{SITE}_matplotlib.png")
    plt.savefig(dirout / f"total_damage_by_adaptation_{year_label}_{SITE}_matplotlib.pdf")
    plt.show()

# Plotly versions - adaptation
for year in sorted(ALL_DAMAGES['year'].unique()):
    year_label = f"{int(year)}"
    fig = go.Figure()
    no_adapt_year = {
        row['rp']: row['total_damage']
        for _, row in ALL_DAMAGES[
            (ALL_DAMAGES['adapt'] == 'no_adaptation') & (ALL_DAMAGES['year'] == year)
        ].iterrows()
    }
    for idx, adapt in enumerate(adaptation_names.values()):
        scenario_data = ALL_DAMAGES[(ALL_DAMAGES['adapt'] == adapt) & (ALL_DAMAGES['year'] == year)]
        color  = adaptation_colors.get(adapt, plotly_colors[idx % len(plotly_colors)])
        symbol = 'square' if adapt == 'no_adaptation' else 'circle'
        fig.add_trace(go.Scatter(
            x=scenario_data['rp'], y=scenario_data['total_damage'],
            mode='lines+markers', marker=dict(symbol=symbol, size=8),
            name=str(adapt), line=dict(color=color),
        ))
        add_plotly_adaptation_annotations(fig, scenario_data, no_adapt_year, adapt, color, year, site=SITE)

    fig.update_layout(
        title=f'Total Damage vs Return Period by Adaptation Scenario (Year={year})',
        xaxis_title='Return Period [years]',
        yaxis_title='Total Damage [US$]',
        yaxis=dict(range=[ymin, ymax]),
        legend_title=f'Adaptation — {year}',
        font=dict(family='Arial', size=16, color='black'),
        plot_bgcolor='white',
        paper_bgcolor='white',
    )
    format_plotly_axes(fig)
    fig.write_html(dirout / f"total_damage_by_adaptation_{year_label}_{SITE}_plotly.html")
    write_image_safe(fig, dirout / f"total_damage_by_adaptation_{year_label}_{SITE}_plotly.png")
    write_image_safe(fig, dirout / f"total_damage_by_adaptation_{year_label}_{SITE}_plotly.pdf")
    if not BATCH_RUN: fig.show()

############################################################################################################ 
# SUBSET BY BENEFIT THRESHOLD FOR CBA CALCULATION 
# ----------------------------------------------------
# # FLAG AREAS TO INCLUDE IN BCR CALCULATION BASED ON BASELINE DAMAGES (NO ADAPTATION, DEM020, RP50)
# ----------------------------------------------------
# Load csv file with cba_study_areas
damages_by_cba_area_file = dirout / f'ALLD_BY_CBA_STUDY_AREA_{SITE}.csv'
damages_by_cba = pd.read_csv(damages_by_cba_area_file)

# create flag by looking at the damages for the dem020/rp50/adapt000 scenario: if damages > THRESHODLD ($500,000) 
# include in cba calculation (flag = 1), otherwise not included (flag = 0)
baseline_damage_flag = (
    damages_by_cba[
        (damages_by_cba['adapt'] == 'no_adaptation')
        & (damages_by_cba['dem'] == 'dem020')
        & (damages_by_cba['rp'] == 50)
    ]
    .set_index('cba_study_area')['tot_cost']
    .gt(500_000)
    .astype(int)
)
damages_by_cba['include_in_bcr'] = (
    damages_by_cba['cba_study_area']
    .map(baseline_damage_flag)
    .fillna(0)
    .astype(int)
)
# Save as new file with name ALLD_BY_CBA_STUDY_AREA_{SITE}_with_flag.csv
damages_by_cba.to_csv(dirout / f"ALLD_BY_CBA_STUDY_AREA_{SITE}_abovethreshold.csv", index=False)

print(damages_by_cba.head())
print(damages_by_cba.columns)
print(damages_by_cba.shape)
print(damages_by_cba.info())
reference_areas = damages_by_cba['cba_study_area'].unique()
print(f"Reference areas ({len(reference_areas)}): {reference_areas}")

# ----------------------------------------------------------------------------------------------
# Load AED by area csv and add flag column to it as well:
aed_byarea_gdf = pd.read_csv(dirout / f"AED_byarea_{SITE}.csv")
include_in_bcr_lookup = (
    damages_by_cba[['cba_study_area', 'include_in_bcr']]
    .drop_duplicates(subset=['cba_study_area'])
)
aed_byarea_gdf = aed_byarea_gdf.merge(include_in_bcr_lookup, on='cba_study_area', how='left')
aed_byarea_gdf['include_in_bcr'] = aed_byarea_gdf['include_in_bcr'].fillna(0).astype(int)
# Save aed_byarea_gdf with new flag column as a new csv file:
aed_byarea_gdf.to_csv(dirout / f"AED_byarea_{SITE}_abovethreshold.csv", index=False) 

# ----------------------------------------------------------------------------------------------
# Load AEB by area csv and add flag column to it as well:
aeb_byarea_gdf = pd.read_csv(dirout / f"AEB_byarea_{SITE}.csv")

aeb_byarea_gdf = aeb_byarea_gdf.merge(include_in_bcr_lookup, on='cba_study_area', how='left')
aeb_byarea_gdf['include_in_bcr'] = aeb_byarea_gdf['include_in_bcr'].fillna(0).astype(int)

# Save aeb_byarea_gdf with new flag column as a new csv file:
aeb_byarea_gdf.to_csv(dirout / f"AEB_byarea_{SITE}_abovethreshold.csv", index=False) 

# ----------------------------------------------------------------------------------------------
############################################################################################################

print("S022 - AED and AEB calculations completed and exported to CSV.")
print(f"Output files written to {dirout}.")
print('\n end of script')
