import numpy as np
import pandas as pd
import pytest

from coastal_risk_cba import risk

RPS = [5, 20, 50, 100]


MARIN = ([39_530_441, 57_056_634, 70_467_192, 105_966_720], [10, 50, 100, 500])


def test_marin_aed():
    # v1 aux self-test value; it holds for anchor RP 1 (the v1 default before commit 0029489 moved it to 2)
    assert risk.aed(*MARIN, anchor_rp=1) == pytest.approx(22_995_537, abs=1)
    assert risk.aed(*MARIN, anchor_rp=2) == pytest.approx(13_112_926, abs=1)


def test_aed_bitwise_equal_to_v1():
    import importlib.util
    from coastal_risk_cba.config import REPO_ROOT
    path = REPO_ROOT / "pipeline" / "aux_scripts" / "damage_calculation_tools.py"
    spec = importlib.util.spec_from_file_location("v1_tools", path)
    v1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v1)
    rng = np.random.default_rng(0)
    for _ in range(200):
        d = rng.uniform(-1e6, 1e8, 4)
        for anchor in (1, 2, 3):
            assert risk.aed(d, RPS, anchor) == v1.annual_expected_damage_numint(d, RPS, anchor_rp=anchor)


def test_aed_hand_value_and_anchor():
    # one RP: triangle from (p=1/2, 0) to (p=1/5, 100): 50 * 0.3
    assert risk.aed([100], [5], anchor_rp=2) == pytest.approx(15.0)
    assert risk.aed([100], [5], anchor_rp=1) == pytest.approx(40.0)
    with pytest.raises(ValueError):
        risk.aed([100], [5], anchor_rp=5)


def test_aed_clipped_and_unsorted():
    assert risk.aed([-10, -20, -30, -40], RPS) == 0.0
    d = [1, 4, 9, 16]
    assert risk.aed(d[::-1], RPS[::-1]) == risk.aed(d, RPS)


def test_exceedance_curve():
    c = risk.exceedance_curve([10, 20, 30, 40], RPS)
    assert list(c["rp"]) == [100, 50, 20, 5, 2]
    assert list(c["loss"]) == [40, 30, 20, 10, 0]
    assert c["p"].is_monotonic_increasing


def test_var_on_nodes_and_between():
    loss = [10, 20, 30, 40]
    assert risk.value_at_risk(loss, RPS, 0.99) == pytest.approx(40)
    assert risk.value_at_risk(loss, RPS, 0.98) == pytest.approx(30)
    assert risk.value_at_risk(loss, RPS, 0.95) == pytest.approx(20)
    # p = 0.03 between 1/50 and 1/20, linear in p
    assert risk.value_at_risk(loss, RPS, 0.97) == pytest.approx(30 + (20 - 30) * (0.03 - 0.02) / (0.05 - 0.02))
    assert np.isnan(risk.value_at_risk(loss, RPS, 0.999))
    assert risk.value_at_risk(loss, RPS, 0.4) == 0.0


def test_es_flat_tail_and_truncated():
    loss = [10, 20, 30, 40]
    # level 0.99: q = p_min, body 0 -> flat ES = L(p_min); truncated = 0
    assert risk.expected_shortfall(loss, RPS, 0.99, tail="flat") == pytest.approx(40)
    assert risk.expected_shortfall(loss, RPS, 0.99, tail="truncated") == pytest.approx(0, abs=1e-9)
    # level 0.98: body = trapezoid 0.01..0.02 of 40->30 = 0.35; head = 0.01*40
    assert risk.expected_shortfall(loss, RPS, 0.98) == pytest.approx((0.35 + 0.4) / 0.02)
    assert risk.expected_shortfall(loss, RPS, 0.98) >= risk.value_at_risk(loss, RPS, 0.98)


def test_es_truncated_at_anchor_equals_aed():
    # ES over the whole curve (q = 1/anchor) with truncated tail = AED / q
    loss = [10, 20, 30, 40]
    assert risk.expected_shortfall(loss, RPS, 0.5, tail="truncated") * 0.5 == pytest.approx(risk.aed(loss, RPS))


def _alld():
    rows = []
    dmg = {"no_adaptation": [100, 200, 300, 400], "seawall": [0, 50, 150, 300], "reef": [101, 199, 300, 400]}
    for unit, scale in [("a", 1.0), ("b", 10_000.0)]:
        for adapt, d in dmg.items():
            for rp, v in zip(RPS, d):
                rows.append({"cba_study_area": unit, "dem": "dem020", "adapt": adapt, "rp": rp,
                             "tot_cost": v * scale, "population": v / 100, "building_count": v / 50})
    return pd.DataFrame(rows)


def test_aeb_equals_aed_difference():
    alld = _alld()
    aed = risk.aed_table(alld).set_index(["cba_study_area", "adapt"])
    aeb = risk.aeb_table(alld).set_index(["cba_study_area", "adapt"])
    for unit in "ab":
        expected = aed.loc[(unit, "no_adaptation"), "aed"] - aed.loc[(unit, "seawall"), "aed"]
        assert aeb.loc[(unit, "seawall"), "aeb"] == pytest.approx(expected)
        assert aeb.loc[(unit, "no_adaptation"), "aeb"] == 0
        assert aeb.loc[(unit, "seawall"), "aed_wo_adapt"] == aed.loc[(unit, "no_adaptation"), "aed"]


def test_noise_floor():
    alld = _alld()
    # reef differs from baseline by |1| at two RPs: 1 % of 100 and 0.5 % of 200
    raw = risk.benefit_by_rp(alld).query("adapt == 'reef' and cba_study_area == 'a'")
    assert list(raw["benefit"]) == [-1, 1, 0, 0]
    floored = risk.benefit_by_rp(alld, noise_floor_frac=0.01).query("adapt == 'reef' and cba_study_area == 'a'")
    assert list(floored["benefit"]) == [-1, 0, 0, 0]  # |-1| == 1 % of 100 is not below the floor
    floored = risk.benefit_by_rp(alld, noise_floor_frac=0.011).query("adapt == 'reef' and cba_study_area == 'a'")
    assert list(floored["benefit"]) == [0, 0, 0, 0]
    assert risk.aeb_table(alld, noise_floor_frac=0.011).query("adapt == 'reef'")["aeb"].eq(0).all()


def test_inclusion_flag():
    alld = _alld()
    flag = risk.inclusion_flag(alld, threshold_usd=1_000)
    assert flag.to_dict() == {"a": 0, "b": 1}


def test_sum_by_unit_fills_and_drops_roads():
    b = pd.DataFrame({"cba_study_area": ["a", "a", None], "tot_cost": [1.04, 2.0, 99.0],
                      "population": [1, 2, 0], "building_count": [1, 1, 0]})
    s = risk.sum_by_unit(b, ["a", "c"], rp=5, dem="dem020", adapt="seawall")
    assert s.set_index("cba_study_area")["tot_cost"].to_dict() == {"a": 3.0, "c": 0.0}
    assert set(s["rp"]) == {5}


def test_tail_risk_table_total_row():
    t = risk.tail_risk_table(_alld(), levels=(0.99,))
    tot = t[(t["cba_study_area"] == "TOTAL") & (t["adapt"] == "no_adaptation")]
    assert tot["var"].iloc[0] == pytest.approx(400 + 400 * 10_000)
