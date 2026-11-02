# coastal_risk_cba

Code for the economic analysis of **CoSMoS Adapts**: building-level coastal flood damages, expected annual
damage (AED) and benefit (AEB), and cost-benefit analysis (CBA) of seawalls, reefs and dunes under sea-level rise.
It produced the damage and CBA results of the CoSMoS Adapts report for California's Fifth Climate Change
Assessment and the companion CoSMoS Adapts Explorer.

Inputs are flood-depth rasters (one per sea-level scenario, return period and adaptation measure), a building
inventory (USACE NSI) joined to building footprints, study units, and adaptation dimensions and unit costs.
Outputs are damages per building, AED/AEB per study unit, and present value, NPV and benefit-cost ratio per
unit and per site.

## Contents

```
pipeline/                    the analysis, one script per step (S010-S040) + run_pipeline.py
  aux_scripts/               damage-curve lookup, AED/PV tools, road damage, recovery time, rent model fit
coastal_risk_cba/            package under development: risk.py (AED, AEB, exceedance curve, VaR/ES),
                             cba.py (PV, NPV, BCR, cost rules), config.py (reads configs/cosmos_adapts.yaml)
configs/cosmos_adapts.yaml   sites, adaptation codes, return periods, economic parameters
examples/santa_cruz/         download script, comparison with reference results, instructions
docs/PIPELINE.md             what each step reads, computes and writes; conventions
tests/                       unit tests; regression tests against the reference results
```

## Install

```bash
git clone https://github.com/<org>/coastal_risk_cba.git
cd coastal_risk_cba
conda env create -f environment.yml
conda activate coastal-risk-cba
```

or `pip install -e ".[test]"` in an environment with GDAL/rasterio available.

## Run the Santa Cruz example

```bash
python examples/santa_cruz/download_data.py          # ~71 MB from Google Drive into examples/santa_cruz/data/
python pipeline/run_pipeline.py \
    --data-root examples/santa_cruz/data/cosmos_adapts_santacruz_sample \
    --output outputs --site site001_santacruz2 --mode 002 --cost-base legacy
python examples/santa_cruz/compare_to_reference.py \
    --reference examples/santa_cruz/data/cosmos_adapts_santacruz_sample/reference_results --output outputs
```

The full run takes about 15 minutes on a laptop (most of it in S020, 48 flood maps). Details in
`examples/santa_cruz/README.md`.

## Run on other data

Arrange the inputs as in the sample package (`000_Data/` with the damage and indirect-loss tables;
`010_DAMAGES_INPUT/<site>/` with `flood_map_sims/`, `exposure/`, `cba_study_areas/`, `adaptation_dimensions/`),
add the site and its adaptation codes to `_ADAPT_BY_SITE` in `pipeline/S000_project_config_cosmos_adapt.py`, and
run `run_pipeline.py` with `--site` and `--mode`. Steps can be run alone with `--only S022 S030` or resumed with
`--from S021`. Each script can also be run directly; it reads the settings from environment variables
(`COSMOS_DATA_ROOT`, `COSMOS_OUTPUT_DIR`, `COSMOS_SITE`, `COSMOS_MODE`, `COSMOS_COST_BASE`,
`COSMOS_DISCOUNT_RATE`; see `S000`).

## Tests

```bash
pytest                                                   # unit tests
COSMOS_DATA_ROOT=examples/santa_cruz/data/cosmos_adapts_santacruz_sample \
COSMOS_REFERENCE_DIR=examples/santa_cruz/data/cosmos_adapts_santacruz_sample/reference_results \
pytest                                                   # + regression of risk.py/cba.py on Santa Cruz
```

## Status

`pipeline/` is the code used for the report (v1), with paths, site and mode taken from the command line instead
of edited in each script; results are unchanged. `coastal_risk_cba/` is the refactor into a tested package
(risk and CBA done and verified against v1; exposure, damage and indirect-loss modules in progress).

## Citation and licence

See `CITATION.cff`. Code: BSD-3-Clause (`LICENSE`). Data sources and their licences: `SOURCES.md`.

Contact: Borja G. Reguero, University of California, Santa Cruz (breguero@ucsc.edu).
