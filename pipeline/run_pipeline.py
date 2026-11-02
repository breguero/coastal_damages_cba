"""Run the CoSMoS Adapts damage and cost-benefit pipeline (S010-S040) for one site and flood-map mode.

    python pipeline/run_pipeline.py --data-root <folder with 000_Data and 010_DAMAGES_INPUT> \
        --output outputs --site site001_santacruz2 --mode 002

Each step is a script in this folder; it reads the run settings from environment variables
(see S000_project_config_cosmos_adapt.py). Steps run in order; --from/--only select a subset.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = [
    ("S010", "S010_join_nsi_to_buildings_geopandas.py", "join NSI points to building footprints"),
    ("S011", "S011_associate_buildings_to_cba_study_units.py", "assign buildings to CBA study units"),
    ("S012", "S012_calculate_changes_dune_volume.py", "dune volume loss (only with dune_morphodynamic_change input)"),
    ("S013", "S013_calculate_adaptation_costs.py", "adaptation costs per unit"),
    ("S020", "S020_calculate_damages_by_buildings.py", "direct damages per building and flood map; roads"),
    ("S021", "S021_compute_indirect_damages.py", "indirect damages (relocation, business interruption, multipliers)"),
    ("S022", "S022_AED_AEB_calculation_and_plots.py", "expected annual damage (AED) and benefit (AEB) per unit"),
    ("S024", "S024_calculate_totals.py", "damage totals by building class"),
    ("S025", "S025_calculate_geospatial_benefits.py", "benefit per building (GeoPackage)"),
    ("S030", "S030_CBA_calculation.py", "present value, NPV, BCR per unit and site"),
    ("S040", "S040_sum_up_roads_damage.py", "road damage summary"),
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data-root", required=True, type=Path, help="folder that holds 000_Data/ and 010_DAMAGES_INPUT/")
    p.add_argument("--output", required=True, type=Path, help="results folder (one subfolder per site)")
    p.add_argument("--site", default="site001_santacruz2")
    p.add_argument("--mode", default="002", help="flood-map mode: 001 | 002 | 003 | 004")
    p.add_argument("--cost-base", default="all_placed", choices=["all_placed", "legacy"],
                   help="CBA cost rule; 'legacy' reproduces the 2026 report tables")
    p.add_argument("--discount-rate", default=0.03, type=float)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--from", dest="start", choices=[s[0] for s in STEPS], help="start at this step")
    g.add_argument("--only", nargs="+", choices=[s[0] for s in STEPS], help="run only these steps")
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    data_root = a.data_root.expanduser().resolve()
    output = a.output.expanduser().resolve()
    if not (data_root / "010_DAMAGES_INPUT" / a.site).is_dir():
        sys.exit(f"no input folder {data_root / '010_DAMAGES_INPUT' / a.site}")
    if "011_DAMAGES_results_final" in output.parts:
        sys.exit("refusing to write into 011_DAMAGES_results_final (reference results)")

    env = dict(os.environ,
               COSMOS_DATA_ROOT=str(data_root), COSMOS_OUTPUT_DIR=str(output),
               COSMOS_SITE=a.site, COSMOS_MODE=a.mode, COSMOS_COST_BASE=a.cost_base,
               COSMOS_DISCOUNT_RATE=str(a.discount_rate), COSMOS_BATCH="1", MPLBACKEND="Agg")

    steps = STEPS
    if a.only:
        steps = [s for s in STEPS if s[0] in a.only]
    elif a.start:
        steps = STEPS[[s[0] for s in STEPS].index(a.start):]
    has_dune_input = (data_root / "010_DAMAGES_INPUT" / a.site / "dune_morphodynamic_change").is_dir()

    output.mkdir(parents=True, exist_ok=True)
    log_dir = output / a.site / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for sid, script, desc in steps:
        if sid == "S012" and not has_dune_input:
            print(f"[{sid}] skipped: no dune_morphodynamic_change input (dune reconstruction off)")
            continue
        print(f"[{sid}] {desc} ...", flush=True)
        t0 = time.time()
        log = log_dir / f"{sid}.log"
        with open(log, "w") as fh:
            r = subprocess.run([sys.executable, script], cwd=HERE, env=env, stdout=fh, stderr=subprocess.STDOUT)
        print(f"[{sid}] {'done' if r.returncode == 0 else 'FAILED'} in {time.time() - t0:.0f} s (log: {log})", flush=True)
        if r.returncode != 0:
            print("".join(open(log).readlines()[-25:]))
            sys.exit(r.returncode)


if __name__ == "__main__":
    main()
