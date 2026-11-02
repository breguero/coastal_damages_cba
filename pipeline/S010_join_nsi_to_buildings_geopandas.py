
#################################################################################################################
#   S001_join_nsi_to_buildings_geopandas.py                                                                       
#       - Based on the script D001b_join_nsi_to_buildings_geopandas.py from Brook.                               
#       - Improved with code structure and code fragments from NBS Adapts code from David                      
#       - Marina renamed this script to S001_join_nsi_to_buildings_geopandas.py on November 1, 2025             
#                                                                                                               
#   Script description:                                                                                         
#   The script S001_join_nsi_to_buildings_geopandas.py performs a spatial join                                 
#   between two geospatial datasets: NSI (National Structure Inventory) data and building footprint data.       
#   It processes these datasets to align their coordinate reference systems (CRS), performs spatial             
#   operations, and outputs a GeoPackage file containing the joined data.    
#   Marina 
#   Modified by Borja 12.10.2025
# ###############################################################################################################                                                                                                          
#from S000_project_definition import * #From Marina based on NBS adapts code from David
from S000_project_config_cosmos_adapt import * 
import geopandas as gpd
import pandas as pd
import logging #From Marina based on NBS adapts code from David
import logging.handlers #From Marina based on NBS adapts code from David
import os
import numpy as np
#import rioxarray
import glob
import sys
import rasterio

#################################################################################################################################################################
## Input directory for datasets:
DIRDATA = datadir_damages #from S000_project_config_cosmos_adapt.py

# Load dataset for NSI and for Microsoft Buildings:

##These are the four sites we want to run in general for Cosmos Adapts:
    # SITE = 'site001_santacruz' 
    # SITE = 'site002_halfmoonbay' 
    # SITE = 'site003_venturanorth'

# REGION NAME 
SITE = RUN_SITE  # set with COSMOS_SITE or run_pipeline.py --site
#SITE = 'site001_santacruz'
#SITE = 'site002_halfmoonbay' 
#SITE = 'site003_venturanorth'
#SITE = 'site004_venturanorth2'
site_number = SITE.split('_')[0] # extract site number from region name, e.g. site001

## Flood Map Path
flood_map_path          = datadir_damages / SITE / 'flood_map_sims' 

# Create the output folder 
output_folder = output_root / SITE / '011_Joined_NSI_to_Buildings'
os.makedirs(output_folder, exist_ok=True)  #Creates the output folder if it does not already exist.     

#################################################################################################################################################################

# Retrieve the path to the first .tif file (a raster file, likely a flood map) in the specified flood_map_path directory.
name_code = f'{site_number}*_mode001_hmax.tif'  # site001_dem020_rp005_adapt000_mode001_hmax
get_crs_from_flood_raster = flood_map_path / glob.glob(os.path.join(flood_map_path, "*.tif"))[0] 

#Open a raster file (likely a flood map) and extract its Coordinate Reference System (CRS).
with rasterio.open(get_crs_from_flood_raster) as src:
    crs_flood_raster = src.crs
#with rioxarray.open_rasterio(get_crs_from_flood_raster) as src:
#    crs_flood_raster = src.rio.crs

#################################################################################################################################################################
## NSI dataset:

# read the NSI dataset from a GeoPackage file, which contains geospatial data about structures (e.g., buildings) with associated attributes.
nsi_filepath = datadir_damages / SITE / 'exposure' / 'nsi_subset.gpkg' 
nsi_gdf = gpd.read_file(nsi_filepath)

# Ensure the NSI GeoDataFrame uses the same CRS as the flood raster -> Print both coordinate systems
print(f"nsi_gdf coordinate references system: {nsi_gdf.crs}")
print(f"flood_raster coordinate reference system: {crs_flood_raster}")

# if not - Reproject
#if nsi_gdf.crs != crs_flood_raster:
#    nsi_gdf = nsi_gdf.to_crs(crs_flood_raster)
#    print("nsi_gdf reprojected to match flood_raster CRS")

#################################################################################################################################################################
## Building dataset:

#building_filepath = os.path.join(DIRDATA, SITE, 'exposure', 'buildings_subset.gpkg') #***create building_001 and building_002 as needed for each region
building_filepath = DIRDATA / SITE / 'exposure' / 'buildings_subset.gpkg' #by Marina

#Load the building footprint data from a GeoPackage file, then reproject it to match the Coordinate Reference System (CRS) of the flood raster:
buildings_gdf = gpd.read_file(building_filepath)
buildings_gdf = buildings_gdf.to_crs(crs_flood_raster)

# Create a new column, fid_building, in the buildings_gdf GeoDataFrame to serve as a unique identifier for each building:
# Since buildings_gdf doesn't have an 'fid' column, create one using the index
buildings_gdf.reset_index(drop=True, inplace=True)  # Ensure clean index
buildings_gdf['fid_building'] = buildings_gdf.index  # Use index as building ID

# Check for duplicate values in the fid_building column and raises an error if any are found.
if buildings_gdf['fid_building'].duplicated().any():
    raise ValueError("duplicate fid_building values found in buildings_gdf")

