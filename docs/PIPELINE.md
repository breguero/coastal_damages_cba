# Pipeline steps

All paths are relative to `COSMOS_DATA_ROOT` (inputs) and `COSMOS_OUTPUT_DIR/<site>` (outputs).
`<site>` e.g. `site001_santacruz2`; `<mode>` = flood-map mode (`001` hydrodynamic, `002` morphodynamic update,
`003`/`004` the same without DEM change). Flood maps are named
`<siteNNN>_dem<SLR>_rp<RP>_adapt<code>_mode<mode>_hmax.tif` (dem020/050/080 = 2025/2055/2085; RP in years).

| step | does | reads | writes |
|---|---|---|---|
| S010 | nearest join of NSI points to building footprints (≤ 50 m); unmatched NSI points buffered 10 m; values and population summed per footprint, occupancy, stories and foundation | `010_DAMAGES_INPUT/<site>/exposure/nsi_subset.gpkg`, `buildings_subset.gpkg`; CRS from one flood map | `011_Joined_NSI_to_Buildings/nsi_to_buildings_proj_all_occtype.gpkg` |
| S011 | assigns each building to a CBA study unit (intersect; first match kept) | `cba_study_areas/cba_study_area.gpkg` | `buildings_with_cba_study_areas.gpkg`, join table |
| S012 | expected annual dune volume loss per unit (optional; needs `dune_morphodynamic_change/`) | `dune_volumes_<site>.csv` | `012_damages/EAV_dune_volume_<site>.csv` |
| S013 | adaptation cost per unit: seawall $/m interpolated on height, reef and dune unit costs, 5 % maintenance | `adaptation_dimensions/*.csv` | `012_damages/adaptation_costs/all_adapt_costs_<site>.csv` |
| S020 | per flood map: maximum depth per footprint (`all_touched`), HAZUS occupancy code, structure and content damage from FAST curves, ×1.19 (2021→2025 USD); flooded road length × $1.358M/mile | flood maps, buildings, damage tables, `exposure/roads_clipped.gpkg` | `012_damages/damages_by_buildings/flood_map_<mode>/*_damages_and_roads.csv` + gpkg |
| S021 | indirect losses: relocation (residential, damage ratio > 0.5), rent loss (OLS rent model), business interruption from repair time and rent-to-revenue ratios, BEA multipliers; `tot_cost` = direct + indirect | S020 outputs, `000_Data/020_*`, `021_*`, `022_*` | `012_damages/indirect_damages/flood_map_<mode>/*_indirects.csv` + gpkg |
| S022 | damages per unit and RP; expected annual damage (AED, trapezoid over exceedance probability, zero damage at RP 2); expected annual benefit (AEB) of each measure; inclusion flag (no-adaptation damage at 2025, RP 50 ≥ $0.5M); figures | S021 outputs | `012_damages/aed_cba_results/flood_map_<mode>/ALLD_*, AED_*, AEB_*, BENEFIT_BY_RP_*` |
| S024 | damage totals by building class per flood map | S021 summaries | `summary_damages/flood_map_<mode>/*_table_<mode>.csv` |
| S025 | benefit per building (no adaptation − with measure) | S021 gpkg | `*_benefits.gpkg`, `BENEFIT_SUMMARY_<site>.csv` |
| S030 | present value of AEB over 30 years (3 %), NPV, BCR, ROI, break-even cost per unit and per site | `AEB_byarea_*_abovethreshold.csv`, `all_adapt_costs_<site>.csv` | `CBA_results_bycbastudyarea_*.csv`, `CBA_results_TOTALS_*.csv`, figures |
| S040 | road damage per flood map | S021 outputs | `road_damages/flood_map_mode_<mode>/<site>_road_damages_summary.csv` |

## Conventions to be aware of

These are the conventions of the code as used for the California Fifth Climate Change Assessment report.
Switches for them are being added in `coastal_risk_cba` (see `configs/cosmos_adapts.yaml`).

- Depth per building is the maximum of the raster cells touching the footprint, not the mean.
- Roads are costed per flood map (S020, S040) but are not part of AED, AEB or the CBA.
- The PV annuity starts at t = 0 (30-year factor 20.19 at 3 %; 19.60 with the first flow at t = 1).
- Seawalls are designed once on the 2025 50-year level + 0.5 m and kept for all epochs.
- Dune volume loss uses RP 1 as the zero-loss anchor; damages use RP 2.
- CBA cost rule (`COSMOS_COST_BASE`): `all_placed` (default) charges every placed measure its cost in every epoch;
  `legacy` drops units with zero benefit from the cost sum, as in the report tables.
