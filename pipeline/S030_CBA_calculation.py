#################################################################################################################                                                                                 
#   S030A_CBA_calculation.py                                                                                     
#   breguero@ucsc.edu 12/30/2025
#                                                                                                                                  
#   Script description:                                                                                          
#   calculate cba 
#       input: AED_benefits table (from S022_AED_calculation_and_plots.py) and adaptation costs table (from S023_AED_nourishments_and_combineAED.py)
#       output: table with cba results (npv, bcr, roi) for each adaptation scenario, cba study area, and dem year.
#       also creates plots of cba results (bcr, roi, pv) for each adaptation scenario, cba study area, and dem year.
#       plots are saved in the same output directory as the cba results table.
#
# This script uses for the cbr computations only study areas that have damages > $500,000 for the dem020/rp50/no_adaptation scenario.
#
#   Revision 2026-10-29 (cost accounting):
#   - A measure placed in a study area (adapt_cost > 0) always carries its full cost (construction + PV of
#     maintenance), also when its benefit is zero: pv = 0, bcr = 0, npv = -cost. Before, adaptation_cost was
#     set to NaN for zero-benefit areas and silently dropped from the regional cost sum, which inflated the
#     regional BCR (Santa Cruz dunes: 7.25 -> 4.26 in 2025) and made the cost base change by epoch.
#   - A measure not placed in a study area (adapt_cost == 0) has cost 0 and bcr = NaN; any benefit there is
#     spill-over from neighbouring areas and is kept in the regional PV sum (flag column 'placed').
#   - COST_BASE selects the regional cost base: 'all_placed' (default) or 'legacy' (previous behaviour).
# ###############################################################################################################   
from aux_scripts.damage_calculation_tools import NPV, PV, ROI, find_investment_cost_for_bcr_1
from S000_project_config_cosmos_adapt import *

import pandas as pd
import numpy as np
import os
import sys
import warnings
import seaborn as sns
import matplotlib
if not hasattr(sys, 'ps1'):
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
warnings.filterwarnings('ignore')
plt.rcParams.update({
    'font.size': 16,
    'font.family': 'DejaVu Sans',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'sans-serif']
})

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
NAME = f"CBA_{dunemode}"

# ------------------------- COST BASE RULE ------------------------------------------------------
#   'all_placed': every placed measure carries its cost in every epoch (consistent cost base)
#   'legacy'    : zero-benefit areas get NaN cost and drop out of the regional sum (results in the 2026 report)
COST_BASE = RUN_COST_BASE  # set with COSMOS_COST_BASE: 'all_placed' | 'legacy'
print(f"COST_BASE = {COST_BASE}")
# ------------------------- DIRECTORIES AND FILES ----------------------------------------------------

dirdata = output_root / SITE / '012_damages' / 'aed_cba_results' / f'flood_map_{MODE}' 

# costs of adaptation (S013) 
dirdata_costs = output_root / SITE / '012_damages' / 'adaptation_costs'
cost_filepath = dirdata_costs /  f'all_adapt_costs_{SITE}.csv'

# Check if cost_filepath exists
if not cost_filepath.exists():
    raise FileNotFoundError(f"Cost file not found: {cost_filepath}")

# dirout directory for output of this script
dirout = dirdata 
print(f"Output directory: {dirout}")

# ------------------------- CBA CALCULATION --------------------------------------------------------------

DISCOUNTING = RUN_DISCOUNT_RATE  # set with COSMOS_DISCOUNT_RATE (default 0.03)
print(f"Using discount rate: {DISCOUNTING*100:.2f}%" )

# Read AEB benefits table:
#aed_benefits = pd.read_csv(dirdata / f"AEB_byarea_{SITE}.csv") 
aed_benefits = pd.read_csv(dirdata / f"AEB_byarea_{SITE}_abovethreshold.csv") 
print(aed_benefits.head())

# Clip negative AEB values to 0
aed_benefits['aeb'] = aed_benefits['aeb'].clip(lower=0)
aed_benefits['aed'] = aed_benefits['aed'].clip(lower=0)
aed_benefits['aed_population'] = aed_benefits['aed_population'].clip(lower=0)
aed_benefits['aeb_population'] = aed_benefits['aeb_population'].clip(lower=0)

