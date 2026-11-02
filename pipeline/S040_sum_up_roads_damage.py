#################################################################################################################
#   S040_sum_up_roads_damage.py
#
#   Script description:
#   Reads per-scenario building summary CSV files produced by the damage workflow, extracts the ROA
#   (road) total damage from the building_type_category column, and writes a compact site-level summary CSV.
#
#   Input files:
#       *_damages_and_roads_buildings_summary.csv
#       from:
#       damage_folder_outputs/<SITE>/012_damages/indirect_damages/flood_map_<MODE>/
#
#   Output:
#       <SITE>_road_damages_summary.csv
#       written to:
#       damage_folder_outputs/<SITE>/012_damages/road_damages/
#
#   breguero@ucsc.edu
#   05/28/2026
# ###############################################################################################################

from S000_project_config_cosmos_adapt import *
import pandas as pd
from pathlib import Path

# ----------------------------------------------------
# config
##These are the four sites we want to run in general for Cosmos Adapts:
	# SITE = 'site001_santacruz' #site_001, site_002? site is the parent dir so you don't need {site}_NSI folder***
	# SITE = 'site002_halfmoonbay'
	# SITE = 'site003_venturanorth'
#SITE = 'site001_santacruz' #for testing only, comment out when running from terminal
#SITE = 'site001_santacruz'
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

input_dir = output_root / SITE / '012_damages' / 'indirect_damages' / f'flood_map_{MODE}'
if not input_dir.exists():
	raise FileNotFoundError(f"Input directory not found: {input_dir}")

output_folder = output_root / SITE / '012_damages' / 'road_damages' / f'flood_map_mode_{MODE}'
output_folder.mkdir(parents=True, exist_ok=True)

input_files = sorted(input_dir.glob('*_damages_and_roads_buildings_summary.csv'))
if not input_files:
	raise FileNotFoundError(f"No input CSV files found in {input_dir}")


def _parse_file_metadata(file_path: Path):
	stem_tokens = file_path.stem.split('_')
	lower_tokens = [token.lower() for token in stem_tokens]

	def _find(prefix):
		for token in stem_tokens:
			if token.lower().startswith(prefix):
				return token
		return ''

	cut_idx = [
		i for i, token in enumerate(lower_tokens)
		if token.startswith('dem') or token.startswith('rp') or token.startswith('adapt') or token.startswith('mode')
	]
	first_cut = min(cut_idx) if cut_idx else len(stem_tokens)
	site_name = '_'.join(stem_tokens[:first_cut])

	return {
		'site_name': site_name,
		'dem': _find('dem'),
		'rp': _find('rp'),
		'adaptation_scenario': _find('adapt'),
		'mode': _find('mode') or MODE,
	}


road_rows = []

for file_path in input_files:
	meta = _parse_file_metadata(file_path)
	df = pd.read_csv(file_path)

	if 'building_type_category' not in df.columns:
		raise KeyError(f"'building_type_category' column not found in {file_path.name}")
	if 'tot_cost' not in df.columns:
		raise KeyError(f"'tot_cost' column not found in {file_path.name}")

	roa_total = df.loc[df['building_type_category'].astype(str).str.upper() == 'ROA', 'tot_cost'].sum()

	road_rows.append({
		'site_name': meta['site_name'],
		'dem': meta['dem'],
		'rp': meta['rp'],
		'adaptation_scenario': meta['adaptation_scenario'],
		'mode': meta['mode'],
		'building_type_category': 'ROA',
		'tot_cost': float(roa_total),
	})

road_damages_summary = pd.DataFrame(road_rows, columns=['site_name', 'dem', 'rp', 'adaptation_scenario', 'mode', 'building_type_category', 'tot_cost'])
road_damages_summary.to_csv(output_folder / f'{SITE}_road_damages_summary.csv', index=False)

print(f"Saved road damages summary to: {output_folder / f'{SITE}_road_damages_summary.csv'}")
print('end of script')