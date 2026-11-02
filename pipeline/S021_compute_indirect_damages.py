#################################################################################################################
#                                                                                                                              
#   S021_compute_indirect_damages.py                                                                               
#                                                                                                                
#   Created by Marina Rottmueller on November 1, 2025                                                          
#       - Based on the script R scripts from Drishan.                                                             
#       - Marina converted this R script into Python                                                              
#                                                                                                                                  
#   Script description:   (Still to be described in more detail-.- TBD-)                                        
#   This script calculates the indirect damages per scenario, and then creates csv files for each scenario     
#   that contain the direct damages, indirect damages, and total damages per building.                          
#   Input file(s): direct damage results as csv files per building per scenario per study area                  
#   Output files: csv files per scenario that summarize direct damages, indirect damages, and total damages     
#   per building.                                                                                               
#   
#  Dependencies:         
#       input: csv of direct damages from S020 
#       output: csv with the indirect and total damages --> to be used in subsequent scripts 
# 
#  breguero@ucsc.edu
#  01/04/2026
# ###############################################################################################################   

## IMPORT PACKAGES 
from S000_project_config_cosmos_adapt import *
from aux_scripts.calculate_damage_percentage_from_lookup_table import calculate_damage_percentage_from_lookup_table
from aux_scripts.get_road_damage_by_buildings import get_road_damage_by_buildings
from aux_scripts.interpolate_recovery_time import interpolate_recovery_time

import os
import sys
import pandas as pd
from pathlib import Path
import statsmodels.api as sm
import matplotlib.pyplot as plt
import numpy
import numpy as np
import geopandas as gpd

import openpyxl; print(openpyxl.__version__) # reads Excel files 

#################################################################################################################################################################

## MAIN SCRIPT EXECUTION:
## to run the script from the command line of the terminal:
# INTERACTIVE_RUN = False
# if len(sys.argv) < 2:
#     print('Usage: python S030_compute_indirect_damages.py [region_name]')
#     sys.exit(1)

# ----------------------------------------------------
# config 
##These are the four sites we want to run in general for Cosmos Adapts:
SITE = 'site001_santacruz2'
#SITE = 'site001_santacruz' #site_001, site_002? site is the parent dir so you don't need {site}_NSI folder***
#SITE = 'site002_halfmoonbay' 
# SITE = 'site003_venturanorth'
#SITE = 'site003_venturanorth'
#SITE = 'site004_venturanorth2'

# Mode (runs)  	
#   001: hydrodynamic only / DEM = 1, morpho = 0 
#   002: morphodynamic update enabled / DEM = 1, morpho = 1 
#   003: hydro without DEM change (bathy use dem020) / DEM = 0, morpho = 0 
#   004: morpho without DEM change (bathy use dem020) / DEM = 0, morpho = 1 	
MODE = '002' # check 000_scenario_convention_dictionary.doc 
# ----------------------------------------------------

# Print to show which site is being processed:
print(f"Calculating indirect damages for site: {SITE}")

# ----------------------------------------------------
if SITE not in ['site001_santacruz2','site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', 'site004_venturanorth2']:
    raise ValueError(f"region_name {SITE} not recognized. Please choose from 'site001_santacruz', 'site002_halfmoonbay', 'site003_venturanorth', or 'site004_venturanorth2'.")    
# ----------------------------------------------------

# zillow data 
zillow_path = indirectdamages_zillow_directory / "zillowrent.xlsx"
sheet_map = {
        "site001_santacruz2": "Santa Cruz",
        "site001_santacruz": "Santa Cruz",
        "site002_halfmoonbay": "Half Moon Bay",
        "site003_venturanorth": "Ventura county",
        "site004_venturanorth2": "Ventura county",
}
sheet_name = sheet_map.get(SITE)
if sheet_name is None:
    raise ValueError(f"Unknown SITE: {SITE}")

## LOAD INPUT DATASETS:

# Load direct damages datasets:
# Replace the single-file read with a loop over all input CSVs in the 020_DIRECT_DAMAGES_CSV folder.

input_dir = project_root_directory / damage_folder_outputs / SITE / '012_damages' / 'damages_by_buildings' / f'flood_map_{MODE}'
input_files = sorted(input_dir.glob("*_damages_and_roads.csv")) 