# -------------------------------------------------------------------------------------- 
# fill out missing combinations of cba_study_area, year, and adapt in aed_benefits with zero benefits (for cases where there were no benefits calculated because of missing damage or population data for that area)
# Read adaptation costs table:
all_adapt_costs = pd.read_csv(cost_filepath)
print(all_adapt_costs.head())

# Ensure adaptation scenarios in benefits have cost records.
# required_adapt_combos = (
#     aed_benefits.loc[aed_benefits['adapt'] != 'no_adaptation', ['cba_study_area', 'year', 'adapt']]
#     .drop_duplicates()
#     .rename(columns={'year': 'dem'})
# )
# missing_combos = required_adapt_combos.merge(
#     all_adapt_costs[['cba_study_area', 'dem', 'adapt']].drop_duplicates(),
#     on=['cba_study_area', 'dem', 'adapt'],
#     how='left',
#     indicator=True
# )
# missing_combos = missing_combos[missing_combos['_merge'] == 'left_only'].drop(columns=['_merge'])
# if not missing_combos.empty:
#     print(f"Adding {len(missing_combos)} missing adaptation cost records with zero costs")
#     for col in ['adapt_cost', 'maint_cost', 'recon_cost']:
#         if col not in all_adapt_costs.columns:
#             all_adapt_costs[col] = np.nan
#     missing_rows = missing_combos.assign(adapt_cost= np.nan, maint_cost= np.nan, recon_cost= np.nan)
#     all_adapt_costs = pd.concat([all_adapt_costs, missing_rows], ignore_index=True)
# all_adapt_costs['adapt_cost'] = all_adapt_costs['adapt_cost'].fillna(0)
# --------------------------------------------------------------------------------------

# ------------------------- CBA ANALYSIS ------------------------- 
# CBA per individual cba_study_area (per subregion): 
# Per cba_study_area: calculate PV, NPV, ROI, BCR for each adaptation scenario and DEM year.
cba_results = []
for (study_area, year), group in aed_benefits.groupby(['cba_study_area', 'year']):
    for adapt in group['adapt'].unique():
        if adapt == 'no_adaptation': continue

        # Get the adaptation cost for the current scenario
        # construction 
        adapt_cost = all_adapt_costs[(all_adapt_costs['cba_study_area']==study_area) & 
                        (all_adapt_costs['year']==year) &
                        (all_adapt_costs['adapt']==adapt)]['adapt_cost'].values[0]
        print(adapt + ' - ' + str(adapt_cost))

        # maintenance cost
        maint_cost = all_adapt_costs[(all_adapt_costs['cba_study_area']==study_area) & 
                        (all_adapt_costs['year']==year) &
                        (all_adapt_costs['adapt']==adapt)]['maint_cost'].values[0]
        
        benefit = group[group['adapt'] == adapt]['aeb'].values[0]
        placed = adapt_cost > 0

        # total cost of a placed measure: construction + PV of maintenance (+ PV of dune reconstruction if activated)
        if placed:
            if (adapt == 'dune') & ACTIVATE_DUNE_RECONSTRUCTION:
                recon_cost = all_adapt_costs[(all_adapt_costs['cba_study_area']==study_area) &
                            (all_adapt_costs['year']==year) &
                            (all_adapt_costs['adapt']==adapt)]['recon_cost'].values[0]
                adapt_cost = adapt_cost + PV([recon_cost], NYR, DISCOUNTING)  # + PV([maint_cost], NYR, DISCOUNTING)
            else:
                adapt_cost = adapt_cost + PV([maint_cost], NYR, DISCOUNTING)
        else:
            adapt_cost = 0.0

        if COST_BASE == 'legacy' and not benefit > 0:
            adapt_cost = np.nan

        pv = PV([benefit], NYR, DISCOUNTING) if benefit > 0 else 0.0
        if placed and adapt_cost > 0:
            npv = NPV([benefit], NYR, DISCOUNTING, adapt_cost)
            roi = ROI([benefit], NYR, DISCOUNTING, adapt_cost)
            bcr = pv / adapt_cost
            cost_bcr1 = find_investment_cost_for_bcr_1([benefit], adapt_cost, DISCOUNTING, NYR)
        else:
            npv = np.nan
            roi = np.nan
            bcr = np.nan
            cost_bcr1 = np.nan
        if COST_BASE == 'legacy' and not benefit > 0:
            pv = np.nan

        # Save results
        cba_results.append({
            'cba_study_area': study_area,
            'year': year,
            'adapt': adapt,
            'aeb': benefit, 
            'adaptation_cost': adapt_cost,
            'discount_rate': DISCOUNTING,
            'nyr': NYR,
            'roi': roi,
            'cost_for_bcr_1': cost_bcr1,
            'pv': pv,
            'npv': npv, 
            'bcr': bcr, 
            'placed': int(placed),
            'include_in_bcr': group['include_in_bcr'].values[0] if 'include_in_bcr' in group.columns else 0
            })

