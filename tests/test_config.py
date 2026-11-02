import importlib.util
import sys
from pathlib import Path

import pytest

from coastal_risk_cba.config import REPO_ROOT, Config, normalize_dem


@pytest.fixture(scope="module")
def cfg():
    return Config.load()


def test_plan_check(cfg):
    assert cfg.site("santacruz").adapt_names == {
        "000": "no_adaptation", "014": "seawall", "023": "reef", "031": "dune",
    }


def test_site_aliases(cfg):
    assert cfg.site("santacruz").id == "site001_santacruz2"
    assert cfg.site("ventura").id == "site004_venturanorth2"
    assert cfg.site("site002_halfmoonbay") is cfg.site("halfmoonbay")
    with pytest.raises(ValueError):
        cfg.site("nowhere")


def test_regression_sites(cfg):
    assert {(s.id, s.regression_mode) for s in cfg.regression_sites} == {
        ("site001_santacruz2", "002"), ("site002_halfmoonbay", "001"), ("site004_venturanorth2", "002"),
    }


def test_site_helpers(cfg):
    hmb = cfg.site("halfmoonbay")
    assert hmb.measures == ["seawall", "reef"] and not hmb.has_dunes
    assert hmb.flood_map_stem(2025, 5, "seawall", "001") == "site002_dem020_rp005_adapt010_mode001_hmax"
    assert cfg.site("santacruz").flood_map_stem("dem080", 100, "031", "002") == "site001_dem080_rp100_adapt031_mode002_hmax"


def test_normalize_dem():
    for v in (20, "20", 2025, "2025", "dem020"):
        assert normalize_dem(v) == "dem020"
    with pytest.raises(ValueError):
        normalize_dem(30)


def test_overrides(cfg):
    c2 = cfg.with_overrides({"cba.cost_base": "legacy", "risk.anchor_rp": 1})
    assert c2.cba["cost_base"] == "legacy" and c2.risk["anchor_rp"] == 1
    assert cfg.cba["cost_base"] == "all_placed"
    with pytest.raises(KeyError):
        cfg.with_overrides({"cba.no_such_key": 1})
    with pytest.raises(ValueError):
        cfg.with_overrides({"cba.cost_base": "bogus"})


def test_outputs_never_reference(cfg):
    assert cfg.outputs_dir == REPO_ROOT / "outputs"
    bad = cfg.with_overrides({"paths.outputs": "/Volumes/cccr-lab/001_projects/003_cosmos-adapt/011_DAMAGES_results_final"})
    with pytest.raises(ValueError):
        bad.outputs_dir


def _load_v1_s000():
    path = REPO_ROOT / "pipeline" / "S000_project_config_cosmos_adapt.py"
    spec = importlib.util.spec_from_file_location("v1_S000", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except FileNotFoundError as e:  # S000 raises when neither COSMOS_DATA_ROOT nor the lab share exists
        pytest.skip(str(e))
    return mod


def test_matches_v1_s000(cfg):
    v1 = _load_v1_s000()
    assert cfg.return_periods == v1.RP_list
    assert cfg.dems == v1.DEM_list
    assert cfg.dem_year == v1.dem_year_map
    assert cfg.cba["nyr"] == v1.NYR
    assert cfg.cba["discount_rates"][0] == v1.DISCOUNT_RATES[0]
    assert cfg.damage["usd_update"] == v1.USD_VALUE_UPDATE
    assert cfg.damage["meters_to_feet"] == v1.meters_to_feet
    assert cfg.costs["dune_reconstruction_factor"] == v1.FACTOR_RECONSTRUCTION_DUNES
    assert cfg.road_cost_per_meter == v1.road_damage_value_per_meter
    r = cfg.rent_ratios
    for name in ["rpr_ret", "rpr_off", "rpr_ind", "rr_ret", "rr_off", "rr_rest", "rr_ind",
                 "rr_ret_rest", "rr_ret_off", "rpr_ret_off"]:
        assert r[name] == pytest.approx(getattr(v1, name), rel=1e-15), name
    for sid in v1.VALID_SITES:
        assert cfg.site(sid).adapt_names == v1.get_adaptation_names(sid)
    for v in [20, "50", 2085, "dem020"]:
        assert normalize_dem(v) == v1.normalize_dem(v)
    assert cfg.project_dir == v1.project_root_directory
    assert cfg.inputs_dir == v1.datadir_damages
    assert cfg.damage_tables_dir == v1.damage_table_directory
    assert cfg.recovery_time_file.parent == v1.indirectdamages_max_recovery_time_directory
    assert cfg.multipliers_file.parent == v1.indirectdamages_multiplier_directory
    assert cfg.zillow_file.parent == v1.indirectdamages_zillow_directory


@pytest.mark.regression
def test_input_files_exist(cfg):
    zillow_ok = cfg.zillow_file.is_file() or (cfg.zillow_file.parent / "zillow_rent_ols_coefficients.csv").is_file()
    assert zillow_ok, cfg.zillow_file
    for f in [cfg.recovery_time_file, cfg.multipliers_file,
              cfg.damage_tables_dir / cfg.damage["structure_table"],
              cfg.damage_tables_dir / cfg.damage["contents_table"]]:
        assert f.is_file(), f
    for s in cfg.available_regression_sites:
        assert cfg.unit_cost_table(s).is_file()
        assert cfg.dimensions_table(s, "seawall").is_file()
        assert s.reference_dir.is_dir()
