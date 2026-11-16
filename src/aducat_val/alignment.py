"""Common reference of several datasets.

InSAR velocities are relative to a reference point or area, so every dataset may be shifted by a constant
offset. :func:`stable_offsets` estimates that offset per dataset on cells that are stable in *all* datasets:

1. start: offset = median velocity of each dataset over all common cells,
2. commonly stable cells: |velocity − offset| ≤ tol in every dataset,
3. offset = median over the commonly stable cells; repeat 2–3 until the offsets change by < ``eps``.

The criterion is relative to each dataset's own offset, so it does not depend on the offset itself.
A remaining spatial trend (tilt) between the datasets is not removed.
"""
from __future__ import annotations

import pandas as pd


def common_values(cell_stats: dict[str, pd.DataFrame], column: str, min_count: int = 1,
                  count_column: str = "count") -> pd.DataFrame:
    """One column per dataset with ``column``, only cells where every dataset has >= ``min_count`` points."""
    return pd.concat({name: stats.loc[stats[count_column] >= min_count, column] for name, stats in cell_stats.items()},
                     axis=1, join="inner").dropna()


def stable_offsets(values: pd.DataFrame, tol: float = 1.0, max_iter: int = 50, eps: float = 1e-3):
    """Offsets on commonly stable cells (see module docstring).

    values : one column per dataset, one row per common cell (e.g. from :func:`common_values`)
    Returns (offsets Series, index of the commonly stable cells, number of iterations).
    """
    if values.empty:
        raise ValueError("no common cells: lower the minimum number of points per cell")
    offsets = values.median()
    for iteration in range(1, max_iter + 1):
        is_stable = (values - offsets).abs().le(tol).all(axis=1)
        new_offsets = values[is_stable].median()
        change = (new_offsets - offsets).abs().max()
        offsets = new_offsets
        if change < eps:
            break
    return offsets, values.index[is_stable], iteration
