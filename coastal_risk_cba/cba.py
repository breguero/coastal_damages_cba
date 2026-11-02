"""Present value, NPV, ROI, BCR per unit and region (v1 S030 fixed 2026-10-29, cba_tables).

breguero@ucsc.edu

Per unit, epoch (year) and measure:
- placed  = construction cost > 0.
- cost    = construction + PV(annual maintenance) if placed, else 0. With dune reconstruction on, a dune's PV(recon)
            replaces PV(maintenance) (v1 S030).
- pv      = PV(aeb) if aeb > 0 else 0.
- npv = pv - cost, roi = npv / cost, bcr = pv / cost, cost_for_bcr_1 = pv - cost  (only where placed and cost > 0).

Cost base (F1, `cost_base`):
- all_placed:     placed + zero benefit -> pv = 0, bcr = 0; not placed -> cost 0, bcr NaN, PV kept (spill-over).
- portfolio_2025: as all_placed, but only units where the measure is placed AND has aeb > 0 in the first epoch
                  carry cost, in every epoch. Other placed units are treated as not placed.
- legacy:         aeb <= 0 -> cost NaN and pv NaN (drops out of the regional cost sum; 2026 report).

Regional totals over units with include_in_bcr == 1: aeb and cost summed (NaN skipped), pv = PV(sum aeb),
bcr = pv / cost. Annuity (F2): `first_cashflow_year` 0 = v1 (npf.npv, flows at t = 0..nyr-1), 1 = t = 1..nyr.
"""

from __future__ import annotations

import numpy as np
import numpy_financial as npf
import pandas as pd

UNIT = "cba_study_area"
COST_BASES = ("all_placed", "portfolio_2025", "legacy")


def pv_factor(rate: float, nyr: int, first_cashflow_year: int = 0) -> float:
    """PV of 1 per year for `nyr` years; 20.19 (t=0) / 19.60 (t=1) at 3 %, 30 yr."""
    return pv(1.0, rate, nyr, first_cashflow_year)


def pv(annual: float, rate: float, nyr: int, first_cashflow_year: int = 0) -> float:
    """PV of a constant annual amount. first_cashflow_year=0 reproduces v1 PV() exactly."""
    flows = np.full(nyr, float(annual))
    if first_cashflow_year:
        flows = np.concatenate([np.zeros(first_cashflow_year), flows])
    return float(npf.npv(rate, flows))


def _cost_columns(costs: pd.DataFrame, dem_year: dict | None) -> pd.DataFrame:
    """Normalise a cost table (v1 all_adapt_costs) to unit, adapt, [year], adapt_cost, maint_cost, recon_cost."""
    c = costs.copy()
    if "year" not in c.columns and "dem" in c.columns:
        if dem_year is None:
            raise ValueError("cost table has 'dem' but no 'year'; pass dem_year")
        c["year"] = c["dem"].map(dem_year)
    for col in ("maint_cost", "recon_cost"):
        if col not in c.columns:
            c[col] = 0.0
    keys = [UNIT, "adapt"] + (["year"] if "year" in c.columns else [])
    if c.duplicated(keys).any():
        raise ValueError(f"duplicate cost rows for keys {keys}")
    return c[keys + ["adapt_cost", "maint_cost", "recon_cost"]]


