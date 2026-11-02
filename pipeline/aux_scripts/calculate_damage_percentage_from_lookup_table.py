# calculate_damage_percentage_from_lookup_table.py
# This function, calculate_damage_percentage_from_lookup_table, calculates the damage percentage and 
# retrieves the damage function ID for a building based on its attributes and flood depth.
# Created by Marina on November 9, 2025
# breguero@ucsc.edu 10.12.2025

import numpy as np
import pandas as pd
import warnings

def calculate_damage_percentage_from_lookup_table(building, damage_function_table):
        #3.28084 feet in a meter, sorry :D
        if 'max_flood_depth' in building and pd.notna(building['max_flood_depth']):
            flood_depth_m = building['max_flood_depth']
        elif 'mean_flood_depth' in building and pd.notna(building['mean_flood_depth']):
            flood_depth_m = building['mean_flood_depth']
        else:
            raise ValueError("building does not contain a usable flood depth value")

        flood_depth_ft = flood_depth_m * 3.28084 #we could also do a lookup table for conversions but it would be more lines of code
        if flood_depth_ft < 3:
            selected_damage_function = damage_function_table[
                (damage_function_table['occtype'] == building['occtype']) & 
                (damage_function_table['SOccupId'] == building['SOccupId']) & 
                (damage_function_table['HazardR'] == True)] #also called Hazard A (not sure why)
        elif flood_depth_ft >= 3 and flood_depth_ft < 6:
            selected_damage_function = damage_function_table[
                (damage_function_table['occtype'] == building['occtype']) &
                (damage_function_table['SOccupId'] == building['SOccupId']) &
                (damage_function_table['HazardCA'] == True)]
        elif flood_depth_ft >= 6:
            selected_damage_function = damage_function_table[
                (damage_function_table['occtype'] == building['occtype']) & 
                (damage_function_table['SOccupId'] == building['SOccupId']) & 
                (damage_function_table['HazardCV'] == True)]
        else:
            raise ValueError(f"the flood depth is {flood_depth_ft} feet and did not find a damage function for it")

        if selected_damage_function.empty:
            print(f"the flood depth is {flood_depth_m} is empty")
            print(f"the building is {building['occtype']} {building['SOccupId']} {building['found_type']} {building['num_story']}")
            print(f"the choosen function is {selected_damage_function}")
            raise ValueError(f"the flood depth is {flood_depth_m} is empty")

        depth_cols = selected_damage_function.loc[:, 'ft04m':'ft24'].columns #selects columns from -4ft to 24ft depth
        #add a value error if the length is wrong of the depth_cols
        if len(depth_cols) != 29:
            raise ValueError(f"the depth columns are not correct, they are {len(depth_cols)}")

        depth_values_ft = [-float(col.replace('ft', '').replace('m', '')) if 'm' in col else float(col.replace('ft', '')) for col in depth_cols]

        if len(selected_damage_function) > 1:
            warnings.warn(f"the flood depth is {flood_depth_m} is not unique, picking the first damage function")

        damage_values = selected_damage_function.loc[:, 'ft04m':'ft24'].values[0] #in case there is more than one row in the selected_damage_function
        damage_percentage = np.interp(flood_depth_ft, depth_values_ft, damage_values)#interpolates the damage percentage based on the flood depth

        #we need to be able to grab either the BldgDmgFnID or the ContDmgFnId depending on the lookup table
        if 'BldgDmgFnID' in selected_damage_function.columns:
            DmgFnID = selected_damage_function['BldgDmgFnID'].values[0]
        elif 'ContDmgFnId' in selected_damage_function.columns:
            DmgFnID = selected_damage_function['ContDmgFnId'].values[0]
        else:
            print(f"columns are {selected_damage_function.columns}")
            raise ValueError(f"the lookup table is not supported")
        
        return damage_percentage, DmgFnID