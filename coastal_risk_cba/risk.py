"""Expected annual damage (AED), expected annual benefit (AEB), loss-exceedance curve, VaR/ES (v1 S022, aux tools).

breguero@ucsc.edu

Conventions (v1 unless configured otherwise)
- AED: trapezoidal integral of loss over annual exceedance probability p = 1/RP, closed with zero loss at
  `anchor_rp` (v1: 2) and truncated at the largest modelled RP (no tail beyond it). Clipped at 0.
- AEB: per-RP benefit b(RP) = damage_no_adapt(RP) - damage_adapt(RP), integrated the same way, clipped at 0
  (v1 `aeb`; equals AED difference for identical RPs; v1 `aeb2` dropped).
  F3: with `noise_floor_frac` > 0, |b| < noise_floor_frac * damage_no_adapt(RP) is set to 0 before integrating.
- VaR(level): loss at exceedance probability p = 1 - level on the piecewise-linear (in p) loss-exceedance curve that
  the AED integrates. NaN outside the modelled range p < 1/max(RP).
- ES(level): (1/p) * integral_0^p L(q) dq. Below p_min = 1/max(RP) the curve is unknown:
  tail='flat' holds L(p_min) (lower bound for a non-decreasing tail); tail='truncated' uses 0, consistent with AED.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

METRICS = ["tot_cost", "population", "building_count"]
UNIT = "cba_study_area"
BASELINE = "no_adaptation"


# --- single-curve functions ---------------------------------------------------------------------

def _curve(losses, return_periods, anchor_rp: float):
    """(p, loss) with the zero-loss anchor appended, sorted by ascending RP (descending p), as in v1."""
    rps = np.asarray(return_periods, dtype=float)
    if anchor_rp >= rps.min():
        raise ValueError(f"anchor_rp {anchor_rp} must be below the smallest RP {rps.min()}")
    d = np.append(np.asarray(losses, dtype=float), 0.0)
    t = np.append(rps, anchor_rp)
    idx = np.argsort(t)
    return 1.0 / t[idx], d[idx]


def aed(losses, return_periods, anchor_rp: float = 2) -> float:
    """Annual expected damage, trapezoidal over exceedance probability (v1 annual_expected_damage_numint)."""
    p, d = _curve(losses, return_periods, anchor_rp)
    total = 0.0
    for t in ((d[:-1] + d[1:]) / 2 * (p[:-1] - p[1:])).tolist():
        total += t  # plain left-to-right sum as v1; builtin sum() is compensated since Python 3.12
    return max(total, 0.0)


def exceedance_curve(losses, return_periods, anchor_rp: float = 2) -> pd.DataFrame:
    """Loss-exceedance curve points incl. the zero-loss anchor; columns rp, p, loss; ascending p."""
    p, d = _curve(losses, return_periods, anchor_rp)
    return pd.DataFrame({"rp": 1.0 / p, "p": p, "loss": d}).iloc[::-1].reset_index(drop=True)


def value_at_risk(losses, return_periods, level: float, anchor_rp: float = 2) -> float:
    """Loss exceeded with annual probability 1 - level (linear in p). NaN beyond the largest modelled RP."""
    p, d = _curve(losses, return_periods, anchor_rp)
    q = 1.0 - level
    p_asc, d_asc = p[::-1], d[::-1]
    if q < p_asc[0] - 1e-15:
        return np.nan
    if q >= p_asc[-1]:
        return 0.0
    return float(np.interp(q, p_asc, d_asc))


def expected_shortfall(losses, return_periods, level: float, anchor_rp: float = 2, tail: str = "flat") -> float:
    """Mean loss in the worst (1 - level) of years: (1/q) * integral_0^q L. See module docstring for `tail`."""
    if tail not in ("flat", "truncated"):
        raise ValueError(f"tail must be 'flat' or 'truncated', got {tail!r}")
    p, d = _curve(losses, return_periods, anchor_rp)
    q = 1.0 - level
    p_asc, d_asc = p[::-1], d[::-1]
    p_min = p_asc[0]
    if q < p_min - 1e-15:
        return np.nan
    q_eff = min(q, p_asc[-1])
    keep = p_asc < q_eff
    px = np.append(p_asc[keep], q_eff)
    dx = np.append(d_asc[keep], np.interp(q_eff, p_asc, d_asc))
    body = float(np.sum((dx[:-1] + dx[1:]) / 2 * np.diff(px)))
    head = p_min * d_asc[0] if tail == "flat" else 0.0
    return (body + head) / q


# --- tables -------------------------------------------------------------------------------------

def sum_by_unit(buildings: pd.DataFrame, units, **labels) -> pd.DataFrame:
    """Per-unit sums of tot_cost, population, building_count for one flood map (v1 S022 l.130-140).

    Rows without a unit (v1 road rows) drop out of the groupby. All `units` are present, missing filled with 0.
    tot_cost is rounded to 0.1 as in v1. `labels` (rp=, dem=, adapt=) are added as columns.
    """
    df = buildings.groupby(UNIT)[METRICS].sum().reindex(units).rename_axis(UNIT).reset_index()
    df[METRICS] = df[METRICS].fillna(0)
    for k, v in labels.items():
        df[k] = v
    df["tot_cost"] = df["tot_cost"].round(1)
    return df


def inclusion_flag(alld: pd.DataFrame, threshold_usd=500_000, metric="tot_cost",
                   adapt=BASELINE, dem="dem020", rp=50) -> pd.Series:
    """include_in_bcr per unit: baseline `metric` at (adapt, dem, rp) > threshold (v1 S022 l.712-729)."""
    base = alld[(alld["adapt"] == adapt) & (alld["dem"] == dem) & (alld["rp"] == rp)]
    flag = base.set_index(UNIT)[metric].gt(threshold_usd).astype(int)
    units = pd.Index(alld[UNIT].unique(), name=UNIT)
    return flag.reindex(units).fillna(0).astype(int).rename("include_in_bcr")


def add_inclusion(df: pd.DataFrame, flag: pd.Series) -> pd.DataFrame:
    out = df.copy()
    out["include_in_bcr"] = out[UNIT].map(flag).fillna(0).astype(int)
    return out


def aed_table(alld: pd.DataFrame, anchor_rp: float = 2) -> pd.DataFrame:
    """AED per (unit, dem, adapt) for tot_cost, population, building_count (v1 AED_byarea)."""
    rows = []
    for (unit, dem, adapt), g in alld.groupby([UNIT, "dem", "adapt"], sort=False):
        rps = g["rp"].to_numpy()
        rows.append({UNIT: unit, "dem": dem, "adapt": adapt,
                     "aed": aed(g["tot_cost"], rps, anchor_rp),
                     "aed_population": aed(g["population"], rps, anchor_rp),
                     "aed_building_count": aed(g["building_count"], rps, anchor_rp)})
    return pd.DataFrame(rows)


def aed_totals(aed_by_unit: pd.DataFrame) -> pd.DataFrame:
    """Sum over units per (dem, adapt) (v1 AED_totals)."""
    return aed_by_unit.groupby(["dem", "adapt"], as_index=False)[["aed", "aed_population", "aed_building_count"]].sum()


def _floor(b: np.ndarray, base: np.ndarray, frac: float) -> np.ndarray:
    if frac <= 0:
        return b
    return np.where(np.abs(b) < frac * np.abs(base), 0.0, b)


def benefit_by_rp(alld: pd.DataFrame, noise_floor_frac: float = 0.0) -> pd.DataFrame:
    """Per-RP benefits vs no_adaptation, on RPs common to both scenarios (v1 BENEFIT_BY_RP_byarea)."""
    rows = []
    for (unit, dem), area in alld.groupby([UNIT, "dem"], sort=False):
        base = area[area["adapt"] == BASELINE].set_index("rp")[METRICS]
        if base.empty:
            continue
        for adapt, g in area.groupby("adapt", sort=False):
            a = g.set_index("rp")[METRICS]
            rps = sorted(set(base.index) & set(a.index))
            b0, b1 = base.loc[rps], a.loc[rps]
            diff = {m: _floor((b0[m] - b1[m]).to_numpy(float), b0[m].to_numpy(float), noise_floor_frac) for m in METRICS}
            for i, rp in enumerate(rps):
                rows.append({UNIT: unit, "dem": dem, "adapt": adapt, "rp": rp,
                             "benefit": diff["tot_cost"][i],
                             "damage_no_adapt": b0["tot_cost"].iloc[i], "damage_adapt": b1["tot_cost"].iloc[i],
                             "benefit_population": diff["population"][i],
                             "benefit_building_count": diff["building_count"][i]})
    return pd.DataFrame(rows)


def aeb_table(alld: pd.DataFrame, anchor_rp: float = 2, noise_floor_frac: float = 0.0,
              aed_by_unit: pd.DataFrame | None = None) -> pd.DataFrame:
    """AEB per (unit, dem, adapt) with AED context columns (v1 AEB_byarea without aeb2)."""
    if aed_by_unit is None:
        aed_by_unit = aed_table(alld, anchor_rp)
    bbr = benefit_by_rp(alld, noise_floor_frac)
    aed_idx = aed_by_unit.set_index([UNIT, "dem", "adapt"])
    rows = []
    for (unit, dem, adapt), g in bbr.groupby([UNIT, "dem", "adapt"], sort=False):
        rps = g["rp"].to_numpy()
        a, a0 = aed_idx.loc[(unit, dem, adapt)], aed_idx.loc[(unit, dem, BASELINE)]
        rows.append({UNIT: unit, "dem": dem, "adapt": adapt,
                     "aeb": aed(g["benefit"], rps, anchor_rp),
                     "aed": a["aed"], "aed_wo_adapt": a0["aed"],
                     "aeb_population": aed(g["benefit_population"], rps, anchor_rp),
                     "aed_population": a["aed_population"], "aed_population_wo_adapt": a0["aed_population"],
                     "aeb_building_count": aed(g["benefit_building_count"], rps, anchor_rp),
                     "aed_building_count": a["aed_building_count"],
                     "aed_building_count_wo_adapt": a0["aed_building_count"]})
    return pd.DataFrame(rows)


def aeb_totals(aeb_by_unit: pd.DataFrame) -> pd.DataFrame:
    """Sum over units per (dem, adapt) (v1 AEB_totals)."""
    cols = [c for c in aeb_by_unit.columns if c.startswith(("aeb", "aed"))]
    return aeb_by_unit.groupby(["dem", "adapt"], as_index=False)[cols].sum()


def tail_risk_table(alld: pd.DataFrame, levels=(0.95, 0.98, 0.99), anchor_rp: float = 2,
                    tail: str = "flat", metric: str = "tot_cost") -> pd.DataFrame:
    """VaR and ES of `metric` per (unit, dem, adapt) and level; also for the unit sum (unit = 'TOTAL')."""
    total = alld.groupby(["dem", "adapt", "rp"], as_index=False)[metric].sum().assign(**{UNIT: "TOTAL"})
    rows = []
    for (unit, dem, adapt), g in pd.concat([alld, total]).groupby([UNIT, "dem", "adapt"], sort=False):
        rps, loss = g["rp"].to_numpy(), g[metric].to_numpy()
        for lv in levels:
            rows.append({UNIT: unit, "dem": dem, "adapt": adapt, "level": lv, "rp": round(1 / (1 - lv), 6),
                         "var": value_at_risk(loss, rps, lv, anchor_rp),
                         "es": expected_shortfall(loss, rps, lv, anchor_rp, tail)})
    return pd.DataFrame(rows)


def add_year(df: pd.DataFrame, dem_year: dict) -> pd.DataFrame:
    out = df.copy()
    out["year"] = out["dem"].map(dem_year)
    return out
