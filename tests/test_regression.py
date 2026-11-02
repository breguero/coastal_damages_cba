"""v1 regression: coastal_risk_cba.risk and .cba against the v1 reference tables (rel. tol. 1e-6).

Inputs are the v1 per-unit tables (ALLD_BY_CBA_STUDY_AREA, AEB_byarea_abovethreshold, all_adapt_costs).
Runs for every regression site whose reference outputs are reachable (lab share: three sites;
Santa Cruz sample data: site001_santacruz2).
"""

import numpy as np
import pandas as pd
import pytest

from coastal_risk_cba import cba, risk
from coastal_risk_cba.config import Config

pytestmark = pytest.mark.regression
CFG = Config.load()
SITES = [s.id for s in CFG.available_regression_sites]
KEYS = ["cba_study_area", "dem", "adapt"]
RTOL = 1e-6


def _ref(site_id, name):
    s = CFG.site(site_id)
    return pd.read_csv(s.reference_dir / "012_damages" / "aed_cba_results" / f"flood_map_{s.regression_mode}" / name)


def _costs(site_id):
    s = CFG.site(site_id)
    return pd.read_csv(s.reference_dir / "012_damages" / "adaptation_costs" / f"all_adapt_costs_{s.id}.csv")


def _compare(new, ref, keys, cols):
    m = ref.merge(new, on=keys, how="outer", suffixes=("_ref", "_new"), indicator=True)
    assert (m["_merge"] == "both").all(), m.loc[m["_merge"] != "both", keys]
    for c in cols:
        np.testing.assert_allclose(m[f"{c}_new"].astype(float), m[f"{c}_ref"].astype(float),
                                   rtol=RTOL, atol=1e-9, equal_nan=True, err_msg=c)


@pytest.mark.parametrize("site_id", SITES)
def test_aed(site_id):
    alld = _ref(site_id, f"ALLD_BY_CBA_STUDY_AREA_{site_id}.csv")
    by_unit = risk.aed_table(alld, CFG.risk["anchor_rp"])
    _compare(by_unit, _ref(site_id, f"AED_byarea_{site_id}.csv"), KEYS,
             ["aed", "aed_population", "aed_building_count"])
    _compare(risk.aed_totals(by_unit), _ref(site_id, f"AED_totals_{site_id}.csv"), ["dem", "adapt"],
             ["aed", "aed_population", "aed_building_count"])


@pytest.mark.parametrize("site_id", SITES)
def test_aeb_and_inclusion(site_id):
    alld = _ref(site_id, f"ALLD_BY_CBA_STUDY_AREA_{site_id}.csv")
    inc = CFG.risk["inclusion"]
    flag = risk.inclusion_flag(alld, inc["threshold_usd"], inc["metric"], inc["adapt"], inc["dem"], inc["rp"])
    aeb = risk.add_inclusion(risk.add_year(risk.aeb_table(alld, CFG.risk["anchor_rp"]), CFG.dem_year), flag)
    cols = ["aeb", "aed", "aed_wo_adapt", "aeb_population", "aed_population", "aed_population_wo_adapt",
            "aeb_building_count", "aed_building_count", "aed_building_count_wo_adapt", "year", "include_in_bcr"]
    _compare(aeb, _ref(site_id, f"AEB_byarea_{site_id}_abovethreshold.csv"), KEYS, cols)
    _compare(risk.aeb_totals(aeb), _ref(site_id, f"AEB_totals_{site_id}.csv"), ["dem", "adapt"],
             [c for c in cols if c.startswith(("aeb", "aed"))])
    bbr = risk.benefit_by_rp(alld)
    _compare(bbr, _ref(site_id, f"BENEFIT_BY_RP_byarea_{site_id}.csv"), KEYS + ["rp"],
             ["benefit", "damage_no_adapt", "damage_adapt", "benefit_population", "benefit_building_count"])


CBA_COLS = ["aeb", "adaptation_cost", "roi", "cost_for_bcr_1", "pv", "npv", "bcr"]


@pytest.mark.parametrize("site_id", SITES)
def test_cba_legacy(site_id):
    mode = CFG.site(site_id).regression_mode
    aeb = _ref(site_id, f"AEB_byarea_{site_id}_abovethreshold.csv")
    u = cba.unit_cba(aeb, _costs(site_id), 0.03, CFG.cba["nyr"], "legacy", 0, False)
    ref_u = _ref(site_id, f"CBA_results_bycbastudyarea_disc030_CBA_dune0_mode{mode}.csv")
    _compare(u, ref_u, ["cba_study_area", "year", "adapt"], CBA_COLS + ["include_in_bcr"])
    t = cba.regional_cba(u, 0.03, CFG.cba["nyr"], 0)
    ref_t = _ref(site_id, f"CBA_results_TOTALS_{site_id}_CBA_dune0_disc030_mode{mode}.csv")
    _compare(t, ref_t, ["year", "adapt"], CBA_COLS)
