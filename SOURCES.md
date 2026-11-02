# Data sources and licences

Code: BSD-3-Clause (see `LICENSE`). The Santa Cruz sample data are distributed separately (Google Drive link in
`examples/santa_cruz/README.md`); each input keeps the licence of its source.

| input | file(s) | source | licence / terms | status |
|---|---|---|---|---|
| Building inventory | `exposure/nsi_subset.gpkg` | USACE National Structure Inventory (NSI) | US Government work, public | confirm NSI version (2022) |
| Building footprints | `exposure/buildings_subset.gpkg` | Microsoft US Building Footprints | ODbL 1.0 (attribution, share-alike for derived databases) | |
| Roads | `exposure/roads_clipped.gpkg` | to confirm | to confirm | **open** |
| Depth-damage functions | `000_Data/001_DAMAGE_TABLES/flBldg*DmgFn_nsi_2022.csv` | FEMA Hazus Flood Assessment Structure Tool (FAST) | US Government work, public | |
| Repair (recovery) time | `000_Data/020_.../max_recovery_time.csv` | compiled from construction-company websites (D. Banerjee) | project data, CC-BY-4.0 | |
| Indirect-loss multipliers | `000_Data/021_.../multipliers.csv` | derived from BEA supply-use tables | BEA data public; table CC-BY-4.0 | |
| Residential rent model | `000_Data/022_.../zillow_rent_ols_coefficients.csv` | OLS fit on 189 Zillow listings (listings not redistributed) | coefficients CC-BY-4.0 | |
| Flood maps | `flood_map_sims/*.tif` | CoSMoS Adapts simulations (UCSC, with USGS) | to confirm (USGS release review) | **open** |
| CBA study units, adaptation dimensions, unit costs | `cba_study_areas/`, `adaptation_dimensions/` | CoSMoS Adapts project | CC-BY-4.0 | |
| Reference results | `reference_results/` | output of this code, California Fifth Climate Change Assessment run | CC-BY-4.0 | |
