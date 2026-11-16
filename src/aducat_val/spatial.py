"""Spatial helpers: AOI, point-in-polygon, regular grid, point pairing, coordinates along a line."""
from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from .config import LONLAT_CRS, METRIC_CRS

M_PER_DEG = 111_320.0


def inside(lon, lat, polygon) -> np.ndarray:
    """Boolean mask of the points inside ``polygon``: bounding-box test first, exact test only for candidates."""
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    x0, y0, x1, y1 = polygon.bounds
    mask = (lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1)
    mask[mask] = shapely.contains_xy(polygon, lon[mask], lat[mask])
    return mask


def read_aoi(file, metric_crs: str = METRIC_CRS):
    """(AOI polygon in EPSG:4326 for selecting points, AOI GeoDataFrame in ``metric_crs`` for grids and maps)."""
    aoi = gpd.read_file(file)
    return aoi.to_crs(LONLAT_CRS).union_all(), aoi.to_crs(metric_crs)


def covered_area_km2(x, y, cell: float = 100) -> float:
    """Area of all ``cell`` x ``cell`` m cells that contain at least one point (coordinates in metres)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    key = np.floor(x / cell).astype(np.int64) * 10**8 + np.floor(y / cell).astype(np.int64)
    return np.unique(key).size * cell**2 / 1e6


@dataclass
class Grid:
    """Regular grid over the bounding box of an area, in metres.

    Cell id = ``row * nx + col`` (row 0 = north), so the cell of a point follows from its coordinates and
    every per-cell result (Series indexed by cell id) can be turned into an image with :meth:`to_image`.
    Only cells whose centre lies inside the area are used (``in_area``).
    """

    x0: float
    y1: float
    nx: int
    ny: int
    size: float
    in_area: np.ndarray

    @classmethod
    def over(cls, area: gpd.GeoDataFrame, size: float) -> "Grid":
        """Grid with ``size`` m cells over a GeoDataFrame in a metric CRS (e.g. the AOI)."""
        x0, y0, x1, y1 = area.total_bounds
        nx, ny = int(np.ceil((x1 - x0) / size)), int(np.ceil((y1 - y0) / size))
        cx, cy = np.meshgrid(x0 + (np.arange(nx) + 0.5) * size, y1 - (np.arange(ny) + 0.5) * size)
        in_area = shapely.contains_xy(area.union_all(), cx.ravel(), cy.ravel())
        return cls(x0, y1, nx, ny, size, in_area)

    @property
    def extent(self):
        """(left, right, bottom, top) for ``imshow``."""
        return (self.x0, self.x0 + self.nx * self.size, self.y1 - self.ny * self.size, self.y1)

    @property
    def n_cells(self) -> int:
        """Number of cells inside the area."""
        return int(self.in_area.sum())

    def centres(self, cells) -> tuple[np.ndarray, np.ndarray]:
        """Metric (x, y) of the centres of the given cell ids."""
        cells = np.asarray(cells)
        return self.x0 + (cells % self.nx + 0.5) * self.size, self.y1 - (cells // self.nx + 0.5) * self.size

    def cell_index(self, x, y) -> np.ndarray:
        """Cell id of metric coordinates; -1 outside the grid or outside the area."""
        col = np.floor((np.asarray(x, dtype=float) - self.x0) / self.size).astype(np.int64)
        row = np.floor((self.y1 - np.asarray(y, dtype=float)) / self.size).astype(np.int64)
        cell = np.where((col >= 0) & (col < self.nx) & (row >= 0) & (row < self.ny), row * self.nx + col, -1)
        ok = cell >= 0
        cell[ok] = np.where(self.in_area[cell[ok]], cell[ok], -1)
        return cell

    def aggregate(self, pts: pd.DataFrame, **named_aggs) -> pd.DataFrame:
        """Per-cell statistics of a point table with x / y columns (pandas named aggregation).

        Example: ``grid.aggregate(pts, mean=("velocity", "mean"), count=("velocity", "size"))``.
        Points outside the area are ignored. Index = cell id.
        """
        cell = self.cell_index(pts["x"], pts["y"])
        ok = cell >= 0
        return pts.loc[ok].groupby(cell[ok]).agg(**named_aggs)

    def mean_timeseries(self, pts: pd.DataFrame, ts) -> pd.DataFrame:
        """NaN-aware mean time series per cell; ``ts`` rows match ``pts`` (DataFrame or array, columns = dates)."""
        dates = ts.columns if isinstance(ts, pd.DataFrame) else None
        values = np.asarray(ts, dtype="float64")
        cell = self.cell_index(pts["x"], pts["y"])
        ok = cell >= 0
        ids, inv = np.unique(cell[ok], return_inverse=True)
        values = values[ok]
        out = np.empty((ids.size, values.shape[1]))
        for k in range(values.shape[1]):
            v = values[:, k]
            good = np.isfinite(v)
            total = np.bincount(inv[good], weights=v[good], minlength=ids.size)
            count = np.bincount(inv[good], minlength=ids.size)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[:, k] = total / count
        return pd.DataFrame(out, index=ids, columns=dates)

    def to_image(self, values: pd.Series) -> np.ndarray:
        """2D array (ny x nx) from a Series indexed by cell id; cells without a value are NaN."""
        image = np.full(self.nx * self.ny, np.nan)
        image[values.index.to_numpy()] = values.to_numpy()
        return image.reshape(self.ny, self.nx)

    def highpass(self, values: pd.Series, sigma_m: float) -> np.ndarray:
        """Image of the values minus a NaN-aware Gaussian smooth of them (σ in metres)."""
        img = self.to_image(values)
        weight = np.isfinite(img).astype(float)
        sigma = sigma_m / self.size
        smooth = gaussian_filter(np.nan_to_num(img), sigma) / np.maximum(gaussian_filter(weight, sigma), 1e-6)
        return img - smooth


def nearest_pairs(xy_from, xy_to, max_distance: float):
    """Nearest point of ``xy_to`` for every point of ``xy_from`` (n x 2 arrays, metres).

    Returns (paired mask over xy_from, index into xy_to for the paired points, distance of the paired points).
    """
    dist, idx = cKDTree(xy_to).query(xy_from, k=1)
    paired = dist <= max_distance
    return paired, idx[paired], dist[paired]


def line_coordinates(lon, lat, p1, p2):
    """(along, distance, length) in metres relative to the segment p1 -> p2 (lon/lat); distance > 0 = left side."""
    coslat = np.cos(np.deg2rad((p1[1] + p2[1]) / 2))
    ex, ey = (p2[0] - p1[0]) * M_PER_DEG * coslat, (p2[1] - p1[1]) * M_PER_DEG
    length = np.hypot(ex, ey)
    ux, uy = ex / length, ey / length
    px = (np.asarray(lon) - p1[0]) * M_PER_DEG * coslat
    py = (np.asarray(lat) - p1[1]) * M_PER_DEG
    return px * ux + py * uy, -px * uy + py * ux, length


def line_side_names(p1, p2) -> tuple[str, str]:
    """Compass names of the (left, right) side of the segment p1 -> p2."""
    nx = -(p2[1] - p1[1])
    ny = (p2[0] - p1[0]) * np.cos(np.deg2rad(p1[1]))
    left = ("north" if ny > 0 else "south") if abs(ny) >= abs(nx) else ("east" if nx > 0 else "west")
    return left, {"north": "south", "south": "north", "east": "west", "west": "east"}[left]
