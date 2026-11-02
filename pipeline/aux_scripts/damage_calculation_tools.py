"""
damage_calculation_tools.py
breguero@ucsc.edu

Financial tools for the COSMOS-Adapt damage/benefit workflow:
  - Annual Expected Damage (AED) via trapezoidal numerical integration
  - NPV, PV, ROI
  - Expected Volume Loss for dunes
"""

import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Annual Expected Damage
# ---------------------------------------------------------------------------

def annual_expected_damage_numint(
    total_damages,
    return_periods,
    anchor_rp: float = 2,
    plot: bool = False,
) -> float:
    """
    Annual Expected Damage (AED) via trapezoidal integration over exceedance
    probabilities.

    Parameters
    ----------
    total_damages  : array-like, damage values for each return period
    return_periods : array-like, return periods in years
    anchor_rp      : return period appended with zero damage to close the
                     high-probability tail (default 2 years)
    plot           : if True, show diagnostic plots of T vs damage and p vs damage

    Returns
    -------
    AED : float (non-negative)

    Example
    -------
    >>> damages = [1000, 5000, 20000, 50000]
    >>> rps     = [2, 10, 50, 100]
    >>> annual_expected_damage_numint(damages, rps)
    """
    damages = np.append(np.asarray(total_damages, dtype=float), 0.0)
    T       = np.append(np.asarray(return_periods, dtype=float), anchor_rp)

    # sort ascending by return period
    idx = np.argsort(T)
    damages, T = damages[idx], T[idx]
    p = 1.0 / T

    if plot:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        axes[0].plot(T, damages, marker='o')
        axes[0].set(xlabel='Return Period (years)', ylabel='Damage',
                    title='Return Period vs Damage')
        axes[0].grid(True)
        axes[1].plot(p, damages, marker='o')
        axes[1].set(xlabel='Exceedance Probability', ylabel='Damage',
                    title='Exceedance Probability vs Damage')
        axes[1].grid(True)
        plt.tight_layout()
        plt.show()

    AED = sum(
        (damages[i] + damages[i + 1]) / 2 * (p[i] - p[i + 1])
        for i in range(len(damages) - 1)
    )
    return max(float(AED), 0.0)


# ---------------------------------------------------------------------------
# Net Present Value / Present Value / ROI
# ---------------------------------------------------------------------------

def PV(AEB, Nyr: int, discount_rate: float) -> float:
    """Present value of a constant annual benefit over Nyr years.
    AEB may be a scalar, a 1-element list, or a 1-element array."""
    aeb_scalar = float(np.squeeze(AEB))
    return float(npf.npv(discount_rate, np.full(Nyr, aeb_scalar)))


def NPV(AEB: float, Nyr: int, discount_rate: float, initial_cost: float) -> float:
    """Net present value: PV of benefits minus initial cost."""
    return PV(AEB, Nyr, discount_rate) - initial_cost


def ROI(AEB: float, Nyr: int, discount_rate: float, initial_cost: float) -> float:
    """Return on investment: (PV - cost) / cost."""
    if initial_cost <= 0:
        raise ValueError("initial_cost must be greater than zero.")
    value = PV(AEB, Nyr, discount_rate)
    return (value - initial_cost) / initial_cost


def find_investment_cost_for_bcr_1(
    AEB: float,
    cost_implementation_yr1: float,
    discount_rate: float,
    Nyr: int,
) -> float:
    """Maximum additional investment that keeps BCR ≥ 1."""
    return PV(AEB, Nyr, discount_rate) - cost_implementation_yr1


# ---------------------------------------------------------------------------
# Expected Volume Loss (dunes)
# ---------------------------------------------------------------------------

def annual_expected_damage_dunes(
    volume_loss,
    return_periods,
    title_name: str = "Dune Area",
    anchor_rp: float = 1,
    plot: bool = False,
) -> float:
    """
    Expected annual volume loss for dunes via trapezoidal integration.

    Parameters
    ----------
    volume_loss    : array-like, volume loss (m³) per return period
    return_periods : array-like, return periods in years
    title_name     : label used in diagnostic plots
    anchor_rp      : return period appended with zero loss (default 1 year)
    plot           : if True, show diagnostic plots

    Returns
    -------
    EVL : float (non-negative)
    """
    vl = np.append(np.asarray(volume_loss, dtype=float), 0.0)
    T  = np.append(np.asarray(return_periods, dtype=float), anchor_rp)

    idx = np.argsort(T)
    vl, T = vl[idx], T[idx]
    p = 1.0 / T

    if plot:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        axes[0].plot(T, vl, marker='o')
        axes[0].set(xlabel='Return Period (years)', ylabel='Volume loss (m³)',
                    title=f'Return Period vs Volume loss — {title_name}')
        axes[0].grid(True)
        axes[1].plot(p, vl, marker='o')
        axes[1].set(xlabel='Exceedance Probability', ylabel='Volume loss (m³)',
                    title=f'Exceedance Probability vs Volume loss — {title_name}')
        axes[1].grid(True)
        plt.tight_layout()
        plt.show()

    EVL = sum(
        (vl[i] + vl[i + 1]) / 2 * (p[i] - p[i + 1])
        for i in range(len(vl) - 1)
    )
    return max(float(EVL), 0.0)


# ---------------------------------------------------------------------------
# Self-test (only runs when executed directly, not on import)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # Validation against Marin County reference value ($22,995,537)
    damages_marin = [39_530_441, 57_056_634, 70_467_192, 105_966_720]
    rps_marin     = [10, 50, 100, 500]
    aed = annual_expected_damage_numint(damages_marin, rps_marin)
    print(f"Marin County AED (expected ~$22,995,537): ${aed:,.0f}")

    # Dune example
    # vl  = [29876, 38092, 41240, 43589]
    # rps = [5, 20, 50, 100]
    # VD0 = 48424
    # vl_capped = [min(v, VD0) for v in vl]
    # evl = annual_expected_damage_dunes(vl_capped, rps, plot=True)
    # print(f"Expected Volume Loss: {evl:,.0f} m³  |  Ratio: {evl/VD0:.3f}")
