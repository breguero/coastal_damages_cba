"""
plot_utils.py
breguero@ucsc.edu

Shared plotting helpers for the COSMOS-Adapt damage/benefit workflow.
Covers both Matplotlib and Plotly figure formatting.

Usage:
    from aux_scripts.plot_utils import (
        style_matplotlib_axes, damage_formatter,
        plot_matplotlib_adaptation,
        format_plotly_axes, add_plotly_rp_vlines,
        get_plotly_annotation_offset, add_plotly_year_annotations,
        add_plotly_adaptation_annotations,
        ADAPTATION_COLORS, RISK_DAMAGE_COLORS,
    )
"""

import matplotlib.pyplot as plt
import matplotlib.cm as cm
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Shared color palettes
# ---------------------------------------------------------------------------

ADAPTATION_COLORS: dict[str, str] = {
    "no_adaptation": "#000000",   # black
    "reef":          "#06B2BD",   # teal
    "seawall":       "#695A3A",   # concrete grey
    "dune":          "#E8A62C",   # sand
}

RISK_DAMAGE_COLORS: dict[str, str] = {
    "2025": "#a8c8e8",   # light blue
    "2055": "#4a86b8",   # mid blue
    "2085": "#1a3a5c",   # dark blue
}


# ---------------------------------------------------------------------------
# Matplotlib helpers
# ---------------------------------------------------------------------------

def style_matplotlib_axes(ax: plt.Axes) -> None:
    """Apply a clean, white-background style to a Matplotlib axes."""
    ax.set_facecolor("white")
    ax.patch.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(1.0)
    ax.tick_params(axis="both", colors="black")


def damage_formatter(x: float, pos) -> str:
    """
    Matplotlib tick formatter that abbreviates large dollar values.
    Formats as 'XM' (millions) or 'Xk' (thousands); otherwise plain integer.
    Pass to FuncFormatter: FuncFormatter(damage_formatter)
    """
    if abs(x) >= 1e6:
        return f"{x / 1e6:.0f}M"
    if abs(x) >= 1e3:
        return f"{x / 1e3:.0f}k"
    return f"{x:.0f}"


def plot_matplotlib_adaptation(
    ax: plt.Axes,
    scenario_data,
    no_adapt_base: dict,
    adapt: str,
    idx: int,
    colors: list,
    marker: str = "o",
    year: int = None,
    site: str = None,
) -> None:
    """
    Plot one adaptation scenario on a Matplotlib axes and annotate with
    percent-reduction labels relative to the no-adaptation baseline.

    Parameters
    ----------
    ax            : target axes
    scenario_data : DataFrame with columns ['rp', 'total_damage']
    no_adapt_base : dict mapping rp -> no-adaptation damage for the same year
    adapt         : adaptation name (e.g. 'reef', 'seawall', 'dune', 'no_adaptation')
    idx           : color index into `colors`
    colors        : list of colors (e.g. from cm.tab10)
    marker        : matplotlib marker string
    year          : year label (int), used for site-specific annotation offsets
    site          : site key (e.g. 'site001_santacruz'), used for annotation offsets
    """
    color = "black" if adapt == "no_adaptation" else colors[idx]
    ms = 8 if marker == "s" else 6
    ax.plot(
        scenario_data["rp"],
        scenario_data["total_damage"],
        marker=marker,
        markersize=ms,
        label=str(adapt),
        color=color,
    )

    if adapt == "no_adaptation":
        return

    for _, row in scenario_data.iterrows():
        rp, damage = row["rp"], row["total_damage"]
        base_damage = no_adapt_base.get(rp)
        if not base_damage or base_damage <= 0:
            continue
        reduction_pct = 100 * (base_damage - damage) / base_damage

        # Default offsets
        xoffset, yoffset = 0, 18 + idx * 8
        if adapt == "reef":
            yoffset = 30 + idx * 8
            if rp == 20:
                if year == 2025:
                    yoffset -= 60
                elif year == 2055:
                    yoffset += 15
            if site == "site001_santacruz" and rp == 50 and year == 2025:
                yoffset += 20
        if adapt == "seawall" and rp == 100:
            yoffset += 15

        ax.annotate(
            f"{reduction_pct:.1f}%",
            (rp, damage),
            textcoords="offset points",
            xytext=(xoffset, yoffset),
            ha="center",
            va="bottom",
            fontsize=16,
            color=color,
            annotation_clip=False,
        )