def unit_cba(aeb: pd.DataFrame, costs: pd.DataFrame, rate: float, nyr: int = 30,
             cost_base: str = "all_placed", first_cashflow_year: int = 0,
             dune_reconstruction: bool = False, dem_year: dict | None = None) -> pd.DataFrame:
    """Per-unit CBA (v1 CBA_results_bycbastudyarea + `placed`, `in_portfolio`).

    aeb: v1 AEB_byarea[_abovethreshold] columns (unit, year, adapt, aeb, include_in_bcr). Costs without a year column
    are applied to every epoch. Missing cost rows mean "not placed".
    """
    if cost_base not in COST_BASES:
        raise ValueError(f"cost_base must be one of {COST_BASES}")
    a = aeb[aeb["adapt"] != "no_adaptation"].copy()
    if "year" not in a.columns:
        a["year"] = a["dem"].map(dem_year)
    if "include_in_bcr" not in a.columns:
        a["include_in_bcr"] = 0
    a["aeb"] = a["aeb"].clip(lower=0)  # v1 S030
    c = _cost_columns(costs, dem_year)
    keys = [k for k in (UNIT, "year", "adapt") if k in c.columns]
    df = a[[UNIT, "year", "adapt", "aeb", "include_in_bcr"]].merge(c, on=keys, how="left", validate="many_to_one")
    df[["adapt_cost", "maint_cost", "recon_cost"]] = df[["adapt_cost", "maint_cost", "recon_cost"]].fillna(0.0)

    df["placed"] = df["adapt_cost"] > 0
    if cost_base == "portfolio_2025":
        first = df["year"].min()
        sel = df[(df["year"] == first) & df["placed"] & (df["aeb"] > 0)][[UNIT, "adapt"]]
        port = pd.MultiIndex.from_frame(sel)
        df["in_portfolio"] = pd.MultiIndex.from_frame(df[[UNIT, "adapt"]]).isin(port) & df["placed"]
        carries = df["in_portfolio"]
    else:
        df["in_portfolio"] = df["placed"]
        carries = df["placed"]

    use_recon = (df["adapt"] == "dune") & dune_reconstruction
    recurring = np.where(use_recon, df["recon_cost"], df["maint_cost"])
    pv_recurring = np.array([pv(x, rate, nyr, first_cashflow_year) for x in recurring])
    cost = np.where(carries, df["adapt_cost"] + pv_recurring, 0.0)
    pv_ben = np.array([pv(b, rate, nyr, first_cashflow_year) if b > 0 else 0.0 for b in df["aeb"]])
    if cost_base == "legacy":
        zero = ~(df["aeb"] > 0)
        cost = np.where(zero, np.nan, cost)
        pv_ben_out = np.where(zero, np.nan, pv_ben)
    else:
        pv_ben_out = pv_ben

    ok = carries.to_numpy() & (np.nan_to_num(cost) > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        npv = np.where(ok, pv_ben - cost, np.nan)
        # v1 (pre-fix S030) also reports pv - 0 for spill-over units; the fixed S030 reports NaN there
        cost_bcr1 = np.where(df["aeb"] > 0, pv_ben - cost, np.nan) if cost_base == "legacy" else npv
        out = pd.DataFrame({
            UNIT: df[UNIT], "year": df["year"], "adapt": df["adapt"], "aeb": df["aeb"],
            "adaptation_cost": cost, "discount_rate": rate, "nyr": nyr,
            "roi": np.where(ok, npv / cost, np.nan),
            "cost_for_bcr_1": cost_bcr1,
            "pv": pv_ben_out, "npv": npv,
            "bcr": np.where(ok, pv_ben / cost, np.nan),
            "placed": df["placed"].astype(int),
            "in_portfolio": df["in_portfolio"].astype(int),
            "include_in_bcr": df["include_in_bcr"].astype(int),
        })
    return out


def regional_cba(units: pd.DataFrame, rate: float, nyr: int = 30, first_cashflow_year: int = 0) -> pd.DataFrame:
    """Regional totals over included units (v1 CBA_results_TOTALS + n_placed, n_cost_effective)."""
    inc = units[units["include_in_bcr"] == 1]
    g = (inc.assign(carries=inc["in_portfolio"])
         .groupby(["year", "adapt"], as_index=False)
         .agg(aeb=("aeb", "sum"), adaptation_cost=("adaptation_cost", "sum"),
              n_placed=("carries", "sum"), n_cost_effective=("bcr", lambda b: int((b > 1).sum()))))
    pv_t = np.array([pv(b, rate, nyr, first_cashflow_year) for b in g["aeb"]])
    cost = g["adaptation_cost"].to_numpy(float)
    pos = cost > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        npv = np.where(pos, pv_t - cost, np.nan)
        return pd.DataFrame({
            "year": g["year"], "adapt": g["adapt"], "aeb": g["aeb"], "adaptation_cost": cost,
            "n_placed": g["n_placed"].astype(int), "n_cost_effective": g["n_cost_effective"].astype(int),
            "discount_rate": rate, "nyr": nyr,
            "roi": np.where(pos, npv / cost, np.nan),
            "cost_for_bcr_1": np.where(g["adapt"] != "no_adaptation", pv_t - cost, np.nan),
            "pv": pv_t, "npv": npv,
            "bcr": np.where(pos, pv_t / cost, np.nan),
        })


def run(aeb: pd.DataFrame, costs: pd.DataFrame, cba_cfg: dict, dem_year: dict | None = None) -> dict:
    """Unit and regional tables for every rate in cba_cfg['discount_rates'] (F4).

    Returns {suffix: (units, totals)} with suffix 'disc030', 'disc070', ...
    """
    out = {}
    for rate in cba_cfg["discount_rates"]:
        u = unit_cba(aeb, costs, rate, cba_cfg["nyr"], cba_cfg["cost_base"], cba_cfg["first_cashflow_year"],
                     cba_cfg["dune_reconstruction"], dem_year)
        t = regional_cba(u, rate, cba_cfg["nyr"], cba_cfg["first_cashflow_year"])
        out[rate_suffix(rate)] = (u, t)
    return out


def rate_suffix(rate: float) -> str:
    """0.03 -> 'disc030' (v1 naming)."""
    return f"disc{round(rate * 1000):03d}"