#################################################################################################################################################################
## Run spatial join of NSI dataset and Buildings dataset:
# Perform a spatial join between the NSI GeoDataFrame (nsi_gdf) and the building footprint GeoDataFrame (buildings_gdf) based on proximity
    # nsi_gdf: the left GeoDataFrame, which contains the NSI (National Structure Inventory) data. These are point geometries representing structures (e.g., buildings) 
    #   with associated attributes.
    # buildings_gdf: the right GeoDataFrame, which contains the building footprint data. These are polygon geometries representing the shapes of buildings.
    # use an inner join: Only includes rows where a match is found between nsi_gdf and buildings_gdf within the specified distance
    # max_distance=50: Limit the join to only include matches where the distance between the NSI point and the nearest building polygon is 50 meters or less.
    # distance_col='distance_m': Add a new column, distance_m, to the resulting GeoDataFrame (output_gdf), which stores the distance (in meters) between the 
    #   matched NSI point and the nearest building.
print("... running spatial join...")
# Ensure NSI GeoDataFrame uses the same CRS as buildings and flood raster

# Verify both have matching CRS before spatial join
if nsi_gdf.crs != buildings_gdf.crs:
    nsi_gdf = nsi_gdf.to_crs(buildings_gdf.crs)
print(f"nsi_gdf CRS: {nsi_gdf.crs}")
print(f"buildings_gdf CRS: {buildings_gdf.crs}")
# spatial join 
output_gdf = gpd.sjoin_nearest(nsi_gdf, buildings_gdf, how='inner', max_distance=50, distance_col='distance_m')
# Check if output_gdf has any entries
if output_gdf.empty:
    raise ValueError("Error: output_gdf is empty. No matches found between NSI points and buildings.")

# output_gdf: a new GeoDataFrame containing the result of the spatial join. Each row in output_gdf represents an NSI point (nsi_gdf) matched to its nearest 
# building footprint (buildings_gdf). Includes columns from both nsi_gdf and buildings_gdf, as well as the distance_m column. 

# Print the number of rows in the output GeoDataFrame resulting from the spatial join, aka the number of matched NSI points to buildings.
print('Number of matched NSI points to buildings:', len(output_gdf))
#Take the polygon geometry from the buildings_gdf and replace them geom in output_gdf which is just nsi points right now. 
building_geoms = buildings_gdf.set_index('fid_building')['geometry']
output_gdf['geometry'] = output_gdf['fid_building'].map(building_geoms)
# The geometry column in output_gdf now contains the polygon geometries of the matched buildings, replacing the original point geometries from the NSI data.

# Get unmatched NSI features
unmatched_nsi_gdf = nsi_gdf[~nsi_gdf['fd_id'].isin(output_gdf['fd_id'])]

# Print the number of NSI points that were not matched to any building:
print('Number of NSI points not matched to any building:', len(unmatched_nsi_gdf))

# Process NSI points that were not matched to any building during the spatial join.
unmatched_buffered_gdf = unmatched_nsi_gdf.copy()
#Replace the geometry column in unmatched_buffered_gdf with buffered geometries. 
unmatched_buffered_gdf['geometry'] = unmatched_nsi_gdf.geometry.buffer(10) #buffer by X meters

# Filter for polygon type, to remove any failed buffered points:
unmatched_buffered_gdf = unmatched_buffered_gdf[unmatched_buffered_gdf.geometry.type == 'Polygon']

#Give all the unmatched_buffered_gdf all unique negative numbers to avoid conflicts with the positive fid_building values
unmatched_buffered_gdf['fid_building'] = -1 * np.arange(1, len(unmatched_buffered_gdf) + 1)
output_gdf_append = pd.concat([output_gdf, unmatched_buffered_gdf])
output_gdf_append['number_of_units_aggregated'] = 1

#group by the fid_building, occtype, num_story, and found_type and sum the values of the columns
output_gdf_distinct_occtype = output_gdf_append.groupby(['fid_building', 'occtype', 'num_story', 'found_type']).agg({
    'val_struct': 'sum',
    'val_cont': 'sum',
    'val_vehic': 'sum',
    'students': 'sum',
    'pop2amu65': 'sum',
    'pop2amo65': 'sum',
    'pop2pmu65': 'sum',
    'pop2pmo65': 'sum',
    'sqft': 'sum',
    #'number_of_units_aggregated' is the number of units in the building, we need to count the number of units in the building
    'number_of_units_aggregated': 'sum',
    # 'o65disable': 'sum', #these are percentages and should not be summed, we could get the mean but they are summarized at the county level so it shouldn't matter...
    # 'u65disable': 'sum',
    'geometry': 'first'
}).reset_index()

# Convert the aggregated DataFrame into a GeoDataFrame and set its Coordinate Reference System (CRS). 
output_gdf_distinct_occtype_gdf = gpd.GeoDataFrame(output_gdf_distinct_occtype)
output_gdf_distinct_occtype_gdf.crs = nsi_gdf.crs#.set_crs(nsi_gdf.crs) try this to see if it works better***

#########################################################################################################################################################
# OUTPUT:

# Define the Output File Path
filepath = output_folder / 'nsi_to_buildings_proj_all_occtype.gpkg' 
# Remove Existing File (if any)
if os.path.exists(filepath): #Checks if a file already exists at the specified path
    os.remove(filepath) #Deletes the existing file if it exists.

#Save the GeoDataFrame:
output_gdf_distinct_occtype_gdf.to_file(filepath, driver='GPKG')

print(f"Output file written to {filepath}.")
print(f"S001 successfully completed for region: {SITE}")
