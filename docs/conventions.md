# Conventions

These rules apply to every reader, metric and notebook in this repository. If a source does not follow them
natively, its reader (`src/aducat_val/readers.py`) or its preparation step converts it.

## Sign and direction

* All displacements and velocities are **line of sight (LOS)** unless a column name says otherwise.
* **Negative = movement away from the satellite** (range increase, e.g. subsidence),
  positive = towards the satellite.
* Colour maps: `turbo_r` for velocities (red = negative), `RdBu` for differences.

## Units

| Quantity | Unit |
|---|---|
| displacement (time series) | mm |
| velocity | mm/yr (1 yr = 365.25 days) |
| coordinates | degrees (lon/lat), metres (metric CRS) |
| heights | m; say whether ellipsoidal (WGS84) or orthometric. The prepared DEM is ellipsoidal |

## Coordinate reference systems

| Use | CRS |
|---|---|
| selecting points, storing positions (`lon`, `lat`) | EPSG:4326 |
| all metric work: areas, distances, grids, maps (`x`, `y`) | **EPSG:31256** (MGI / Austria GK East), `config.METRIC_CRS` |

Native geometry of the sources (the readers convert it):

| Source | Geometry in the file |
|---|---|
| Augmenterra (prepared parquet) | WKB, EPSG:4326, no lon/lat columns |
| EGMS (prepared parquet) | WKB, EPSG:4326, no lon/lat columns |
| COMPASS-Dolphin | WKB in UTM 33N (EPSG:32633) + `lon`/`lat` columns |
| ISCE2-Dolphin-MintPy | WKB in CRS84 + `lon`/`lat` columns, one point per radar pixel |
| SNAP-StaMPS | not defined yet |

## Temporal reference

Each source has its own reference date, at which the time series is 0:

| Source | Reference date |
|---|---|
| Augmenterra | first acquisition of the analysis (2019-01-05) |
| EGMS | no zero date: EGMS uses a modelled (virtual) temporal reference |
| COMPASS-Dolphin | first acquisition of the stack |
| ISCE2-Dolphin-MintPy | MintPy reference date, in `<stack>.metadata.json` (`product.reference_date`) |

**Before comparing time series, re-reference all of them to a common date**
(`timeseries.common_dates` and `timeseries.rereference`). The notebooks use the first common date.

## Spatial reference

InSAR velocities are relative to a reference point or area, so two datasets can differ by a constant offset.
Comparisons report both:

* **raw**: velocities as delivered,
* **aligned**: each dataset minus its median over the *commonly stable* cells (`alignment.stable_offsets`, see the
  docstring for the procedure). A remaining tilt or other spatial trend is not removed.

## Velocities and comparison period

* Default comparison period: **2022-01-01 – 2024-12-31**.
* Reference datasets: use the columns `VEL_<start>_<end>`. These are linear fits to the time series over that
  period, computed during preparation. EGMS `mean_velocity` comes from a model with a seasonal term and covers
  2020–2024, so it is not comparable to the fits.
* Own pipelines: `velocity_dolphin` (COMPASS-Dolphin) and `velocity_mintpy` (ISCE2-Dolphin-MintPy) cover the
  period of the stack. When the periods or methods differ, fit the velocity the same way for every dataset
  (`timeseries.linear_rate`).

## Differences and pair order

* A difference is always **second − first**.
* Order within a pair: references (Augmenterra, EGMS) first, then own pipelines in the order of the notebook's
  `OWN` list. For example `COMPASS-Dolphin − EGMS` and `ISCE2-Dolphin-MintPy − COMPASS-Dolphin`.
* Positive difference = the second dataset shows higher velocities (less subsidence).

## Quality / coherence

Each source computes its coherence differently, so the values are **not comparable between sources**.
Coherence thresholds are set per dataset (`MIN_COHERENCE` in the notebooks). ISCE2-Dolphin-MintPy files
already contain only points with MintPy temporal coherence ≥ 0.7.

## Names

* Dataset names are the keys of `readers.SOURCES`: `Augmenterra`, `EGMS`, `COMPASS-Dolphin`,
  `ISCE2-Dolphin-MintPy`, `SNAP-StaMPS`.
* Time-series columns are `D<YYYYMMDD>` (EGMS: `<YYYYMMDD>`); velocity-period columns are `VEL_<YYYYMMDD>_<YYYYMMDD>`.
* Own pipeline stacks are named `S1_<ASC|DSC>_<track>_<swaths>_<pol>_<start>_<end>_<area>`, for example
  `S1_ASC_073_IW1-IW2_VV_20220101_20241228_vienna`.

## Metrics

The definitions are in `src/aducat_val/metrics.py`. Key choices:

* NMAD = 1.4826 · median(|d − median(d)|), a robust spread (≈ std for normal data).
* Per-cell velocities on a 40 m grid are the default way to compare datasets with different point locations.
  Nearest-neighbour point pairs (`spatial.nearest_pairs`) are only used for small areas.

## In-situ data (to be defined)

The type and format of the in-situ data are still open. Before the t3 notebooks are written, fix:

* how 3D measurements (e.g. GNSS east/north/up) are projected to LOS. Use the unit vectors stored with the
  InSAR points (`los_east`, `los_north`, `los_up`), and check each file's sign convention first;
* how InSAR points are matched to a station (radius, minimum number of points, aggregation);
* how the temporal reference and sampling of the two time series are matched.
