"""Metrics shared by all tiers.

The metrics are organised by *what* is compared, not by tier, so the same functions serve the
InSAR intercomparison (t2) and the in-situ validation (t3):

* one dataset: :func:`velocity_summary`, :func:`coherence_shares`, :func:`nmad`
* two datasets on matched samples (cells, point pairs, InSAR vs station, dates):
  :func:`difference_metrics`, :func:`difference_metrics_by`

Matching the samples (gridding, nearest-neighbour pairing, projecting GNSS to LOS, re-referencing time
series) is not a metric and lives in ``spatial``, ``alignment`` and ``timeseries``.

Differences are always ``second − first`` (see docs/conventions.md).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def nmad(values) -> float:
    """Normalised median absolute deviation, 1.4826 · median(|x − median(x)|); ≈ std for normal data."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if x.size else np.nan


def velocity_summary(v, stable: float = 2.0, moving: float = 5.0, unit: str = "mm/yr") -> pd.Series:
    """Summary statistics of one velocity sample (percentiles, IQR, share stable / moving)."""
    v = pd.Series(v, dtype=float).dropna()
    q = v.quantile([0.02, 0.25, 0.5, 0.75, 0.98]).to_numpy() if len(v) else np.full(5, np.nan)
    return pd.Series({
        "points": len(v),
        "mean": v.mean(),
        "std": v.std(),
        "min": v.min(),
        "P2": q[0],
        "P25": q[1],
        "median": q[2],
        "P75": q[3],
        "P98": q[4],
        "max": v.max(),
        "IQR": q[3] - q[1],
        "NMAD": nmad(v),
        f"|v| ≤ {stable:g} {unit} [%]": 100 * (v.abs() <= stable).mean(),
        f"v ≤ −{moving:g} {unit} [%]": 100 * (v <= -moving).mean(),
        f"v ≥ +{moving:g} {unit} [%]": 100 * (v >= moving).mean(),
    })


def coherence_shares(coherence, thresholds=(0.3, 0.5, 0.6, 0.7, 0.8, 0.9)) -> dict:
    """Share of points [%] at or above each coherence threshold (NaN counts as below)."""
    c = pd.Series(coherence, dtype=float)
    return {f"≥ {t}": 100 * (c >= t).mean() for t in thresholds}


def difference_metrics(first, second, within: float = 2.0, unit: str = "mm/yr") -> dict:
    """Agreement of two matched samples (same index / same order); difference = second − first.

    N           : number of matched samples with a value in both
    bias        : mean difference;  median diff.: robust bias
    MAE / RMSE  : mean absolute / root mean square difference
    std / NMAD  : spread of the difference (classic / robust) – independent of a constant offset
    |diff| ≤ x  : share of samples that agree within ``within``
    Pearson r / Spearman ρ : linear / rank correlation
    """
    df = pd.concat({"a": pd.Series(first, dtype=float), "b": pd.Series(second, dtype=float)}, axis=1).dropna()
    d = df["b"] - df["a"]
    return {
        "N": len(df),
        f"bias [{unit}]": d.mean(),
        f"median diff. [{unit}]": d.median(),
        f"MAE [{unit}]": d.abs().mean(),
        f"RMSE [{unit}]": float(np.sqrt((d ** 2).mean())) if len(d) else np.nan,
        f"std diff. [{unit}]": d.std(),
        f"NMAD [{unit}]": nmad(d),
        f"|diff| ≤ {within:g} {unit} [%]": 100 * (d.abs() <= within).mean() if len(d) else np.nan,
        "Pearson r": df["a"].corr(df["b"]),
        "Spearman ρ": df["a"].corr(df["b"], method="spearman"),
    }


def difference_metrics_by(first, second, groups, **kwargs) -> pd.DataFrame:
    """:func:`difference_metrics` per group (e.g. per minimum point count, river side, land cover).

    ``groups`` is a Series aligned with first / second (or a dict {label: boolean mask}).
    Returns one row per group.
    """
    first, second = pd.Series(first, dtype=float), pd.Series(second, dtype=float)
    if isinstance(groups, dict):
        masks = groups
    else:
        groups = pd.Series(groups, index=first.index)
        masks = {g: groups == g for g in pd.unique(groups.dropna())}
    return pd.DataFrame({label: difference_metrics(first[m], second[m], **kwargs) for label, m in masks.items()}).T
