###############################################################################################
# interpolate_recovery_time.py
# Created by Marina Rottmueller on November 20, 2025
# Based on the R script damages.R from Drishan
#
# Script description:
#   function to interpolate the maximum recovery time based on building occupancy type and flood depth.
#
# modified by breguero@ucsc.edu 
#################################################################################################


## IMPORT PACKAGES, LIBRARIES AND LINK other .py-scripts
import pandas as pd
import numpy as np

def interpolate_recovery_time(occtype_val, depth_ft, recovery_table):
    """
    Return interpolated max_recovery_time for occtype_val at depth_ft (feet).
    Mirrors the R approx(...) behaviour used in damages.R.
    """
    df = recovery_table[recovery_table["occtype"] == occtype_val].copy()
    df = df.sort_values("flood_severity")
    if len(df) < 2:
        return np.nan
    x = df["flood_severity"].to_numpy()
    y = df["max_recovery_time"].to_numpy()
    # edge cases: return nearest endpoint
    if depth_ft <= x[0]:
        return float(y[0])
    if depth_ft >= x[-1]:
        return float(y[-1])
    # interpolate
    return float(np.interp(depth_ft, x, y))
