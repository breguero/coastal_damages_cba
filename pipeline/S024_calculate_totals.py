
#################################################################################################################
#   S024_calculate_totals.py                                                                               
#   Script description:   Reads per-building damage CSVs produced by S020, aggregates direct damages          
#                         by building type (RES, COM, IND, REL, GOV, ROA) and scenario metadata               
#                         (site, DEM, return period, adaptation option, mode), and writes three                 
#                         summary tables (population, building count, total damage cost) as CSVs.              
#                                                                                                  
#  Dependencies:
#    - S000_project_config_cosmos_adapt.py (imports project_root_directory and config)
#    - Input CSV files matching:
#      *_damages_and_roads_buildings_summary.csv
#      from:
#      011_DAMAGES_results/<SITE>/012_damages/damages_by_buildings/flood_map_<MODE>/
#
#  Outputs:
#    - population_table_<MODE>.csv
#    - building_count_table_<MODE>.csv
#    - total_damage_table_<MODE>.csv
#    written to:
#    011_DAMAGES_results/<SITE>/012_damages/summary_damages/flood_map_<MODE>/
#
#  breguero@ucsc.edu
#  05/14/2026
# ###############################################################################################################   
from S000_project_config_cosmos_adapt import *
import pandas as pd

# ----------------------------------------------------
# config 
##These are the four sites we want to run in general for Cosmos Adapts:
#SITE = 'site001_santacruz2'
# #SITE = 'site001_santacruz' #site_001, site_002? site is the parent dir so you don't need {site}_NSI folder***
# SITE = 'site003_venturanorth'
#SITE = 'site002_halfmoonbay' #for testing only, comment out when running from terminal
SITE = RUN_SITE  # set with COSMOS_SITE or run_pipeline.py --site

# Mode (runs)  	
#   001: hydrodynamic only / DEM = 1, morpho = 0 
#   002: morphodynamic update enabled / DEM = 1, morpho = 1 
#   003: hydro without DEM change (bathy use dem020) / DEM = 0, morpho = 0 
#   004: morpho without DEM change (bathy use dem020) / DEM = 0, morpho = 1 	
MODE = RUN_MODE  # set with COSMOS_MODE or run_pipeline.py --mode (see 000_scenario_convention_dictionary)
# ----------------------------------------------------

# inputs 
damages_folder = output_root / SITE / '012_damages' / 'indirect_damages' / f'flood_map_{MODE}'

#input_dir = damages_folder / damage_folder_outputs / SITE / '012_damages' / 'damages_by_buildings' / f'flood_map_{MODE}'
input_dir = damages_folder
input_files = sorted(input_dir.glob("*_damages_and_roads_buildings_summary.csv")) 

# output folder 
#output_folder = damages_folder / '012_damages' / 'summary_damages' / f'flood_map_{MODE}'
output_folder = output_root / SITE / '012_damages' / 'summary_damages' / f'flood_map_{MODE}'
if not output_folder.exists():
    output_folder.mkdir(parents=True, exist_ok=True)

# set building types (these are the categories we want to summarize by, but not all may be present in every file)
BUILDING_TYPES = ['RES', 'COM', 'IND', 'REL', 'GOV', 'ROA']

# Helper functions
def _parse_file_metadata(file_path):
    stem_tokens = file_path.stem.split('_')
    lower_tokens = [t.lower() for t in stem_tokens]

    def _find(prefix):
        for tok in stem_tokens:
            if tok.lower().startswith(prefix):
                return tok
        return ''

    cut_idx = [
        i for i, tok in enumerate(lower_tokens)
        if tok.startswith('dem') or tok.startswith('rp') or tok.startswith('adapt') or tok.startswith('mode')
    ]
    first_cut = min(cut_idx) if cut_idx else len(stem_tokens)
    site = '_'.join(stem_tokens[:first_cut])

    return {
        'site': site,
        'dem': _find('dem'),
        'rp': _find('rp'),
        'adapt': _find('adapt'),
        'mode': _find('mode') or MODE,
    }
# The building type column can have different names in different files, so we check for common possibilities.
def _find_building_type_column(df):
    for col in ['building_type', 'bld_type', 'type', 'building_type_category']: # Marina added building_type_category as another variable name
        if col in df.columns:
            return col
    #raise KeyError('Building type column not found (expected one of: building_type, bld_type, type).')
    raise KeyError('Building type column not found (expected one of: building_type, bld_type, type, building_type_category).') #building_type_category added by Marina
# Process each file and aggregate data by building type and metadata (site, dem, rp, adapt, mode).
population_rows = []
building_rows = []
damage_rows = []

for file_path in input_files:
    meta = _parse_file_metadata(file_path) # check this 
    print(meta)
    df = pd.read_csv(file_path) 

    btype_col = _find_building_type_column(df)
    df[btype_col] = df[btype_col].astype(str).str.upper()

    pop_sum = df.groupby(btype_col)['population'].sum() if 'population' in df.columns else pd.Series(dtype=float)
    bld_sum = df.groupby(btype_col)['building_counter'].sum() if 'building_counter' in df.columns else pd.Series(dtype=float)
    dmg_sum = df.groupby(btype_col)['tot_cost'].sum() if 'tot_cost' in df.columns else pd.Series(dtype=float)

    population_rows.append({**meta, **{bt: float(pop_sum.get(bt, 0)) for bt in BUILDING_TYPES}})
    building_rows.append({**meta, **{bt: float(bld_sum.get(bt, 0)) for bt in BUILDING_TYPES}})
    damage_rows.append({**meta, **{bt: float(dmg_sum.get(bt, 0)) for bt in BUILDING_TYPES}})

population_table = pd.DataFrame(population_rows, columns=['site', 'dem', 'rp', 'adapt', 'mode'] + BUILDING_TYPES)
building_count_table = pd.DataFrame(building_rows, columns=['site', 'dem', 'rp', 'adapt', 'mode'] + BUILDING_TYPES)
total_damage_table = pd.DataFrame(damage_rows, columns=['site', 'dem', 'rp', 'adapt', 'mode'] + BUILDING_TYPES)

if population_table.empty:
    print("Warning: No population data found in input files. Population table will be empty.")
if building_count_table.empty:
    print("Warning: No building count data found in input files. Building count table will be empty.")
if total_damage_table.empty:
    print("Warning: No damage cost data found in input files. Total damage table will be empty.")
    
# save totals as CSVs
population_table.to_csv(output_folder / f'population_table_{MODE}.csv', index=False)
building_count_table.to_csv(output_folder / f'building_count_table_{MODE}.csv', index=False)
total_damage_table.to_csv(output_folder / f'total_damage_table_{MODE}.csv', index=False)

print(total_damage_table) 
print("Script S024 run successfully. Summary tables saved to output folder.")
print(f"Output files written to {output_folder}.")
print('\n end of script')
