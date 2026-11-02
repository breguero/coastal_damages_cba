#################################################################################################################
#                                                                                                                              
#   S011_calculate_changes_dune_volume.py                                                                                     
#   breguero@ucsc.edu 12/18/2025
#                                                                                                                                  
#   Script description:                                                                                          
#   calculate volumetric changes in dunes from morphodynamic model outputs
#   input: tables with dune volumes before and after storms (calculated from morphodynamic model outputs in Matlab)
#   output: table with annualized propobabilities of volumetric changes and plots
# ###############################################################################################################   

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import seaborn as sns
from pathlib import Path
import sys
import logging

from S000_project_config_cosmos_adapt import *
from aux_scripts.damage_calculation_tools import annual_expected_damage_dunes

# -------------------------
# Config and logging
# -------------------------
# INTERACTIVE_RUN = False
# if len(sys.argv) < 1:
#     print('Usage: python S011_calculate_changes_dune_volume.py [region_name] ')
#     print('example: python S011_calculate_changes_dune_volume.py site001_santacruz')
#     sys.exit(1)
# region_name = sys.argv[1]# Load region_name based on terminal argument:

# ----------------------------------------------------
# Study region to process:
#SITE = 'site001_santacruz' #for testing only, comment out when running from terminal
#SITE = 'site002_halfmoonbay' #for testing only, comment out when running from terminal
#SITE = 'site003_venturanorth' #for testing only, comment out when running from terminal
SITE = RUN_SITE  # set with COSMOS_SITE or run_pipeline.py --site
# ----------------------------------------------------

dirout = output_root / SITE / '012_damages'
dirout.mkdir(parents=True, exist_ok=True)

dirdata_dune_volume_loss = datadir_damages / SITE / 'dune_morphodynamic_change'   

# -------------------------
# Helpers
# -------------------------
REQUIRED_COLS = {
    "cba_study_area",
    "dem",
    "rp",
    "adapt",
    "Vdune",
    "Vdune_loss",
    "Perc_Loss",  # kept optional in practice, but validated as present
}