# Convert results to DataFrame for easier use
cba_results_df = pd.DataFrame(cba_results)

# Export cba_results_df to CSV
formatted = f"{round(DISCOUNTING * 1000):03d}"
NAMEOUT = f'CBA_{dunemode}.csv'
if COST_BASE != 'all_placed':
    NAME = f"{NAME}_{COST_BASE}"
cba_results_df.to_csv(dirout / f"CBA_results_bycbastudyarea_disc{formatted}_{NAME}_mode{MODE}.csv")
#cba_results_df.to_csv(dirout / f"CBA_results_byregion_disc", index=False)
print(cba_results_df)

############################################################################################################################################################## 
## # CBA per total site ( sum of all cba_study_area subregions):

# Sum up individual values for each cba_study_area to get values for total site 
cba_results_df_subset = cba_results_df.copy()
cba_results_df_subset = cba_results_df_subset[cba_results_df_subset['include_in_bcr']==1]  # filter to only include rows where include_in_bcr is 1 for the total site cba calculations
cba_results_df_subset = (cba_results_df_subset
    .groupby(['year', 'adapt'], as_index=False)
    .agg(aeb=('aeb', 'sum'), adaptation_cost=('adaptation_cost', 'sum'),
         n_placed=('placed', 'sum'),
         n_cost_effective=('bcr', lambda b: int((b > 1).sum()))))

print("cba_results_df_subset:")
print(cba_results_df_subset)

# Build total-site CBA metrics from the aggregated rows above.
cba_results_totalregion = []
for _, row in cba_results_df_subset.iterrows():
    year = row['year']
    adapt = row['adapt']
    #include_in_bcr = row['include_in_bcr']
    benefit = row['aeb']
    cost = row['adaptation_cost']

    print(adapt + ' - ' + str(cost))
    print("benefit:")
    print(benefit)

    pv_totals = PV([benefit], NYR, DISCOUNTING)
    npv_totals = NPV([benefit], NYR, DISCOUNTING, cost) if cost > 0 else np.nan
    roi_totals = ROI([benefit], NYR, DISCOUNTING, cost) if cost > 0 else np.nan
    bcr_totals = pv_totals / cost if cost > 0 else np.nan
    cost_bcr1_totals = find_investment_cost_for_bcr_1([benefit], cost, DISCOUNTING, NYR) if adapt != 'no_adaptation' else np.nan

    cba_results_totalregion.append({
        'year': year,
        'adapt': adapt,
        'aeb': benefit,
        'adaptation_cost': cost,
        'n_placed': int(row['n_placed']),
        'n_cost_effective': int(row['n_cost_effective']),
        'discount_rate': DISCOUNTING,
        'nyr': NYR,
        'roi': roi_totals,
        'cost_for_bcr_1': cost_bcr1_totals,
        'pv': pv_totals,
        'npv': npv_totals,
        'bcr': bcr_totals
    })

# export them to a table 
cba_results_totalregion_df = pd.DataFrame(cba_results_totalregion)
print(cba_results_totalregion_df)

