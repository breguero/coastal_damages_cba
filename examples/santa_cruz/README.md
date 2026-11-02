# Santa Cruz example

Site `site001_santacruz2`, flood-map mode `002` (morphodynamic update): 3 sea-level scenarios
(2025, 2055, 2085) × 4 return periods (5, 20, 50, 100 yr) × 4 options (no adaptation, seawall, reef, dune)
= 48 flood maps, 11 study units.

## Data

Google Drive: **<GOOGLE_DRIVE_LINK>** — `cosmos_adapts_santacruz_sample.zip`, 71 MB
(sha256 `164ba694be0e9ebe337e6e9c3f50b35a78324e3f088ce9611b0a1f3f703ae5d2`).

`download_data.py` downloads it, unpacks it into `examples/santa_cruz/data/` and checks every file against
`MANIFEST.csv`. If the download is blocked, download the zip in a browser and run
`python examples/santa_cruz/download_data.py --zip <path to zip>`.

Contents: see `README.txt` inside the archive and `SOURCES.md` in the repository root.

## Run

```bash
python pipeline/run_pipeline.py \
    --data-root examples/santa_cruz/data/cosmos_adapts_santacruz_sample \
    --output outputs --cost-base legacy
```

Results go to `outputs/site001_santacruz2/` (layout in `docs/PIPELINE.md`); a log per step is in `logs/`.
The main tables are in `outputs/site001_santacruz2/012_damages/aed_cba_results/flood_map_002/`:

| file | content |
|---|---|
| `AED_totals_*.csv`, `AED_byarea_*.csv` | expected annual damage by epoch and option, site and per unit |
| `AEB_totals_*.csv`, `AEB_byarea_*_abovethreshold.csv` | expected annual benefit of each measure |
| `CBA_results_bycbastudyarea_*.csv` | PV of benefits, cost, NPV, BCR per unit |
| `CBA_results_TOTALS_*.csv` | the same for the whole site |

## Check against the reference

```bash
python examples/santa_cruz/compare_to_reference.py \
    --reference examples/santa_cruz/data/cosmos_adapts_santacruz_sample/reference_results --output outputs
```

Result of a full run with `--cost-base legacy` (2026-11-01): 14 of 17 tables match to 1e-6, including every
ALLD, AED, AEB and BENEFIT_BY_RP table, the adaptation costs and the building-count and population summaries.
Expected differences:

- `CBA_results_bycbastudyarea_*`: all columns match except `cost_for_bcr_1` in 2 units without a placed measure
  (pleasure_point dune 2085, seabright seawall 2055): the report run wrote the PV there, the current S030 writes
  NaN. Regional totals match.
- `road_damages_summary` and `total_damage_table_002` (road rows only): 7 of 48 flood maps
  (dem020 rp100, all options; dem050 and dem080 rp100, no adaptation) were updated on 21-22 June 2026, after the
  reference damage run (20 June). Building damages from these maps are unchanged; road damage is $0.12M higher per
  map (1-3.6 %). Roads do not enter AED, AEB or the CBA.

With the default `--cost-base all_placed` the AED/AEB tables are the same and the CBA cost base changes where a
placed measure has zero benefit in a unit. Santa Cruz dune, regional BCR 2025/2055/2085:
7.25/8.71/7.10 (`legacy`) and 4.26/4.88/3.28 (`all_placed`).
