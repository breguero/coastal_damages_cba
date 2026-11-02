#################################################################################################################
#   S020_calculate_damages_by_buildings.py                                                                         
#       - Based on the script calculate_damages_by_buildings.py from Brook.                                       
#       - Improved with code structure and code fragments from NBS Adapts code from David                       
#       - Marina renamed this script to S020_calculate_damages_by_buildings.py on November 1, 2025              
#
#   Script description:                                                                             
#   calculates the damages to buildings and roads caused by flooding based on flood maps,           
#   building exposure data, and damage function tables.                                             
#   creates outputs in 'damages_by_buildings' folder including a file for each flood map (in csv and gpkg format)
#
#  Input data:                                                                                              
#       - Flood maps in .tif format located in the appropriate flood maps directory for the study region.
#       - Building exposure data in a GeoPackage file located in the exposure directory for the study region (includes the cba study areas).
#       - Damage function tables in .csv format located in the damage tables directory.
#  Output data:                                                                                             
#       - For each flood map, a .csv file - with direct damages calculation, to be used by indirects calculation 
#       - a .gpkg file containing the calculated damages for buildings and roads.
# (note that indirect damages are not included in this file, but will be added in the next script S021_calculate_indirect_damages.py)
#
# breguero@ucsc.edu 01/08/2026   
# breguero@ucsc.edu 06/15/2026   
# ############################################################################################################### 
#   
from S000_project_config_cosmos_adapt import *
from aux_scripts.calculate_damage_percentage_from_lookup_table import calculate_damage_percentage_from_lookup_table
from aux_scripts.get_road_damage_by_buildings import get_road_damage_by_buildings

import os
import pandas as pd
import geopandas as gpd
import rioxarray
from rasterstats import zonal_stats
import numpy as np
from tqdm import tqdm
import warnings
import glob
import time
from pathlib import Path
import sys
from itertools import product

#################################################################################################################################################################
# the code access the flood_map_sims folder (for SITE) and selects the flood maps that match the MODE and the site number of the region we are analyzing, 
# then it processes each flood map to calculate the damages to buildings and roads, 
# and saves the results in a specified output directory, with one file per flood map. the output folder has the MODE in the name. 

# ----------------------------------------------------
# config 
##These are the four sites we want to run in general for Cosmos Adapts:
    # SITE = 'site001_santacruz' #site_001, site_002? site is the parent dir so you don't need {site}_NSI folder***
    # SITE = 'site002_halfmoonbay' 
    # SITE = 'site003_venturanorth'
SITE = RUN_SITE  # set with COSMOS_SITE or run_pipeline.py --site
#SITE = 'site001_santacruz' #for testing only, comment out when running from terminal
#SITE = 'site002_halfmoonbay' #for testing only, comment out when running from terminal
#SITE = 'site003_venturanorth' #for testing only, comment out when running from terminal
#SITE = 'site004_venturanorth2'

# Mode (runs)  	
#   001: hydrodynamic only / DEM = 1, morpho = 0 
#   002: morphodynamic update enabled / DEM = 1, morpho = 1 
#   003: hydro without DEM change (bathy use dem020) / DEM = 0, morpho = 0 
#   004: morpho without DEM change (bathy use dem020) / DEM = 0, morpho = 1 	
MODE = RUN_MODE  # set with COSMOS_MODE or run_pipeline.py --mode (see 000_scenario_convention_dictionary)
# ----------------------------------------------------

OVERWRITE = True # whether to overwrite existing output files, set to False to skip processing if output already exists

#################################################################################################################################################################
# Create error message if region_name not found:
print(f"Calculating direct damages for site: {SITE}")
# ----------------------------------------------------
if SITE not in ['site001_santacruz2','site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', 'site004_venturanorth2']:
    raise ValueError(f"region_name {SITE} not recognized. Please choose from 'site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', or 'site004_venturanorth2'.")    
# ----------------------------------------------------

# FLOOD MAPS 
site_number = SITE.split('_')[0] # extract site number from region name, e.g. site001
#name_code_flood_maps = f'{site_number}*_mode{MODE}_hmax.tif'  # site001_dem020_rp005_adapt000_mode001_hmax

#  DIRECTORIES: 