# export 
cba_results_totalregion_df.to_csv(dirout / f"CBA_results_TOTALS_{SITE}_{NAME}_disc{formatted}_mode{MODE}.csv")
print(f"CBA_results_totalregion_{NAMEOUT}_disc{formatted}.csv")
print("Intermediate completion.")
#cba_results_df.to_csv(dirout / f"CBA_results_byregion_disc")

##########################################################################################################################################
# FIGURES FROM HERE 
##########################################################################################################################################
# FIGURES FOR TOTAL STUDY AREA:

# BCR FOR TOTAL SITE (ALL SUBREGIONS COMBINED): 

# helper to save figures (accepts either a Figure object or `plt`)
def save_plot(fig, filename):
    plt_out = fig
    plt_out.savefig(dirout / f"{filename}.png")
    plt_out.savefig(dirout / f"{filename}.pdf")
    plt_out.savefig(dirout / f"{filename}.svg")

# Plot BCR for total site (all subregions combined) for all adaptation scenarios and DEMs:
def plot_bcr_by_adaptation_and_year(df, namefileout):
    plt.figure(figsize=(10, 6))
    years = sorted(df.loc[df['adapt'] != 'no_adaptation', 'year'].dropna().unique())
    adapt_order = ['seawall', 'reef', 'dune']
    #adapt_order = [adapt for adapt in adapt_order if adapt in df['adapt'].dropna().unique()]
    # Color palette:
    palette_bcr = ['#a8c8e8', '#4a86b8', '#1a3a5c']
    #palette_bcr = ['#5EC6F2', '#E37B07', '#D4062C']
    
    palette = palette_bcr[:len(years)] if len(years) <= len(palette_bcr) else sns.color_palette("PuOr", n_colors=len(years))
    sns.barplot(
        #data=cba_results_totalregion_df[cba_results_totalregion_df['adapt'] != 'no_adaptation'],
        data = df[df['adapt'] != 'no_adaptation'],
        x='adapt',
        y='bcr',
        order=adapt_order,
        hue='year',
        hue_order=years,
        palette=palette
    )
    plt.xlabel('Adaptation Scenario')
    plt.ylabel('Benefit-Cost Ratio (BCR)')
    # include region in title when plotting a single region
    region = None
    if 'cba_study_area' in df.columns:
        unique_regions = df['cba_study_area'].dropna().unique()
        if len(unique_regions) == 1:
            region = unique_regions[0]
    if region:
        plt.title(f'BCR for Region: {region} \n')
    else:
        plt.title(f'BCR Total Study Site: {SITE} by Adaptation Scenario and Year \n')
    plt.axhline(1.5, color='black', linestyle='--', alpha=0.25)
    plt.legend(title='Year')
    plt.ylim(0, None)
    plt.tight_layout()
    save_plot(plt, namefileout)
    plt.close()

# Plot BCR total study area (total SITE):
plot_bcr_by_adaptation_and_year(cba_results_totalregion_df, f"BCR_totals_site_{SITE}_{dunemode}_benthreshld_mode{MODE}")

##### BCR BY SUBREGION (CBA_STUDY_AREA):
# Plot BCR by region (cba_study_area):
for region in cba_results_df['cba_study_area'].unique():
    plot_bcr_by_adaptation_and_year(cba_results_df[cba_results_df['cba_study_area'] == region], 
                                    f"BCR_by_subregion_{SITE}_{region}_{dunemode}_mode{MODE}")

