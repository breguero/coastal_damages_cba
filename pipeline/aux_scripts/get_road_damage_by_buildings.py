# get_road_damage_by_buildings.py
#This function, get_road_damage_by_buildings, calculates the total damage to roads caused by flooding based 
# on the intersection of road geometries with flooded areas. It returns a DataFrame summarizing the road 
# damage and a GeoDataFrame of the clipped road geometries within the flooded area.
#
# Created by Marina on November 9, 2025 
# breguero@ucsc.edu 10.12.2025

import pandas as pd
import geopandas as gpd
import numpy as np
from rasterio import features
from shapely.geometry import shape

def get_road_damage_by_buildings(road_gdf, flood_map_rio, road_damage_value_per_meter):
    
    flood_mask = flood_map_rio.fillna(0)[0].values > 0
    flood_polys = [shape(geom) for geom, _ in features.shapes(
        flood_map_rio[0].values, mask=flood_mask, transform=flood_map_rio.rio.transform()
    )]
    
    if not flood_polys:
        road_length = 0
    else:
        flood_gdf = gpd.GeoDataFrame(geometry=flood_polys, crs=flood_map_rio.rio.crs)
        if road_gdf.crs != flood_gdf.crs:
            flood_gdf = flood_gdf.to_crs(road_gdf.crs)
        
        road_clipped_gdf = gpd.overlay(road_gdf, flood_gdf, how='intersection')
        road_length = road_clipped_gdf.geometry.length.sum()
    
    return pd.DataFrame({
        'occtype': ['ROAD'], 
        'structure_damage_value': [road_damage_value_per_meter * road_length],
        **{col: [np.nan] for col in ['fid_building', 'num_story', 'found_type', 'BldgDmgFnID', 
                                   'structure_damage_percentage', 'ContDmgFnID', 'contents_damage_percentage', 
                                   'contents_damage_value', 'mean_flood_depth', 'val_struct', 'val_cont', 
                                   'val_vehic', 'students', 'pop2amu65', 'pop2amo65', 'pop2pmu65', 
                                   'pop2pmo65', 'sqft', 'number_of_units_aggregated']}
    }), road_clipped_gdf
