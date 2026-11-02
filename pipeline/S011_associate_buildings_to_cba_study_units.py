#################################################################################################################
#   Script description:                                                                                         
#   spatial join of buildings with the cba aggregation units (cba study areas)
#   Output: 
#          geopackage with buildings associated to cba study areas
#                                                                                                               
#   breguero@ucsc.edu 01/07/2026
# ###############################################################################################################                                                                                                          

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
import matplotlib.pyplot as plt

#################################################################################################################################################################
## Input directory for datasets:

##These are the four sites we want to run in general for Cosmos Adapts:
SITE = RUN_SITE  # set with COSMOS_SITE or run_pipeline.py --site
#SITE = 'site001_santacruz'  # comment if running from terminal 
#SITE = 'site002_halfmoonbay'  # comment if running from terminal
#SITE = 'site003_venturanorth'  # comment if running from terminal
#SITE = 'site004_venturanorth2' 

if SITE not in ['site001_santacruz2','site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', 'site004_venturanorth2']:
    raise ValueError(f"region_name {SITE} not recognized. Please choose from 'site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', or 'site004_venturanorth2'.")    

#################################################################################################################################################################
#buildings_file_path = project_root_directory / datadir_damages / SITE / 'exposure' / 'nsi_to_buildings_proj_all_occtype.gpkg'
joined_buildings_dir = output_root / SITE / '011_Joined_NSI_to_Buildings' 
buildings_file_path = joined_buildings_dir / 'nsi_to_buildings_proj_all_occtype.gpkg' # output of S010 
buildings = gpd.read_file(buildings_file_path)

# output results directory for this script:
output_dir = joined_buildings_dir 

# cba areas 
cba_areas_file_path = project_root_directory / datadir_damages / SITE / 'cba_study_areas' / 'cba_study_area.gpkg'
cba_areas = gpd.read_file(cba_areas_file_path)
# Reproject CBA areas to match buildings CRS if needed
if cba_areas.crs != buildings.crs:
    cba_areas = cba_areas.to_crs(buildings.crs)

# figure 
# Quick plot of buildings and CBA areas and save to file
fig, ax = plt.subplots(figsize=(10, 10))
cba_areas.plot(ax=ax, edgecolor="tab:red", facecolor="none", linewidth=0.8)
buildings.plot(ax=ax, edgecolor="black", facecolor="none", linewidth=0.2)
ax.set_title(f"Buildings + CBA Study Areas - {SITE}")
ax.set_axis_off()

fig_dir = output_dir 
os.makedirs(fig_dir, exist_ok=True)
fig.savefig(fig_dir / "buildings_overview.png", dpi=200, bbox_inches="tight")
plt.show() 
plt.close(fig)

# drop index_right if exists
if 'index_right' in buildings.columns:
    buildings = buildings.drop(columns=['index_right'])
if 'index_right' in cba_areas.columns:
    cba_areas = cba_areas.drop(columns=['index_right'])

# spatial join 
buildings_cba = gpd.sjoin(buildings, cba_areas, how="left", predicate="intersects")
buildings_cba = buildings_cba[buildings_cba["cba_study_area"].notna()]
buildings_cba.columns

#check if fid_building is in multiple cba_study_areas:
for fid_building in buildings_cba["fid_building"].unique():
    if buildings_cba[buildings_cba["fid_building"] == fid_building]["cba_study_area"].nunique() > 1:
        print(fid_building)

buildings_cba = buildings_cba.drop_duplicates(subset=["fid_building"])

buildings_cba.filter(["fid_building", "cba_study_area"]).to_csv(os.path.join(output_dir, "fid_building_cba_study_area_join_table.csv"), index=False)

file_out = output_dir / 'buildings_with_cba_study_areas.gpkg'
buildings_cba.to_file(file_out, driver="GPKG")
print(f"S011 successfully completed for region: {file_out}")
print('--------------- \n end of script')