# ---------------------------------------------------------------------------
# Plotly helpers
# ---------------------------------------------------------------------------

def format_plotly_axes(fig: go.Figure) -> None:
    """Apply a clean axis style (box, outside ticks, no grid) to a Plotly figure."""
    shared = dict(
        showline=True,
        linewidth=1,
        linecolor="black",
        mirror=True,
        ticks="outside",
        ticklen=6,
        tickwidth=1,
        tickcolor="black",
        showgrid=False,
    )
    fig.update_xaxes(
        **shared,
        tickmode="array",
        tickvals=[5, 20, 50, 100],
        ticktext=[5, 20, 50, 100],
    )
    fig.update_yaxes(**shared)


def add_plotly_rp_vlines(
    fig: go.Figure,
    rp_values,
    ymin: float,
    ymax: float,
) -> None:
    """Add dashed vertical guide lines at each return period."""
    for rp in sorted(rp_values):
        fig.add_shape(
            type="line",
            x0=rp, x1=rp,
            y0=ymin, y1=ymax,
            line=dict(color="gray", dash="dash", width=1),
            opacity=0.5,
        )


def get_plotly_annotation_offset(
    year: int,
    rp: int = None,
    site: str = None,
) -> tuple[int, int]:
    """
    Return (xshift, yshift) for a Plotly percent-change annotation.

    Site- and year-specific overrides are encoded here so callers stay clean.
    """
    xshift, yshift = 0, -10
    if year == 2085:
        if site == "site003_venturanorth" and rp == 20:
            xshift = 20
        else:
            yshift = -15
    return xshift, yshift


def add_plotly_adaptation_annotations(
    fig: go.Figure,
    scenario_data,
    no_adapt_base: dict,
    adapt: str,
    color: str,
    year: int,
    site: str = None,
) -> None:
    """
    Annotate each point on an adaptation trace with the percent damage
    reduction relative to the no-adaptation baseline for the same year.
    Skips the no_adaptation scenario itself.

    Parameters
    ----------
    fig            : Plotly figure to annotate
    scenario_data  : DataFrame with columns ['rp', 'total_damage']
    no_adapt_base  : dict mapping rp -> no-adaptation total_damage for same year
    adapt          : adaptation name (e.g. 'reef', 'seawall', 'dune')
    color          : annotation text color
    year           : year being annotated (int), used for offset logic
    site           : site key for site-specific offset overrides
    """
    if adapt == 'no_adaptation':
        return

    for _, row in scenario_data.iterrows():
        rp, damage = row['rp'], row['total_damage']
        base_damage = no_adapt_base.get(rp)
        if not base_damage or base_damage <= 0:
            continue
        reduction_pct = 100 * (base_damage - damage) / base_damage

        xshift, yshift = 0, -10
        if site == 'site003_venturanorth' and adapt == 'reef' and rp == 20 and year == 2085:
            xshift = 20

        fig.add_annotation(
            x=rp,
            y=damage,
            text=f"{reduction_pct:.1f}%",
            showarrow=False,
            xshift=xshift,
            yshift=yshift,
            font=dict(size=16, color=color),
            align='center',
        )


def add_plotly_year_annotations(
    fig: go.Figure,
    year_data,
    base_data: dict,
    color: str,
    year: int,
    site: str = None,
) -> None:
    """
    Annotate each point on a year trace with the percent change relative to
    the base year (2025). Only annotates non-base years.

    Parameters
    ----------
    fig       : Plotly figure to annotate
    year_data : DataFrame with columns ['rp', 'total_damage']
    base_data : Series or dict mapping rp -> base-year total_damage
    color     : annotation text color
    year      : year being annotated (int)
    site      : site key for site-specific offset logic
    """
    for _, row in year_data.iterrows():
        rp, damage = row["rp"], row["total_damage"]
        base_damage = base_data.get(rp)
        if not base_damage or base_damage <= 0:
            continue
        increase_pct = 100 * (damage - base_damage) / base_damage
        xshift, yshift = get_plotly_annotation_offset(year, rp=rp, site=site)
        fig.add_annotation(
            x=rp,
            y=damage,
            text=f"{increase_pct:.1f}%",
            showarrow=False,
            xshift=xshift,
            yshift=yshift,
            font=dict(size=16, color=color),
            align="center",
        )