def validate_df(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

def load_data(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")
    df = pd.read_csv(csv_path)
    validate_df(df)

    # Ensure Vdune and Vdune_loss are numeric
    for col in ["Vdune", "Vdune_loss"]:
        if col in df.columns:
            non_na_before = df[col].notna().sum()
            # Clean common formatting artifacts then convert
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(",", "", regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            non_na_after = df[col].notna().sum()
            coerced = non_na_before - non_na_after
            if coerced > 0:
                logging.warning(f"Coerced {coerced} non-numeric values to NaN in column '{col}'.")

    # Ensure numeric rp and sensible ordering
    df["rp"] = pd.to_numeric(df["rp"], errors="coerce")
    if df["rp"].isna().any():
        logging.warning("Some rp values could not be parsed to numeric and will be dropped.")
        df = df.dropna(subset=["rp"])
    df["rp"] = df["rp"].astype(int)

    # Optional: enforce categories to reduce memory and stabilize ordering
    for col in ["cba_study_area", "dem", "adapt"]:
        if col in df.columns:
            df[col] = df[col].astype("category")

    # Map dem to years
    df['dem'] = df['dem'].map(dem_year_dict) 

    return df

def aggregate_weighted(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate by area/dem/rp[/adapt] using volume-weighted percentage:
    Perc_Change_pct = 100 * sum(Vdune_loss) / sum(Vdune)
    """
    grp_cols = ["cba_study_area", "dem", "rp", "adapt"]
    agg = (
        df.groupby(grp_cols, observed=True)
          .agg(Vdune=("Vdune", "sum"),
               Vdune_loss=("Vdune_loss", "sum"))
          .reset_index()
    )
    
    # Avoid divide-by-zero
    agg["Perc_Change_pct"] = np.where(
        agg["Vdune"] > 0,
        100.0 * agg["Vdune_loss"] / agg["Vdune"],
        np.nan,
    )
    return agg

def plot_perc_change(df_agg: pd.DataFrame, out_png: Path) -> None:
    sns.set_theme(style="whitegrid")
    areas = sorted(df_agg["cba_study_area"].unique().tolist())
    dems = sorted(df_agg["dem"].unique().tolist())
    adapts = sorted(df_agg["adapt"].unique().tolist())

    # Order x by rp ascending
    df_agg = df_agg.sort_values(["cba_study_area", "dem", "adapt", "rp"])

    col_wrap = min(3, max(1, len(areas)))
    palette = sns.color_palette("viridis_r", n_colors=max(3, len(dems)))

    # If multiple adapt scenarios exist, show line style per adapt
    style_kw = {"style": "adapt"} if len(adapts) > 1 else {}

    g = sns.FacetGrid(
        df_agg,
        col='cba_study_area',
        col_order=areas,
        col_wrap=col_wrap,
        hue='dem',
        hue_order=dems,
        palette=palette,
        sharex=True,
        sharey=True,
        height=4,
        aspect=1.3,
    )
    g.map_dataframe(sns.lineplot, x='rp', y='Perc_Change_pct', marker='o')
    
    #  Legends
    # Put legend outside on the right
    g.fig.subplots_adjust(right=0.82)
    handles, labels = g.axes.flat[0].get_legend_handles_labels()
    g.fig.legend(handles=handles, labels=labels, title="DEM",
                 loc="center left", bbox_to_anchor=(1.02, 0.5))
    # Make room on the right for the legend
    #g.fig.subplots_adjust(right=0.8)
    
    if len(adapts) > 1:
        # Add a second legend for adapt by drawing an invisible plot
        # Workaround: map a second axis-level plot with style legend extraction
        pass  # seaborn already includes style in the same legend when passed via map_dataframe

    g.set_axis_labels("Return Period (years)", "Dune Volume Change (%)")
    g.set_titles("{col_name}")
    # Keep y within [0, 100] if appropriate; comment out if data exceeds
    for ax in g.axes.flat:
        #ax.set_ylim(0, 100)
        ax.grid(True, which="major", axis="both", alpha=0.25)

    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    g.fig.savefig(out_png, dpi=200, bbox_inches="tight")
    print(f"Saved figure: {out_png}")

# -------------------------
# Main
# -------------------------
def main() -> None:
    print(f"NAME: {SITE}")
    
    # read file with dune volume changes 
    filename = f"dune_volumes_{SITE}.csv"
    csv_path = (dirdata_dune_volume_loss / filename).resolve()
    print(f"Input CSV: {csv_path}")

    df_raw = load_data(csv_path)
    print(f"Loaded {len(df_raw):,} rows")

    df_agg = aggregate_weighted(df_raw)
    print(f"Aggregated rows: {len(df_agg):,}")

    # Save aggregated CSV for reproducibility
    #out_csv = (dirout / f"dune_volume_agg_{NAME}.csv").resolve()
    #df_agg.to_csv(out_csv, index=False)
    #print(f"Saved aggregated CSV: {out_csv}")

    # Plot
    out_png = (dirout / f"perc_change_vs_rp_{SITE}.png").resolve()
    plot_perc_change(df_agg, out_png)

    # calculate annual expected volume loss for a given area/dem/adapt
    # Expected Annual Volume loss (EAV) per area/dem/adapt using trapezoidal integration over AEP=1/rp
    results = []
    group_cols = ["cba_study_area", "dem", "adapt"]
    for (area, dem, adapt), g in df_agg.groupby(group_cols, observed=True):
        
        # Sort by increasing AEP (i.e., rp descending) for stable integration
        g = g.dropna(subset=["rp"]).sort_values("rp", ascending=True)
        
        # get the reference dune volume
        VD0 = g["Vdune"].unique()

        # Ensure VD0 is a single numeric value (take first if multiple)
        VD0_vals = pd.Series(VD0).dropna().astype(float).to_numpy()
        if VD0_vals.size == 0:
            VD0 = np.nan
        else:
            if VD0_vals.size > 1:
                logging.warning(f"Multiple Vdune values for {area}/{dem}/{adapt}; using first: {VD0_vals[0]}")
            VD0 = float(VD0_vals[0])
        
        # extract volume loss and return periods
        volume_loss = g["Vdune_loss"].to_numpy(dtype=float)
        # HERE 
        # volume_loss = VD0 * g["Perc_Loss_ratio"].to_numpy(dtype=float) 
        
        return_periods = g["rp"].to_numpy(dtype=float)

        # calculate expected annual volume loss
        title_name = g.iloc[0]["cba_study_area"]
        EVL = annual_expected_damage_dunes(volume_loss, return_periods, title_name)

        # save results
        results.append({
            "cba_study_area": area,
            "dem": dem,
            "adapt": adapt,
            "Vdune_ref": VD0,
            "EAV_m3_per_year": EVL,
            "EAV_pct_per_year": EVL/VD0 * 100 if VD0 and VD0 > 0 else np.nan
            })

    # output results
    evl_df = pd.DataFrame(results).sort_values(group_cols)
    print(evl_df.head)

    out_csv_eav = (dirout / f"EAV_dune_volume_{SITE}.csv").resolve()
    evl_df.to_csv(out_csv_eav, index=False)
    print(f"Saved EAV table: {out_csv_eav}")

if __name__ == "__main__":
    main()