# output damages directory name
output_folder = output_root / SITE / '012_damages' / 'damages_by_buildings' / f'flood_map_{MODE}'
#output_folder = output_root / SITE / '012_damages_normalfiles' / 'damages_by_buildings' / f'flood_map_{MODE}' #Change to "_cleaned" when running cleaned files
if not output_folder.exists():
    output_folder.mkdir(parents=True, exist_ok=True)
print(f"Output directory: {output_folder}")

# directory for flood maps 
flood_maps_directory = datadir_damages / SITE / 'flood_map_sims' # original line;
#FOR HALF MOON BAY:
# flood_maps_directory = datadir_damages / SITE / 'flood_map_sims' / 'flood_map_sims_copied_by_Marina' # subfolder to copy "normal" floodmaps in 010_DAMAGES
print(f"Flood maps directory: {flood_maps_directory}")

# directory for damage function tables
directory_flood_damage_curves = database_directory / '001_DAMAGE_TABLES'
print(f"Flood damage curves directory: {directory_flood_damage_curves}")

# EXPOSURE DATA  
exposure_directory = datadir_damages / SITE / 'exposure'
file_roads = exposure_directory / 'roads_clipped.gpkg'

clipped_buildings_directory = output_root / SITE / '011_Joined_NSI_to_Buildings' 
nsi_buildings_file = clipped_buildings_directory / 'buildings_with_cba_study_areas.gpkg'
print(f"NSI buildings file: {nsi_buildings_file}")

# In case these directories have not been created, create them:
for adir in [output_folder]:
    if not adir.exists():
        adir.mkdir(parents=True, exist_ok=True)

#################################################################################################################################################################
# load datasets 
# #################################################################################################
# roads
road_gdf = gpd.read_file(file_roads)
if road_gdf.empty:
    raise ValueError("Road GeoDataFrame is empty.")

#  DAMAGE FUNCTION TABLES:
# Structural damage function:
structure_damage_function_table_filepath = directory_flood_damage_curves / 'flBldgStructDmgFn_nsi_2022.csv'
structure_damage_function_table = pd.read_csv(structure_damage_function_table_filepath)
print(structure_damage_function_table.head())

# Contents damage function:
contents_damage_function_table_filepath = directory_flood_damage_curves / 'flBldgContDmgFn_nsi_2022.csv'
contents_damage_function_table = pd.read_csv(contents_damage_function_table_filepath)

#  NSI data file from exposure directory
output_gdf_distinct_occtype_gdf = gpd.read_file(nsi_buildings_file)
print(f"Read NSI data file from exposure directory...")
if output_gdf_distinct_occtype_gdf['geometry'].isnull().any():
    raise ValueError("Some geometries in the GeoDataFrame are invalid.")

# Check if coordinate references system (CRS) of road_gdf matches that of output_gdf_distinct_occtype_gdf
if road_gdf.crs and output_gdf_distinct_occtype_gdf.crs and road_gdf.crs != output_gdf_distinct_occtype_gdf.crs:
    road_gdf = road_gdf.to_crs(output_gdf_distinct_occtype_gdf.crs)

#---------------------------------------------------------------------------------------------------------------
# DEFINE RETURN PERIODS AND DEM YEARS TO PROCESS:
# check if any flood map is missing 
adaptation_names = get_adaptation_names(SITE)

# Normalize adaptation keys and print mapping
if isinstance(adaptation_names, dict):
    adapt_keys = list(adaptation_names.keys())
    for adaptkey in adapt_keys:
        print(f"{adaptkey} -> {adaptation_names[adaptkey]}")
else:
    adapt_keys = list(adaptation_names)
    for adaptkey in adapt_keys:
        print(f"{adaptkey}")

# Check for missing indirect damages files
missing = []
search_root = flood_maps_directory
for adaptkey, rp, dem in product(adapt_keys, RP_list, DEM_list):
    filename = f"{site_number}_{dem}_rp{rp:03d}_adapt{adaptkey}_mode{MODE}_hmax.tif" 
    if not any(search_root.rglob(filename)):
        missing.append(filename)

if missing:
    print(f"Missing {len(missing)} flood map files:")
    for fn in missing[:10]:
        print(f"  {fn}")
    if len(missing) > 10:
        print(f"  ... {len(missing) - 10} more")
    raise FileNotFoundError("Flood maps missing.")
else:
    print("All flood maps files found for all (adaptation, rp, dem) combinations.")