#Print: the input_dir has been found and contains how many files:
print(f"Input CSV files in {input_dir} contain {len(input_files)} files.")
if not input_files:
    raise FileNotFoundError(f"No input CSV files found in {input_dir}")

# dirout 
output_folder = project_root_directory / damage_folder_outputs / SITE / '012_damages' / 'indirect_damages' / f'flood_map_{MODE}'
if not output_folder.exists(): output_folder.mkdir(parents=True, exist_ok=True)

# Load input direct damages file, as well as Zillow rent data for scenario of a given region:
for direct_damages_input_path in input_files:
    print(f"Processing input file: {direct_damages_input_path}")
    direct_damages_input_data = pd.read_csv(str(direct_damages_input_path))
    
    # open geopackage too 
    name_gpkg = direct_damages_input_path.stem.replace("_damages_and_roads", ".gpkg")
    gpkg_path = input_dir / name_gpkg
    direct_damages_input_data_gpkg = gpd.read_file(str(gpkg_path))
    direct_damages_input_data_gpkg.columns

    # Validate required column presence
    if "max_flood_depth" not in direct_damages_input_data.columns and "mean_flood_depth" not in direct_damages_input_data.columns:
        raise ValueError(f"Required column 'max_flood_depth' not found in input file: {direct_damages_input_path.name}")
    print(f"Loaded direct damages input data from: {direct_damages_input_path} (shape={direct_damages_input_data.shape})")

    # Prefer the new S020 output column, but keep the old name as a fallback for older CSVs.
    flood_depth_column = "max_flood_depth" if "max_flood_depth" in direct_damages_input_data.columns else "mean_flood_depth"

    # -----------------------------------------------------------------------------------------------------------
    ## RENT ESTIMATION FOR RESIDENTIAL BUILDINGS 
    #  USING ZILLOW DATA AND OLS REGRESSION 
    # -----------------------------------------------------------------------------------------------------------
    # Load Zillow rent data:
    # load only the sheet needed for the current SITE
    zil = pd.read_excel(zillow_path, sheet_name=sheet_name)
    print(f"Loaded Zillow rent data for site: {SITE} from sheet: {sheet_name}")
    
    # Estimate rent for residential buildings (Zillow regressions) by doing a ordinary least squares regression (OLS_).
    # The overall form of such a OLS regression is:
    # y = beta * X + error
    # y = beta1 * X1 + beta2 * X2 + ... + betaN * XN + error

    # here:
    # rent ~ price + area(sq ft) + storey + blocks from the ocean ---
    # y = rent
    # X = [price; area (sq ft); storey; blocks from the ocean]
    # -----------------------------------------------------------------------------------------------------------
    print(f"Estimate the rent for residential building using Zillow data for site using an ordinary least squares regression: {SITE}")
    print(f"\n Run the full model...\n")
    #Allocating variables to prepare the OLS regression:
    # Dependent variable
    #y = pd.to_numeric(zil_sc["rent"], errors="coerce")
    y = pd.to_numeric(zil["rent"], errors="coerce")

    # Independent variables
    #X = zil_sc[["price", "storey", "blocks from the ocean", "area (sq ft)"]].copy()
    X = zil[["price", "storey", "blocks from the ocean", "area (sq ft)"]].copy()

    # Convert storey to numeric (like as.numeric(storey))
    X["storey"] = pd.to_numeric(X["storey"], errors="coerce")

    # Add intercept
    # Add an intercept column to the predictor matrix X so the regression includes a constant term.
    X = sm.add_constant(X)

    # Run OLS regression (full model):
    model_full = sm.OLS(y, X, missing="drop").fit()

    # Print the summary of the OLS regression (full model):
    print(model_full.summary())

    #-----------------------------------------------------------------------------------------------------------
    # Create a second OLS regression model with less parameters (reduced model)
    # Reduced model without 'storey' and 'blocks from the ocean' (not significant)
    # rent ~ price + area(sq ft)
    #-----------------------------------------------------------------------------------------------------------
    print(f"\n Run the reduced model...\n")

    #Allocating variables to prepare the OLS regression:
    # Dependent variable
    #y2 = pd.to_numeric(zil_sc["rent"], errors="coerce")
    y2 = pd.to_numeric(zil["rent"], errors="coerce")

    # Independent variables
    #X2 = zil_sc[["price", "area (sq ft)"]].copy()
    X2 = zil[["price", "area (sq ft)"]].copy()

    # Add intercept
    # Add an intercept column to the predictor matrix X so the regression includes a constant term.
    X2 = sm.add_constant(X2)

    # Run OLS regression (reduced model):
    model_reduced = sm.OLS(y2, X2, missing="drop").fit()

    # Print the summary of the OLS regression (reduced model):
    print(model_reduced.summary())

    # Extract coefficients from reduced model:
    alpha = model_reduced.params["const"]            # intercept
    beta_price = model_reduced.params["price"]
    beta_area  = model_reduced.params["area (sq ft)"]

    # Plot histogram of flood depth from direct damages input data (guard against missing/NaN data)
    if flood_depth_column in direct_damages_input_data.columns:
        mf = pd.to_numeric(direct_damages_input_data[flood_depth_column], errors="coerce")
        if mf.notna().any():
            plt.hist(mf.dropna(), bins=30, edgecolor="black")
            plt.xlabel(flood_depth_column)
            plt.ylabel("Frequency")
            plt.title("Histogram of Flood Depth")
            print("Created histogram of flood depth and frequency...")
            #out_dir = output_folder
            #out_dir.mkdir(parents=True, exist_ok=True)

            # Use the current input file's stem to create a short output filename
            input_stem = direct_damages_input_path.stem  # e.g. "site002_dem020_rp005_adapt000_mode001_hmax"
            out_path = output_folder / f"{flood_depth_column}_hist_{input_stem}.png"

            plt.savefig(str(out_path), bbox_inches="tight", dpi=150)
            print(f"Saved histogram to: {out_path}")
            plt.close()
        else:
            print(f"WARNING: '{flood_depth_column}' contains no finite values — skipping histogram.")
    else:
        print("WARNING: no flood depth column found — skipping histogram.")


    ############## MAXIMUM RECOVERY TIME ESTIMATION ##############
    ## Load max recovery time table:
    print("Compute now maximum recovery time...")
    path = Path(indirectdamages_max_recovery_time_directory/ 'max_recovery_time.csv')
    recovery_table = pd.read_csv(path)

    # Quick inspection of recovery table to make sure correct table loaded:
    print("\nLoading the first few rows of the recovery table for quality control:\n")
    print(recovery_table.head())

    # Step 1: Convert meters -> feet
    # Creates a new column named "flood_depth_ft" by converting meters → feet 
    # (multiplies the existing meters value in the selected flood depth column by meters_to_feet) — 
    # numeric result, NaNs preserved. 
    direct_damages_input_data['flood_depth_m'] = pd.to_numeric(direct_damages_input_data[flood_depth_column], errors='coerce')
    direct_damages_input_data['flood_depth_ft'] = direct_damages_input_data['flood_depth_m'] * meters_to_feet

    # Step 2: collapse occtype values starting with "RES1" to "RES1"
    # Find rows where occtype starts with "RES1" (regex ^RES1) and replaces those values
    # with the canonical string "RES1". The na=False prevents errors for missing values. 
    # This collapses variants like "RES1-2" to "RES1".
    mask = direct_damages_input_data['occtype'].str.match(r'^RES1', na=False)
    direct_damages_input_data.loc[mask, 'occtype'] = 'RES1'

    # Step 3:
    # Call the interpolate_recovery_time function to compute the time_for_recovery column:
    direct_damages_input_data["time_for_recovery"] = direct_damages_input_data.apply(
        lambda r: interpolate_recovery_time(r["occtype"], r["flood_depth_ft"], recovery_table),
        axis=1
    ) # Marina created this line to modify what CoPilot suggested so the 
    # interpolate_recovery_time.py function could be placed outside of script. 
    # Keep an eye on it to make sure the code runs correctly and does that it is 
    # supposed to do.

    print("For example the average recovery time for a flood depth of 1 ft for building occupation type RES1:", interpolate_recovery_time("RES1", 1, recovery_table), "[days].")

    ###########################################################################################################
    
    ## Estimate rent for all buildings based on occupancy type:

    ###########################################################################################################

    print("Estimating rent for all buildings based on occupancy type...")
    # Residential buildings: use regression coefficients from the fitted OLS
    # Commercial buildings: use retail rent-to-price ratio
    # Industrial buildings: use industrial rent-to-price ratio
    # coefficients from the fitted OLS (assumes these were extracted earlier):
    #   alpha_sc, beta_price_sc, beta_area_sc

    # create or alias the working dataframe (use the df variable you have; here I assume direct_damages_input_data)
    df = direct_damages_input_data

    # initialize rent column (preserve existing values when not matched)
    df["rent"] = df.get("rent", pd.Series(index=df.index, dtype=float))

    # Residential: use regression coefficients 
    # (rent_residential = Intercept + val_struct * beta_price + sqft * beta_area)
    mask_res = df["occtype"].str.match(r"^RES", na=False)
    df.loc[mask_res, "rent"] = (
        alpha
        + df.loc[mask_res, "val_struct"] * beta_price
        + df.loc[mask_res, "sqft"] * beta_area
    )

    # Commercial: use retail rent-to-price ratio 
    # (rent_commercial = val_struct * rpr_ret)
    mask_com = df["occtype"].str.match(r"^COM", na=False)
    df.loc[mask_com, "rent"] = df.loc[mask_com, "val_struct"] * rpr_ret # constant defined in S000_project_config_cosmos_adapt.py

    # Industrial: use industrial rent-to-price ratio
    # (rent_industrial = val_struct * rpr_ind)
    mask_ind = df["occtype"].str.match(r"^IND", na=False)
    df.loc[mask_ind, "rent"] = df.loc[mask_ind, "val_struct"] * rpr_ind # constant defined in S000_project_config_cosmos_adapt.py

    #############################################################################################
    # Ensure `categories` exists even if SITE != '001_santacruz' (prevent NameError)
    categories = np.array([])

    # Helper to map R 1-based category indices to Python values from `categories`
    def _cat(i):
        return categories[i - 1] if (1 <= i <= len(categories)) else None

    def _cats(idxs):
        return [categories[i - 1] for i in idxs if 1 <= i <= len(categories)]

    #############################################################################################

    # If SITE is '001_santacruz', apply special category-based rent estimation rules:

    if SITE == '001_santacruz':
        print("Applying special category-based rent estimation rules for site 001_santacruz...")
        if "use_code_std_desc_lps" in direct_damages_input_data.columns:
            categories = direct_damages_input_data["use_code_std_desc_lps"].unique()

            # debug prints (optional)
            print("present:", True)
            print("dtype:", direct_damages_input_data["use_code_std_desc_lps"].dtype)
            print("unique sample:", direct_damages_input_data["use_code_std_desc_lps"].dropna().unique()[:20])
            print(direct_damages_input_data["use_code_std_desc_lps"].value_counts(dropna=False).head(10))

            # helper to map R 1-based category indices to Python (0-based)
            def _cat(i):
                return categories[i - 1] if (1 <= i <= len(categories)) else None

            cat_12  = _cat(12)
            cat_22  = _cat(22)
            cat_43  = _cat(43)
            cat_36  = _cat(36)
            cat_42  = _cat(42)
            cat_55  = _cat(55)
            cat_39  = _cat(39)

            # 1) categories[12] -> 0.5*val_struct*rpr_off + 0.5*(rent regression)
            if cat_12 is not None:
                mask = direct_damages_input_data["use_code_std_desc_lps"] == cat_12
                res_part = alpha + direct_damages_input_data.loc[mask, "val_struct"] * beta_price + beta_area * direct_damages_input_data.loc[mask, "sqft"]
                direct_damages_input_data.loc[mask, "rent"] = 0.5 * direct_damages_input_data.loc[mask, "val_struct"] * rpr_off + 0.5 * res_part

            # 2) categories[c(22,43)] -> val_struct * rpr_off
            cats_22_43 = [c for c in (cat_22, cat_43) if c is not None]
            if cats_22_43:
                mask = direct_damages_input_data["use_code_std_desc_lps"].isin(cats_22_43)
                direct_damages_input_data.loc[mask, "rent"] = direct_damages_input_data.loc[mask, "val_struct"] * rpr_off

            # 3) categories[c(36,42,55)] -> val_struct * rpr_ret_off
            cats_36_42_55 = [c for c in (cat_36, cat_42, cat_55) if c is not None]
            if cats_36_42_55:
                mask = direct_damages_input_data["use_code_std_desc_lps"].isin(cats_36_42_55)
                direct_damages_input_data.loc[mask, "rent"] = direct_damages_input_data.loc[mask, "val_struct"] * rpr_ret_off

            # 4) categories[39] -> 1/3*(ret + off + res-regression)
            if cat_39 is not None:
                mask = direct_damages_input_data["use_code_std_desc_lps"] == cat_39
                res_part = alpha + direct_damages_input_data.loc[mask, "val_struct"] * beta_price + beta_area * direct_damages_input_data.loc[mask, "sqft"]
                direct_damages_input_data.loc[mask, "rent"] = (
                    (1 / 3) * direct_damages_input_data.loc[mask, "val_struct"] * rpr_ret
                    + (1 / 3) * direct_damages_input_data.loc[mask, "val_struct"] * rpr_off
                    + (1 / 3) * res_part
                )
    ############################################

    # Estimate revenue based on rent and rent-to-revenue ratios:
    print("Estimating revenue based on rent and rent-to-revenue ratios...")

    # Create initial revenue column for COM and IND
    direct_damages_input_data['revenue'] = np.nan
    mask_com = direct_damages_input_data['occtype'].str.match(r'^COM', na=False)
    mask_ind = direct_damages_input_data['occtype'].str.match(r'^IND', na=False)
    direct_damages_input_data.loc[mask_com, 'revenue'] = direct_damages_input_data.loc[mask_com, 'rent'] / rr_ret
    direct_damages_input_data.loc[mask_ind, 'revenue'] = direct_damages_input_data.loc[mask_ind, 'rent'] / rr_ind

    # Override logic based on use_code_std_desc_lps (maps R indices -> Python)
    cats_72_28_69 = _cats([72, 28, 69])
    if cats_72_28_69:
        mask = direct_damages_input_data['use_code_std_desc_lps'].isin(cats_72_28_69)
        direct_damages_input_data.loc[mask, 'revenue'] = direct_damages_input_data.loc[mask, 'rent'] / rr_ret_rest

    cats_63_34 = _cats([63, 34])
    if cats_63_34:
        mask = direct_damages_input_data['use_code_std_desc_lps'].isin(cats_63_34)
        direct_damages_input_data.loc[mask, 'revenue'] = direct_damages_input_data.loc[mask, 'rent'] / rr_rest

    cats_36_42_55 = _cats([36, 42, 55])
    if cats_36_42_55:
        mask = direct_damages_input_data['use_code_std_desc_lps'].isin(cats_36_42_55)
        direct_damages_input_data.loc[mask, 'revenue'] = direct_damages_input_data.loc[mask, 'rent'] / rr_ret_off

    cats_12_22 = _cats([12, 22])
    if cats_12_22:
        mask = direct_damages_input_data['use_code_std_desc_lps'].isin(cats_12_22)
        direct_damages_input_data.loc[mask, 'revenue'] = direct_damages_input_data.loc[mask, 'rent'] / rr_off

    cat_39 = _cat(39)
    if cat_39 is not None:
        mask = direct_damages_input_data['use_code_std_desc_lps'] == cat_39
        direct_damages_input_data.loc[mask, 'revenue'] = direct_damages_input_data.loc[mask, 'rent'] / rr_ret_off

    # Calculating non-structural damages
    print("Compute non-structural damages...")
    direct_damages_input_data['non_struct_cost'] = np.nan

    mask_res = direct_damages_input_data['occtype'].str.match(r'^RES', na=False)
    mask_comind = direct_damages_input_data['occtype'].str.match(r'^(COM|IND)', na=False)

    ################################################################################################################
    ##Compute non-structural costs based on occupancy type:

    # Non-structural costs for residential buildings:
    # For residential (RES) buildings: In case the structural damage to value of the structure is greater than 50%,
    # the people have to relocate, thus add relocation costs (1.5*rent) to non-structural costs.

    # Thus, first calculate the ratio of structure_damage_value / val_struct ratio to determine if it is > 0.5:
    # For RES: if structure_damage_value / val_struct > 0.5 add relocation cost (1.5*rent)
    # protect against division by zero by replacing 0 with NaN in denominator
    val_struct_safe = direct_damages_input_data['val_struct'].replace({0: np.nan})
    ratio = direct_damages_input_data['structure_damage_value'] / val_struct_safe


    # Compute the baseline non-structural cost for each row as rent * (time_for_recovery in days) / 30 
    # (i.e., converts recovery days to months). Result is a Series.
    res_base = direct_damages_input_data['rent'] * direct_damages_input_data['time_for_recovery'] / 30
    # Variant of the above that adds a relocation/extra cost equal to 1.5 × rent
    res_plus = res_base + 1.5 * direct_damages_input_data['rent']
    direct_damages_input_data.loc[mask_res, 'non_struct_cost'] = np.where(ratio[mask_res] > 0.5, res_plus[mask_res], res_base[mask_res])

    # Non-structural costs for commercial (COM) and industrial (IND) buildings:

    # For COM|IND: revenue * time_for_recovery / 30
    direct_damages_input_data.loc[mask_comind, 'non_struct_cost'] = direct_damages_input_data.loc[mask_comind, 'revenue'] * direct_damages_input_data.loc[mask_comind, 'time_for_recovery'] / 30

    ################################################################################################################################
    # COMPUTE DAMAGE CATEGORIES:
    ################################################################################################################################
    # This code segment computes different damage categories: total direct damages, total indirect damages, 
    # and total damages (= direct and indirect damages).
    print("Compute different damages categories...")

    ################################################################################################################################
    # Total direct damages:
    print("Compute total direct damages...")

    # Total direct damages (R: rowSums(..., na.rm = TRUE))
    direct_damages_input_data['tot_direct_costs'] = direct_damages_input_data[['structure_damage_value', 'contents_damage_value', 'non_struct_cost']].fillna(0).sum(axis=1)

    ################################################################################################################################
    # Total indirect damages (COM/ IND only):
    print("Compute total indirect damages...")
    # Indirect damage multipliers: read CSV into a pandas DataFrame
    # Apply multipliers to assess indirect costs for COM and IND buildings.

    multipliers_path = Path(indirectdamages_multiplier_directory / "multipliers.csv")

    # If multipliers_path is not existing, raise error message:
    if not multipliers_path.exists():
        raise FileNotFoundError(f"Multipliers file not found at: {multipliers_path}")    

    # Load multipliers CSV file:
    multipliers = pd.read_csv(multipliers_path)
    print(f"Loaded multipliers for indirect damages from: {multipliers_path} (shape={multipliers.shape})")

    # Join overall_multiplier from multiplier using occtype <-> NSI.Code
    # Perform a left-join (SQL-style) of the multipliers table into direct_damages_input_data by matching 
    # direct_damages_input_data["occtype"] with multipliers["NSI Code"].
    direct_damages_input_data = direct_damages_input_data.merge(
        multipliers[["NSI Code", "overall_multiplier"]], #Only the two columns ["NSI Code", "overall_multiplier"] 
        #are taken from multipliers for the join. Because it is a left join, every row from direct_damages_input_data 
        # is kept; if no match is found the new overall_multiplier will be NaN for that row.
        how="left",
        left_on="occtype",
        right_on="NSI Code"
    ).drop(columns=["NSI Code"]) #After the merge the temporary right-side key column "NSI Code" is dropped, 
    #so the result gains the overall_multiplier column and loses the duplicate key column
    # The merged DataFrame is assigned back to direct_damages_input_data (it overwrites the original variable).

    # indirect damages = multiplier * non_struct_cost (0 if overall_multiplier is missing)
    direct_damages_input_data["tot_indirect_costs"] = np.where(
        direct_damages_input_data["overall_multiplier"].isna(),
        0,
        direct_damages_input_data["non_struct_cost"] * direct_damages_input_data["overall_multiplier"]
    )

    # compute total cost = tot_direct_costs + tot_indirect_costs
    direct_damages_input_data["tot_cost"] = direct_damages_input_data[["tot_direct_costs", "tot_indirect_costs"]].fillna(0).sum(axis=1)

    # Keep road damages only on ROAD rows; all other rows stay missing.
    direct_damages_input_data["road_damages"] = np.where(
        direct_damages_input_data["occtype"].eq("ROAD"),
        direct_damages_input_data["structure_damage_value"],
        np.nan,
    )

    # Mark only the first row for each fid_building with 1; repeated fid_building rows stay missing.
    direct_damages_input_data['building_count'] = pd.Series(pd.NA, index=direct_damages_input_data.index, dtype='Int64')
    first_building_rows = direct_damages_input_data['fid_building'].notna() & ~direct_damages_input_data['fid_building'].duplicated(keep='first')
    direct_damages_input_data.loc[first_building_rows, 'building_count'] = 1

    # guard against missing population column
    if "population" not in direct_damages_input_data.columns:
        raise KeyError("'population' column not found in direct_damages_input_data")
    
    # map adapt codes to names (guard against missing 'adapt' column)
    # adapt_map = {0: "none", 14: "seawall", 23: "reef", 31: "beach_dune"}
    # if "adapt" in direct_damages_input_data.columns:
    #     direct_damages_input_data["adapt_name"] = direct_damages_input_data["adapt"].map(adapt_map)
    #     direct_damages_input_data["adapt_name"] = direct_damages_input_data["adapt_name"].where(
    #         direct_damages_input_data["adapt_name"].notna(), pd.NA
    #     )
    # else:
    #     # fallback when adapt is missing
    #     print("WARNING: 'adapt' column not found — setting adapt_name to NA")
    #     direct_damages_input_data["adapt_name"] = pd.NA

    # merge the direct_damages_input_data with the geopackage data to get the geometry column back (if needed for future spatial analysis or plotting)
    # Merge geometry from geopackage back into the damages data and save as spatial output
    
    # avoid duplicated columns (e.g., population -> population_x/population_y) when merging back geometry
    cols_to_add = [
        c for c in direct_damages_input_data.columns
        if c == "fid_building" or c not in direct_damages_input_data_gpkg.columns
    ]
    result = direct_damages_input_data_gpkg.merge(
        direct_damages_input_data[cols_to_add],
        on="fid_building",
        how="left",
    )
    nameout = output_folder / f'{direct_damages_input_path.stem}_indirects.gpkg'
    result.to_file(nameout, driver="GPKG")

    # OUTPUT FILE (for each scenario):
    out_path = Path(output_folder / f"{direct_damages_input_path.stem}_indirects.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    direct_damages_input_data.to_csv(out_path, index=False)
    print(f"Saved consolidated file to: {out_path}")

    # sum by type and building counts 
    building_types = direct_damages_input_data.copy() 
    building_types['building_type_category'] = building_types['occtype'].str[:3]
    building_types['building_counter'] = 1
    building_types_summary = (
        building_types
        .groupby('building_type_category', dropna=False)[['tot_direct_costs', 'tot_indirect_costs', 'tot_cost', 'population','building_counter']]
        .sum(min_count=1)
        .reset_index()
    )
    building_types_summary.to_csv(output_folder / f'{direct_damages_input_path.stem}_buildings_summary.csv', index=False)

    # Plot direct vs indirect damages
    plt.figure(figsize=(10, 6))
    plt.bar(range(1, len(direct_damages_input_data) + 1),direct_damages_input_data['overall_multiplier'])
     
    plt.xlabel('Building Index')
    plt.ylabel('Overall Multiplier')
    plt.title('Multipliers for Indirect Damages')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Save the plot
    plot_path = output_folder / f"multipliers_{input_stem}.png"
    plt.savefig(str(plot_path), bbox_inches="tight", dpi=150)
    print(f"Saved multipliers plot to: {plot_path}")
    plt.close()


# check number of outputs 
input_files = sorted(input_dir.glob("*_damages_and_roads.csv")) 
output_files = sorted(output_folder.glob("*damages_and_roads_indirects.csv")) 
print(f"Number of output_files: {len(output_files)}")
print(f"Number of output_files: {len(input_files)}")
print(len(input_files) == len(output_files))

print("S021 successfully completed. Indirect damages computation completed for all input files.")
print(f"Output files written to {output_folder}.")
print('end of script')
