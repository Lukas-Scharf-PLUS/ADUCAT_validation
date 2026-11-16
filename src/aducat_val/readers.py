"""Readers: one function per data source, all returning the same point table.

Every source function (``augmenterra``, ``egms``, ``compass_dolphin``, ``isce2_dolphin_mintpy``,
``snap_stamps``) describes *which* columns of that source's files mean what. It does not know where the data
is: the file is always given by the notebook, so everyone can keep the data where they like.
It returns a :class:`Source`. The generic functions then read any source the same way:

>>> src = egms("/path/to/EGMS_L2A_073_2020_2024.parquet")        # or source("EGMS", file=...)
>>> pts = read_points(src, aoi_polygon, extras=["los_up"])
>>> ts = read_timeseries(src, pts.iloc[:100])

Point table returned by :func:`read_points` (one row per measurement point)

========== ============================================================
column     meaning
========== ============================================================
lon, lat   position, EPSG:4326
x, y       position in ``config.METRIC_CRS`` (metres)
velocity   mean LOS velocity [mm/yr] of the column ``Source.velocity``
coherence  quality column ``Source.coherence`` (NOT comparable between sources)
rg, row    row group and row of the point in the file (used by read_timeseries)
<extras>   any further file columns asked for, with their original names
========== ============================================================

Time series returned by :func:`read_timeseries`: rows = points (same index as the point table),
columns = acquisition dates (DatetimeIndex), values = LOS displacement [mm] relative to the source's own
reference date. Conventions (sign, units, CRS, reference) are in ``docs/conventions.md``.

Adding a source: write a function that returns a ``Source`` and register it in ``SOURCES``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from pyproj import CRS, Transformer

from .config import LONLAT_CRS, METRIC_CRS
from .spatial import inside

CORE_COLUMNS = ["lon", "lat", "x", "y", "velocity", "coherence", "rg", "row"]

# Plot colour and marker per source (colour-blind safe Okabe-Ito colours), used in every notebook
COLORS = {
    "Augmenterra": "#0072B2",
    "EGMS": "#009E73",
    "COMPASS-Dolphin": "#D55E00",
    "ISCE2-Dolphin-MintPy": "#CC79A7",
    "SNAP-StaMPS": "#E69F00",
}
MARKERS = {"Augmenterra": "o", "EGMS": "^", "COMPASS-Dolphin": "s", "ISCE2-Dolphin-MintPy": "D", "SNAP-StaMPS": "v"}


@dataclass(frozen=True)
class Source:
    """Where a dataset is stored and how its columns map to the common point table."""

    name: str                      # display name, also the key in tables and plots
    kind: str                      # "pipeline" (own processing), "reference" (EGMS, Augmenterra) or "insitu"
    file: Path
    velocity: str                  # mean velocity column [mm/yr]
    coherence: str                 # quality column
    ts_pattern: str = r"D(\d{8})"  # regex of the time-series columns, group 1 = date YYYYMMDD
    lonlat: tuple[str, str] | None = ("lon", "lat")   # lon/lat columns; None = decode the WKB geometry
    color: str = "0.4"
    marker: str = "o"
    notes: dict = field(default_factory=dict, compare=False)

    def with_(self, **changes) -> "Source":
        """Copy with some fields changed, e.g. ``src.with_(velocity="VEL_20200101_20241231")``."""
        return replace(self, **changes)


# --------------------------------------------------------------------------------------------- sources
def _source(name: str, kind: str, file, velocity: str, coherence: str, **kwargs) -> Source:
    """Source with the shared colour / marker; checks that the file exists so path errors show up early."""
    file = Path(file).expanduser()
    if not file.exists():
        raise FileNotFoundError(f"{name}: file not found: {file}")
    return Source(name, kind, file, velocity, coherence, color=COLORS[name], marker=MARKERS[name], **kwargs)


def augmenterra(file: str | Path, velocity: str = "VEL_20220101_20241231") -> Source:
    """Augmenterra (reference): parquet file written by ``notebooks/prep/prep_augmenterra.ipynb``.

    Velocity columns ``VEL_<start>_<end>`` are linear fits to the time series over that period
    (``timeseries.linear_fit``); ``VEL`` is the provider velocity over the full period (also a linear fit:
    ``VEL_20190101_20260430`` reproduces it). Geometry: WKB in EPSG:4326, no lon/lat columns.
    """
    return _source("Augmenterra", "reference", file, velocity, "COHERENCE", ts_pattern=r"D(\d{8})", lonlat=None)


def egms(file: str | Path, velocity: str = "VEL_20220101_20241231") -> Source:
    """EGMS (reference): parquet file written by the ``egms_download`` repository (L2A or L2B).

    ``VEL_<start>_<end>`` are linear fits over that period; ``mean_velocity`` is the EGMS model velocity
    (includes a seasonal term). Time-series columns are plain ``YYYYMMDD``; no date is exactly 0
    (EGMS uses a modelled temporal reference). Geometry: WKB in EPSG:4326, no lon/lat columns.
    """
    return _source("EGMS", "reference", file, velocity, "temporal_coherence", ts_pattern=r"(\d{8})", lonlat=None)


def compass_dolphin(file: str | Path, velocity: str = "velocity_dolphin") -> Source:
    """COMPASS-Dolphin (own pipeline). Geocoded grid; WKB geometry in UTM 33N, lon/lat columns present.

    ``velocity_dolphin`` = Dolphin velocity; newer stacks also have ``mean_velocity`` (model fit).
    """
    return _source("COMPASS-Dolphin", "pipeline", file, velocity, "temporal_coherence")


def isce2_dolphin_mintpy(file: str | Path, velocity: str = "velocity_mintpy") -> Source:
    """ISCE2-Dolphin-MintPy (own pipeline). One point per radar pixel; WKB in CRS84, lon/lat columns present.

    ``temporal_coherence`` is the MintPy temporal coherence of the network inversion (files contain only
    points >= 0.7), a different quantity than the Dolphin temporal coherence.
    """
    return _source("ISCE2-Dolphin-MintPy", "pipeline", file, velocity, "temporal_coherence")


def snap_stamps(file: str | Path, velocity: str = "velocity") -> Source:
    """SNAP-StaMPS (own pipeline). Not available yet.

    Once the post-processed output exists, fill in the velocity / coherence / time-series column names here
    (ideally the post-processing writes the same layout as the other pipelines: lon, lat, D<YYYYMMDD> columns
    in mm, velocity in mm/yr).
    """
    raise NotImplementedError("SNAP-StaMPS output format not defined yet: implement readers.snap_stamps")


SOURCES = {
    "Augmenterra": augmenterra,
    "EGMS": egms,
    "COMPASS-Dolphin": compass_dolphin,
    "ISCE2-Dolphin-MintPy": isce2_dolphin_mintpy,
    "SNAP-StaMPS": snap_stamps,
}


def source(name: str, **options) -> Source:
    """Source by its name in ``SOURCES``; options go to the source function (file=..., velocity=...)."""
    try:
        return SOURCES[name](**options)
    except KeyError:
        raise KeyError(f"unknown source {name!r}, known: {', '.join(SOURCES)}") from None


def sources(config: dict[str, dict]) -> dict[str, Source]:
    """{name: Source} from a notebook configuration ``{name: {"file": path, "velocity": column, ...}}``."""
    return {name: source(name, **(options or {})) for name, options in config.items()}


# ------------------------------------------------------------------------------------ file metadata
def parquet_crs(pf: pq.ParquetFile) -> CRS:
    """CRS of the WKB geometry column, from the GeoParquet metadata (missing = WGS84 lon/lat)."""
    geo = (pf.schema_arrow.metadata or {}).get(b"geo")
    crs = json.loads(geo)["columns"]["geometry"].get("crs") if geo else None
    return CRS.from_json_dict(crs) if crs else CRS.from_epsg(4326)


def ts_columns(names, pattern: str, start=None, end=None) -> dict[str, pd.Timestamp]:
    """{column name: date} of all time-series columns matching ``pattern``, optionally within start..end."""
    start = pd.Timestamp(start) if start is not None else None
    end = pd.Timestamp(end) if end is not None else None
    cols = {}
    for name in names:
        match = re.fullmatch(pattern, name)
        if match:
            date = pd.Timestamp(match.group(1))
            if (start is None or date >= start) and (end is None or date <= end):
                cols[name] = date
    return cols


def file_overview(src: Source) -> dict:
    """Summary of a source file from the parquet footer only (no data read)."""
    pf = pq.ParquetFile(src.file)
    dates = pd.DatetimeIndex(sorted(ts_columns(pf.schema_arrow.names, src.ts_pattern).values()))
    return {
        "file": src.file.name,
        "size [GB]": f"{src.file.stat().st_size / 1e9:.2f}",
        "points": f"{pf.metadata.num_rows:,}",
        "row groups": pf.metadata.num_row_groups,
        "geometry CRS": parquet_crs(pf).to_string(),
        "time steps": len(dates),
        "first date": dates.min().date() if len(dates) else None,
        "last date": dates.max().date() if len(dates) else None,
        "median spacing [days]": dates.to_series().diff().dt.days.median() if len(dates) > 1 else np.nan,
        "velocity column": src.velocity,
        "coherence column": src.coherence,
    }


def attribute_columns(src: Source) -> list[str]:
    """All columns except the time series (and their ``_std`` columns)."""
    names = pq.ParquetFile(src.file).schema_arrow.names
    return [c for c in names if not re.fullmatch(src.ts_pattern + r"(_std)?", c)]


def read_metadata(src: Source) -> dict | None:
    """Processing metadata ``<file>.metadata.json`` written by the own pipelines (None if missing)."""
    meta = src.file.with_name(src.file.stem + ".metadata.json")
    return json.loads(meta.read_text()) if meta.exists() else None


# ------------------------------------------------------------------------------------------ reading
def read_points(src: Source, polygon=None, extras=(), min_coherence: float = 0.0,
                metric_crs: str = METRIC_CRS) -> pd.DataFrame:
    """Point table of one source (see module docstring), optionally only points inside ``polygon``.

    polygon       : shapely geometry in EPSG:4326, or None for the whole file
    extras        : further columns to keep, with their original names
    min_coherence : drop points with coherence below this (and NaN coherence) when > 0

    Reads one row group at a time and only the needed columns.
    """
    pf = pq.ParquetFile(src.file)
    extras = [c for c in extras if c not in (src.velocity, src.coherence)]
    value_cols = list(dict.fromkeys([src.velocity, src.coherence, *extras]))
    coord_cols = list(src.lonlat) if src.lonlat else ["geometry"]

    to_lonlat = None
    if not src.lonlat:
        data_crs = parquet_crs(pf)
        if data_crs.to_epsg() != 4326:
            to_lonlat = Transformer.from_crs(data_crs, LONLAT_CRS, always_xy=True)

    parts = []
    for rg in range(pf.metadata.num_row_groups):
        table = pf.read_row_group(rg, columns=coord_cols + value_cols)
        if src.lonlat:
            lon, lat = table[coord_cols[0]].to_numpy(), table[coord_cols[1]].to_numpy()
        else:
            xy = shapely.get_coordinates(shapely.from_wkb(table["geometry"].to_numpy()))
            lon, lat = to_lonlat.transform(xy[:, 0], xy[:, 1]) if to_lonlat else (xy[:, 0], xy[:, 1])

        keep = inside(lon, lat, polygon) if polygon is not None else np.ones(len(lon), bool)
        if min_coherence > 0:
            keep &= np.nan_to_num(table[src.coherence].to_numpy(zero_copy_only=False), nan=-np.inf) >= min_coherence
        rows = np.flatnonzero(keep)
        if not rows.size:
            continue
        part = {
            "lon": np.asarray(lon)[rows],
            "lat": np.asarray(lat)[rows],
            "velocity": table[src.velocity].to_numpy(zero_copy_only=False)[rows].astype("float32"),
            "coherence": table[src.coherence].to_numpy(zero_copy_only=False)[rows].astype("float32"),
            "rg": np.int32(rg),
            "row": rows.astype("int32"),
        }
        for col in extras:
            part[col] = table[col].to_numpy(zero_copy_only=False)[rows]
        parts.append(pd.DataFrame(part))

    if parts:
        pts = pd.concat(parts, ignore_index=True)
    else:
        pts = pd.DataFrame(columns=["lon", "lat", "velocity", "coherence", "rg", "row", *extras])
    to_metric = Transformer.from_crs(LONLAT_CRS, metric_crs, always_xy=True)
    pts["x"], pts["y"] = to_metric.transform(pts["lon"].to_numpy(float), pts["lat"].to_numpy(float))
    pts = pts[CORE_COLUMNS + extras]
    pts.attrs.update(source=src.name, file=str(src.file), metric_crs=metric_crs)
    return pts


def read_timeseries(src: Source, pts: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """Displacement time series [mm] of the given points (rows of a table from ``read_points``).

    Only the row groups that contain the points and only the dates within start..end are read.
    Rows = points (same index as ``pts``), columns = dates (sorted DatetimeIndex).
    """
    pf = pq.ParquetFile(src.file)
    cols = ts_columns(pf.schema_arrow.names, src.ts_pattern, start, end)
    if len(pts) == 0:
        return pd.DataFrame(columns=pd.DatetimeIndex(sorted(cols.values())), dtype=float)

    parts = []
    for rg, rows in pts.groupby("rg")["row"]:
        table = pf.read_row_group(int(rg), columns=list(cols)).take(rows.to_numpy())
        parts.append(table.to_pandas().set_axis(rows.index))
    ts = pd.concat(parts).loc[pts.index].rename(columns=cols)
    return ts.sort_index(axis=1).astype(float)