##########################################################################################################################################
# PV FIGURE:
# Plot PV for all adaptation scenarios and DEMs
def plot_pv_by_adaptation_and_year(df, namefileout):
    plt.figure(figsize=(10, 6))
    adapt_order = ['seawall', 'reef', 'dune']
    # adapt_order = [adapt for adapt in adapt_order if adapt in df['adapt'].dropna().unique()]
    sns.barplot(
        data=df[df['adapt'] != 'no_adaptation'],
        x='adapt',
        y='pv',
        order=adapt_order,
        hue='year'
    )
    plt.xlabel('Adaptation Scenario')
    plt.ylabel('Present Value (PV) [US$]')
    # include region in title when plotting a single region
    region = None
    if 'cba_study_area' in df.columns:
        unique_regions = df['cba_study_area'].dropna().unique()
        if len(unique_regions) == 1:
            region = unique_regions[0]
    if region:
        plt.title(f'PV for Region: {region} \n')
    else:
        plt.title(f'PV Total Study Site: {SITE} by Adaptation Scenario and Year \n')
    plt.legend(title='Year')
    ax = plt.gca()
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 1_000_000:g}M"))
    ax.yaxis.get_offset_text().set_visible(False)
    plt.ylim(0, None)
    plt.tight_layout()
    save_plot(plt, namefileout)
    plt.close()

# Plot PV total study area (total SITE)
plot_pv_by_adaptation_and_year(cba_results_totalregion_df, f"PV_totalsite_{SITE}_{dunemode}_mode{MODE}")

# Plot PV by region (cba_study_area):
for region in cba_results_df['cba_study_area'].unique():
    plot_pv_by_adaptation_and_year(cba_results_df[cba_results_df['cba_study_area'] == region], f"PV_by_subregion_{SITE}_{region}_{dunemode}_benthreshld_mode{MODE}")

# #########################################################################################################################################################
# Plot AEB for total region for all adaptation scenarios and DEMs

# plt.figure(figsize=(10, 6))
# sns.barplot(
#     data=cba_results_totalregion_df[cba_results_totalregion_df['adapt'] != 'no_adaptation'],
#     x='adapt',
#     y='aed_benefit',
#     hue='year'
# )
# plt.xlabel('Adaptation Scenario')
# plt.ylabel('Annual Expected Benefit  (AEB) [US$]')
# plt.title(f'AEB for {SITE} by Adaptation Scenario and Year')
# plt.legend(title='Year')
# ax = plt.gca()
# ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 1_000_000:g}M"))
# ax.yaxis.get_offset_text().set_visible(False)
# plt.tight_layout()
# save_plot(plt, f"AEB_totalsite_{SITE}_{dunemode}_by_adaptation_and_year_dlt500k")
# plt.show()

def plot_aeb_by_adaptation_and_year(df, namefileout):
    plt.figure(figsize=(10, 6))
    adapt_order = ['seawall', 'reef', 'dune']
    #adapt_order = [adapt for adapt in adapt_order if adapt in df['adapt'].dropna().unique()]
    sns.barplot(
        data=df[df['adapt'] != 'no_adaptation'],
        x='adapt',
        y='aeb',
        order=adapt_order,
        hue='year'
    )
    plt.xlabel('Adaptation Scenario')
    plt.ylabel('Annual Expected Benefit (AEB) [US$]')
    # include region in title when plotting a single region
    region = None
    if 'cba_study_area' in df.columns:
        unique_regions = df['cba_study_area'].dropna().unique()
        if len(unique_regions) == 1:
            region = unique_regions[0]
    if region:
        plt.title(f'AEB for Region: {region} \n')
    else:
        plt.title(f'AEB Total Study Site: {SITE} by Adaptation Scenario and Year \n')
    plt.legend(title='Year')
    ax = plt.gca()
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 1_000_000:g}M"))
    ax.yaxis.get_offset_text().set_visible(False)
    plt.ylim(0, None)
    plt.tight_layout()
    save_plot(plt, namefileout)
    plt.close()

# Plot AEB total study area (total SITE)
plot_aeb_by_adaptation_and_year(cba_results_totalregion_df, dirout / f"AEB_totalsite_{SITE}_{dunemode}_benthreshld_mode{MODE}")

# Plot AEB by region (cba_study_area):
for region in cba_results_df['cba_study_area'].unique():
    plot_aeb_by_adaptation_and_year(cba_results_df[cba_results_df['cba_study_area'] == region],
                                    dirout / f"AEB_by_subregion_{SITE}_{region}_{dunemode}_mode{MODE}")

print("S030A - CBA analysis and plotting completed.")
print(f"Output files written to {dirout}.")
print('\n end of script')