#################################################################################################
# PROCESS FLOOD MAPS AND CALCULATE DAMAGES 
#################################################################################################
#The following lines process a list of flood map files, calculate flood damages for buildings and roads, and save the results.

# FLOOD MAP FILES
# Locate all flood map files (in .tif format) within the specified directory

#flood_maps_pattern = str(flood_maps_directory / f'*.tif') # NOTE THAT applies the calculation to all the tiff files!!! 
flood_maps_pattern = f"{site_number}_*_mode{MODE}_hmax.tif" # find the MODE in the flood maps directory, e.g. site001_dem020_rp005_adapt000_mode001_hmax.tif
flood_map_filepaths = glob.glob(os.path.join(flood_maps_directory,flood_maps_pattern)) # finds all the flood map files that match the pattern in the flood maps directory

# Add a check to ensure that flood_map_filepaths is not empty:
if not flood_map_filepaths:
    raise FileNotFoundError(f"No flood map files found in {flood_maps_directory}")
else:
    print(f"Found flood map files: {len(flood_map_filepaths)} flood map files found.")

# Start timer to track processing time for the following operation:
time_start = time.time() 

# loop over return periods and dem years
damages = []
for rp, dem in product(RP_list, DEM_list):
    pass

for index, flood_map_filepath in enumerate(tqdm(flood_map_filepaths, desc="Processing flood maps", total=len(flood_map_filepaths), leave=False)): # iterate over flood map files
    
    # Print progress and time taken: 
    print(f"Analysis is {round(index/len(flood_map_filepaths)*100, 1)} % complete, time taken: {round((time.time() - time_start)/60, 1)} minutes") 
    flood_map_name = os.path.basename(flood_map_filepath).split('.')[0]

    # Extract Flood Map Name
    output_filename = os.path.basename(flood_map_filepath).split('.')[0]
    if (output_folder / f'{output_filename}.gpkg').exists() and not OVERWRITE:
        print(f'{output_filename} already exists')
        continue

    # Open flood map (as a raster object) using rioxarray
    flood_map_rio = rioxarray.open_rasterio(flood_map_filepath)
    flood_map_rio.rio.write_nodata(np.nan)
    flood_map_rio = flood_map_rio.fillna(0)

    # Validate flood map (ensure flood map is valid before proceeding)
    if flood_map_rio is None:
        raise ValueError("Flood map raster data is invalid.")
    if flood_map_rio[0,:,:].values is None:
        raise ValueError("Flood map raster data is invalid.")

    #Check if flood map and building data have the same coordinate reference system (CRS). Reproject if necessary.
    if flood_map_rio.rio.crs and output_gdf_distinct_occtype_gdf.crs:
        if flood_map_rio.rio.crs != output_gdf_distinct_occtype_gdf.crs:
            flood_map_rio = flood_map_rio.rio.reproject(output_gdf_distinct_occtype_gdf.crs)
    else:
        raise ValueError("CRS is missing for either the flood map or the building data.")

    #now we want to intersect the flood map with the output_gdf_distinct_occtype_gdf for each record and get the mean flood depth (zonal statistics)
    
    # Calculate mean flood depth:
        #Initialize the mean_flood_depth column:
    # output_gdf_distinct_occtype_gdf['mean_flood_depth'] = None
    # print('Calculating mean flood depth...')
    
    # #Calculate the mean flood depth for each building geometry using zonal statistics
    # output_gdf_distinct_occtype_gdf['mean_flood_depth'] = pd.DataFrame(
    #     zonal_stats(
    #         vectors=output_gdf_distinct_occtype_gdf['geometry'],
    #         raster=flood_map_rio[0,:,:].values,
    #         affine=flood_map_rio.rio.transform(),
    #         stats='mean', # using mean water depth
    #         nodata=np.nan  # this is just to hide a warning really, all nan values are previously changed to 0

    #     )
    # )['mean']

    # CALCULATE MAXIMUM FLOOD DEPTH PER BUILDING FOOTPRINT:
    # Calculate the mean flood depth for each building geometry using zonal statistics
    print('Calculating max flood depth...')
    output_gdf_distinct_occtype_gdf['max_flood_depth'] = pd.DataFrame(
        zonal_stats(
            vectors=output_gdf_distinct_occtype_gdf['geometry'],
            raster=flood_map_rio[0,:,:].values,
            affine=flood_map_rio.rio.transform(),
            stats='max', # using mean water depth
            #nodata=np.nan  # this is just to hide a warning really, all nan values are previously changed to 0
            all_touched=True  # Include pixels that touch the geometry
        )
    )['max']
    
    # Filter buildings with flood depth > 0.
    output_gdf_distinct_occtype_gdf_filtered = output_gdf_distinct_occtype_gdf[output_gdf_distinct_occtype_gdf['max_flood_depth'] > 0].copy()
    print(f"Buildings with flood depth > 0: {len(output_gdf_distinct_occtype_gdf_filtered)}")

    # Specific Occupancy Identifier (SOccupId) Generation
    output_gdf_distinct_occtype_gdf_filtered['SOccupId'] = None
    valid_soccupids = set(structure_damage_function_table['SOccupId'].unique()) 
    if not valid_soccupids:
        raise ValueError("No valid SOccupIds found in the structure damage function table.")

    #parsing all the records in the output_gdf_distinct_occtype_gdf_filtered to get the SOccupId
    # Generate SOccupId for Each Building
        # Generates a specific occupancy ID (SOccupId) for each building based on its attributes.
        # Validates the generated SOccupId against the damage function table.
    for index, occ in tqdm(output_gdf_distinct_occtype_gdf_filtered.iterrows()): #create function and pull out***

        OC = occ['occtype'].split('-')[0]
        foundation_type = occ['found_type']
        num_stories = occ['num_story']

        sopre = OC[:1]+OC[-(len(OC)-3):] if OC != 'REL1' else 'RE1' #move the if into it's own line to be human readable
        name_long = sopre +'-'+OC+'-'+foundation_type+'-'+str(num_stories)
        
        # Suffix: Easy - Basement or no Basement
        #UKS - use the value 4 as a number not string
        sosuf = 'B' if foundation_type == 'B' else 'N' #Brook changed this to B from 4

        # Middle Character: Number of Stories
        if OC[:4] == 'RES3':
            # RES3 has three categories: 1 3 5
            somid = '5' if num_stories > 4 else '3' if num_stories > 2 else '1'
        elif OC[:4] == 'RES1':
            # If NumStories is not an integer, assume Split Level residence
            # Also, cap it at 3.
            num_stories = 3 if num_stories > 3.0 else num_stories
            somid = str(round(num_stories)) if num_stories - round(num_stories) == 0 else 'S'

            if occ['occtype'].startswith('RES1-'):#my addition below
                # Extract the story number from occtype (2nd character after RES1-)
                # the occtype is more accurate than the num_stories so this is a check and correction
                # 3,051 out of 93,160,167 RES1 homes have this mismatch between the occtype and the num_stories that gets corrected by this block
                story_from_occtype = occ['occtype'].split('-')[1][0]
                if story_from_occtype.isdigit() and story_from_occtype != somid:
                    warnings.warn(f"{occ['occtype']} story mismatch corrected")
                    somid = story_from_occtype

            #my addition below, however it might not be needed as split homes don't exist in the NSI 2022 dataset, 
            #I checked all the states three times and then are int levels of stories not split (half levels)
            if len(occ['occtype'].split('-')) > 1:
                check_for_level_split = occ['occtype'].split('-')[1]
                if (check_for_level_split[0:1] == 'SL'):
                    somid = 'S'
                    print(f"Split level found for {name_long}")
        elif OC[:4] == 'RES2':
            # Manufactured Housing is by definition limited to one story
            somid = '1'
        else:
            # All other cases: Easy!  1-3, 4-7, 8+
            somid = 'H' if num_stories > 6 else 'M' if num_stories > 3 else 'L'

        SpecificOccupId = sopre + somid + sosuf
        # Check if the generatd SOccupId is in the damage_function_table
        if SpecificOccupId not in valid_soccupids:
            raise ValueError(f"Generated SOccupId '{SpecificOccupId}' not found in damage functions for record {index}")

        output_gdf_distinct_occtype_gdf_filtered.loc[index, 'SOccupId'] = SpecificOccupId
        #print(f"Generated SOccupId: {SpecificOccupId} for record {index}")

    # Initialize the damage columns
    building_and_function = output_gdf_distinct_occtype_gdf_filtered.copy(deep=True)#check if it's a deep copy or a shallow copy***
    building_and_function['structure_damage_percentage'] = None
    building_and_function['BldgDmgFnID'] = None
    building_and_function['contents_damage_percentage'] = None
    building_and_function['ContDmgFnID'] = None

    # Calculate Damage Percentages
        # Calculates the structure and contents damage percentages for each building using the damage function tables.

    for index, building in building_and_function.iterrows():
        structure_damage_pct, BldgDmgFnID = calculate_damage_percentage_from_lookup_table(building, structure_damage_function_table)
        building_and_function.loc[index, 'structure_damage_percentage'] = structure_damage_pct
        building_and_function.loc[index, 'BldgDmgFnID'] = BldgDmgFnID
        
        contents_damage_pct, ContDmgFnID = calculate_damage_percentage_from_lookup_table(building, contents_damage_function_table)
        building_and_function.loc[index, 'contents_damage_percentage'] = contents_damage_pct
        building_and_function.loc[index, 'ContDmgFnID'] = ContDmgFnID

    # Calculate Damage Values
        #  structural damage values:
    building_and_function['structure_damage_value'] = building_and_function['structure_damage_percentage']/100 * building_and_function['val_struct']
        # Calculate contents damage values:
    building_and_function['contents_damage_value'] = building_and_function['contents_damage_percentage']/100 * building_and_function['val_cont']

    # update USD value to 2025 dollars 
    building_and_function['structure_damage_value'] = building_and_function['structure_damage_value'] * USD_VALUE_UPDATE
    building_and_function['contents_damage_value'] = building_and_function['contents_damage_value'] * USD_VALUE_UPDATE
    building_and_function['val_struct'] = building_and_function['val_struct'] * USD_VALUE_UPDATE
    building_and_function['val_cont'] = building_and_function['val_cont'] * USD_VALUE_UPDATE
    building_and_function['val_vehic'] = building_and_function['val_vehic'] * USD_VALUE_UPDATE

    building_and_function['population']= building_and_function['students'] + building_and_function['pop2amu65'] + building_and_function['pop2amo65'] 
    #building_and_function['building_count'] = 1
    
    # Prepare Data for CSV Export:
       # This line creates a new DataFrame (building_and_function_to_csv) containing only the columns needed for export to a CSV file.
    building_and_function_to_csv = building_and_function[['cba_study_area',
                                                          'fid_building', 'occtype', 'num_story', 'found_type', 
                                                          'BldgDmgFnID', 'structure_damage_percentage', 'structure_damage_value', 
                                                          'ContDmgFnID', 'contents_damage_percentage', 'contents_damage_value', 
                                                          'max_flood_depth',
                                                          'val_struct', 'val_cont', 'val_vehic', 
                                                          'students', 'pop2amu65', 'pop2amo65', 'pop2pmu65', 'pop2pmo65',
                                                          'population', 
                                                          'sqft', 'number_of_units_aggregated']].copy(deep=True)
   
    # Calculate Road Damages:
        # Calculates road damage based on the length of flooded roads.
    road_damage_record, road_clipped_gdf = get_road_damage_by_buildings(road_gdf, flood_map_rio, road_damage_value_per_meter)
        # Append the road damage data to the building damage data.
    building_and_function_to_csv = pd.concat([building_and_function_to_csv, road_damage_record], ignore_index=True, sort=False)
    
    # OUTPUT ############################################################################################################################################
    # Save the road_clipped_gdf to a gpkg    
    road_clipped_gdf.to_file(output_folder / f'{output_filename}_road_clipped.gpkg', driver='GPKG')

    # Save the building damages to a csv
    building_and_function_to_csv.to_csv(output_folder / f'{output_filename}_damages_and_roads.csv', index=False)

    # convert all the columns that appear as numeric to numeric
    numeric_cols = building_and_function.select_dtypes(include=['number']).columns
    string_cols = building_and_function.select_dtypes(include=['object']).columns
    for col in string_cols:
        try:
            building_and_function[col] = pd.to_numeric(building_and_function[col])
        except (ValueError, TypeError):
            pass

    # Save building damage data to gpkg file:
    building_and_function.to_file(output_folder / f'{output_filename}.gpkg', driver='GPKG')

print(f"S020 - Finished running successfully for {SITE} using flood maps of type {MODE}.")
print(f"Output files written to {output_folder}.")
print('end of script')
