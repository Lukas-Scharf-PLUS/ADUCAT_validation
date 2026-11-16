"""Time-series helpers. A time-series table has rows = points (or cells) and columns = dates (DatetimeIndex),
values = LOS displacement [mm]."""
from __future__ import annotations

import numpy as np
import pandas as pd


def reference_dates(ts: pd.DataFrame, tol: float = 1e-6) -> pd.DatetimeIndex:
    """Dates at which every row is 0, i.e. the temporal reference of the series (empty if there is none)."""
    return ts.columns[ts.abs().max(axis=0).to_numpy() < tol]


def overview(ts: pd.DataFrame) -> dict:
    """Temporal coverage of a time-series table and its reference date(s)."""
    dates = ts.columns
    return {
        "points": len(ts),
        "time steps": len(dates),
        "first date": dates.min().date() if len(dates) else None,
        "last date": dates.max().date() if len(dates) else None,
        "median spacing [days]": dates.to_series().diff().dt.days.median() if len(dates) > 1 else np.nan,
        "reference date (all values 0)": ", ".join(str(d.date()) for d in reference_dates(ts)) or "none",
    }


def common_dates(series: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Dates present in every time-series table."""
    return pd.DatetimeIndex(sorted(set.intersection(*(set(ts.columns) for ts in series.values()))))


def rereference(ts: pd.DataFrame, date) -> pd.DataFrame:
    """Shift every row so that it is 0 at ``date``."""
    return ts.sub(ts[pd.Timestamp(date)], axis=0)


def decimal_years(dates, origin=None) -> np.ndarray:
    """Time in years (365.25 days) since ``origin`` (default: first date)."""
    dates = pd.DatetimeIndex(dates)
    origin = dates[0] if origin is None else pd.Timestamp(origin)
    return np.asarray((dates - origin).days, dtype=float) / 365.25


def linear_rate(ts, dates=None) -> np.ndarray:
    """Least-squares linear rate per row [mm/yr] (rows with any NaN give NaN).

    ``ts`` is a DataFrame with date columns or an array (then ``dates`` is needed).
    """
    dates = ts.columns if dates is None else dates
    t = decimal_years(dates)
    t = t - t.mean()
    values = np.asarray(ts, dtype=float)
    with np.errstate(invalid="ignore"):
        return ((values - values.mean(axis=1, keepdims=True)) @ t) / (t @ t)


def linear_fit(values, dates, min_observations: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares line per row, skipping NaN dates row by row (vectorised).

    values           : array (n points x m dates) of displacements [mm]
    dates            : the m dates
    min_observations : rows with fewer valid dates get NaN

    Returns (rate [mm/yr], standard error of the rate [mm/yr]). The standard error is the one of
    ``np.polyfit(t, y, 1, cov=True)``: residual variance with n − 2 degrees of freedom divided by Σ(t − t̄)².
    Rows with exactly 2 valid dates have no residual degrees of freedom: their standard error is NaN.
    """
    y = np.asarray(values, dtype=np.float64)
    t = decimal_years(dates)
    valid = np.isfinite(y)
    y0 = np.where(valid, y, 0.0)

    n = valid.sum(axis=1).astype(np.float64)
    sum_t = valid @ t
    sum_tt = valid @ (t * t)
    sum_y = y0.sum(axis=1)
    sum_ty = y0 @ t

    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = sum_tt - sum_t ** 2 / n                     # Σ(t − t̄)² over the valid dates of each row
        rate = (sum_ty - sum_t * sum_y / n) / sxx
        intercept = (sum_y - rate * sum_t) / n
        residuals = np.where(valid, y - intercept[:, None] - rate[:, None] * t, 0.0)
        residual_variance = (residuals ** 2).sum(axis=1) / (n - 2)
        rate_std = np.sqrt(residual_variance / sxx)

    too_few = n < max(min_observations, 2)
    rate[too_few] = np.nan
    rate_std[too_few | (n <= 2)] = np.nan
    return rate, rate_std


def trend(series: pd.Series) -> float:
    """Linear rate [mm/yr] of one time series (NaN dates skipped), e.g. of a median time series."""
    ok = np.isfinite(series.to_numpy(dtype=float))
    if ok.sum() < 2:
        return np.nan
    return float(np.polyfit(decimal_years(series.index)[ok], series.to_numpy(dtype=float)[ok], 1)[0])
