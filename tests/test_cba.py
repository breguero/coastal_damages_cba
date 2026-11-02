import numpy as np
import pandas as pd
import pytest

from coastal_risk_cba import cba


def test_pv_factors():
    assert cba.pv_factor(0.03, 30, 0) == pytest.approx(20.19, abs=0.005)
    assert cba.pv_factor(0.03, 30, 1) == pytest.approx(19.60, abs=0.005)
    assert cba.pv_factor(0.03, 30, 0) == pytest.approx(cba.pv_factor(0.03, 30, 1) * 1.03)


def test_pv_matches_v1_definition():
    import numpy_financial as npf
    assert cba.pv(1234.5, 0.07, 30) == float(npf.npv(0.07, np.full(30, 1234.5)))


def test_rate_suffix():
    assert cba.rate_suffix(0.03) == "disc030" and cba.rate_suffix(0.07) == "disc070"


def _toy():
    """A: placed, benefit. B: placed, no benefit in 2025, benefit in 2055. C: not placed, spill-over benefit."""
    aeb = pd.DataFrame({
        "cba_study_area": ["A", "B", "C", "A", "B", "C"],
        "year": [2025, 2025, 2025, 2055, 2055, 2055],
        "adapt": ["dune"] * 6,
        "aeb": [100.0, 0.0, 10.0, 100.0, 50.0, 10.0],
        "include_in_bcr": [1] * 6,
    })
    costs = pd.DataFrame({"cba_study_area": ["A", "B"], "adapt": ["dune", "dune"],
                          "adapt_cost": [1000.0, 2000.0], "maint_cost": [10.0, 20.0], "recon_cost": [0.0, 0.0]})
    return aeb, costs


F = cba.pv_factor(0.03, 30)


def test_all_placed_rule():
    aeb, costs = _toy()
    u = cba.unit_cba(aeb, costs, 0.03, cost_base="all_placed").set_index(["cba_study_area", "year"])
    assert u.loc[("A", 2025), "adaptation_cost"] == pytest.approx(1000 + 10 * F)
    assert u.loc[("B", 2025), "adaptation_cost"] == pytest.approx(2000 + 20 * F)
    assert u.loc[("B", 2025), "pv"] == 0 and u.loc[("B", 2025), "bcr"] == 0
    assert u.loc[("C", 2025), "adaptation_cost"] == 0 and np.isnan(u.loc[("C", 2025), "bcr"])
    assert u.loc[("C", 2025), "pv"] == pytest.approx(10 * F)
    t = cba.regional_cba(u.reset_index(), 0.03).set_index("year")
    assert t.loc[2025, "adaptation_cost"] == pytest.approx(3000 + 30 * F)
    assert t.loc[2025, "pv"] == pytest.approx(110 * F)
    assert t.loc[2025, "n_placed"] == 2 and t.loc[2025, "n_cost_effective"] == 1


def test_legacy_rule():
    aeb, costs = _toy()
    u = cba.unit_cba(aeb, costs, 0.03, cost_base="legacy").set_index(["cba_study_area", "year"])
    assert np.isnan(u.loc[("B", 2025), "adaptation_cost"]) and np.isnan(u.loc[("B", 2025), "pv"])
    assert u.loc[("B", 2055), "adaptation_cost"] == pytest.approx(2000 + 20 * F)
    t = cba.regional_cba(u.reset_index(), 0.03).set_index("year")
    assert t.loc[2025, "adaptation_cost"] == pytest.approx(1000 + 10 * F)  # B's cost dropped
    assert t.loc[2055, "adaptation_cost"] == pytest.approx(3000 + 30 * F)


def test_portfolio_2025_rule():
    aeb, costs = _toy()
    u = cba.unit_cba(aeb, costs, 0.03, cost_base="portfolio_2025").set_index(["cba_study_area", "year"])
    assert u.loc[("B", 2055), "placed"] == 1 and u.loc[("B", 2055), "in_portfolio"] == 0
    assert u.loc[("B", 2055), "adaptation_cost"] == 0 and np.isnan(u.loc[("B", 2055), "bcr"])
    assert u.loc[("B", 2055), "pv"] == pytest.approx(50 * F)  # kept as spill-over
    t = cba.regional_cba(u.reset_index(), 0.03).set_index("year")
    assert t.loc[2055, "adaptation_cost"] == pytest.approx(1000 + 10 * F)
    assert t.loc[2055, "n_placed"] == 1


def test_inclusion_filter_and_first_cashflow_year():
    aeb, costs = _toy()
    aeb.loc[aeb["cba_study_area"] == "C", "include_in_bcr"] = 0
    u = cba.unit_cba(aeb, costs, 0.03, first_cashflow_year=1)
    t = cba.regional_cba(u, 0.03, first_cashflow_year=1).set_index("year")
    assert t.loc[2025, "pv"] == pytest.approx(100 * cba.pv_factor(0.03, 30, 1))


def test_dune_reconstruction_replaces_maintenance():
    aeb, costs = _toy()
    costs["recon_cost"] = [500.0, 0.0]
    u = cba.unit_cba(aeb, costs, 0.03, dune_reconstruction=True).set_index(["cba_study_area", "year"])
    assert u.loc[("A", 2025), "adaptation_cost"] == pytest.approx(1000 + 500 * F)


def test_costs_by_dem_and_run_rates():
    aeb, costs = _toy()
    dem_year = {"dem020": 2025, "dem050": 2055}
    costs_dem = pd.concat([costs.assign(dem=d) for d in dem_year])
    cfg = {"discount_rates": [0.03, 0.07], "nyr": 30, "cost_base": "all_placed",
           "first_cashflow_year": 0, "dune_reconstruction": False}
    out = cba.run(aeb, costs_dem, cfg, dem_year)
    assert set(out) == {"disc030", "disc070"}
    u_no_year = cba.unit_cba(aeb, costs, 0.03)
    pd.testing.assert_frame_equal(out["disc030"][0], u_no_year)
