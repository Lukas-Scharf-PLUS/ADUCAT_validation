"""Table formatting and small plotting helpers used by several notebooks."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display


def show(df: pd.DataFrame, decimals: int = 2, int_labels=("points", "N")):
    """Display a numeric table with readable number formatting.

    Rows or columns whose label (or last level of a MultiIndex label) is in ``int_labels`` are shown as integers.
    """
    def is_int(label):
        return (label[-1] if isinstance(label, tuple) else label) in int_labels

    styler = df.style.format(f"{{:,.{decimals}f}}", na_rep="–")
    int_rows = [r for r in df.index if is_int(r)]
    int_cols = [c for c in df.columns if is_int(c)]
    if int_rows:
        styler = styler.format("{:,.0f}", subset=pd.IndexSlice[int_rows, :], na_rep="–")
    if int_cols:
        styler = styler.format("{:,.0f}", subset=pd.IndexSlice[:, int_cols], na_rep="–")
    display(styler)


def style_map(ax, outline=None):
    """Map axes in metres: equal aspect, plain tick labels, optional outline (GeoDataFrame, e.g. the AOI)."""
    if outline is not None:
        outline.boundary.plot(ax=ax, color="black", lw=0.8)
    ax.set_aspect("equal")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.tick_params(labelsize=8)


def panel_axes(n: int, per_row: int = 3, width: float = 6.5, height: float = 6, **kwargs):
    """Figure with ``n`` panels, ``per_row`` per row; unused panels are hidden. Returns (fig, flat axes)."""
    ncols = max(1, min(per_row, n))
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(width * ncols, height * nrows), constrained_layout=True,
                             squeeze=False, **kwargs)
    axes = axes.ravel()
    for ax in axes[n:]:
        ax.set_visible(False)
    return fig, axes[:n]


def plot_ts_band(ax, ts: pd.DataFrame, color, label: str, max_lines: int = 300, seed: int = 0):
    """Individual time series (random sample of ``max_lines``) plus median line and P25–P75 band."""
    if len(ts) == 0:
        return
    sample = ts.sample(min(max_lines, len(ts)), random_state=seed)
    ax.plot(sample.columns, sample.T.to_numpy(), color=color, lw=0.5, alpha=0.15)
    q25, q50, q75 = ts.quantile([0.25, 0.5, 0.75]).to_numpy()
    ax.fill_between(ts.columns, q25, q75, color=color, alpha=0.3, lw=0)
    ax.plot(ts.columns, q50, color=color, lw=2, label=f"{label}: median (n = {len(ts):,})")


def metrics_box(ax, m: dict, unit: str = "mm/yr"):
    """Small text box with N, bias, RMSE, NMAD and r of a :func:`metrics.difference_metrics` result."""
    ax.text(0.03, 0.97,
            f"N = {m['N']:,.0f}\nbias = {m[f'bias [{unit}]']:.2f}\nRMSE = {m[f'RMSE [{unit}]']:.2f}\n"
            f"NMAD = {m[f'NMAD [{unit}]']:.2f}\nr = {m['Pearson r']:.3f}",
            transform=ax.transAxes, va="top", fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.8))
