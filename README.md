# ADUCAT validation

Validation of the ADUCAT InSAR processing chains over Vienna. Two kinds of comparison:

* the own pipelines (**SNAP-StaMPS**, **ISCE2-Dolphin-MintPy**, **COMPASS-Dolphin**) against each other and
  against the reference products **EGMS** and **Augmenterra**;
* later, all of them against **in-situ** measurements (type and format still open).

The analysis happens in Jupyter notebooks. Code that more than one notebook needs (reading the datasets, metrics,
grids, alignment) is kept in the small package `aducat_val` in `src/`, so every notebook reads the data and
computes the metrics the same way.

## Layout

```
ADUCAT_validation/
├── README.md
├── CLAUDE.md                   # instructions for Claude Code (same template as the other ADUCAT repos)
├── docs/
│   └── conventions.md          # sign, units, CRS, temporal / spatial reference, pair order – read first
├── src/aducat_val/             # shared code, imported by the notebooks
│   ├── config.py               # metric CRS, colour maps (no data paths)
│   ├── readers.py              # one function per data source -> common point table
│   ├── metrics.py              # statistics of one dataset, agreement metrics between two
│   ├── spatial.py              # AOI, point-in-polygon, 40 m grid, nearest-neighbour pairs, line coordinates
│   ├── alignment.py            # common reference: offsets on commonly stable cells
│   ├── timeseries.py           # re-referencing, common dates, linear rates
│   └── display.py              # table formatting, small plotting helpers
├── notebooks/
│   ├── ref_InSAR/              # prepare the reference deliveries as parquet files (not a tier)
│   │   └── Augmenterra/
│   ├── t0_inputs/              # inputs shared by all pipelines (DEM, ...)
│   ├── t1_pipeline_products/   # one pipeline or reference product at a time: intermediate and final products
│   │   ├── dolphin-compass/
│   │   ├── isce2-dolphin-compass/
│   │   ├── SNAP-StaMPs/
│   │   └── ref_InSAR/          # checks of the prepared reference products (EGMS, Augmenterra)
│   ├── t2_intercomparison/     # InSAR vs InSAR: own pipelines vs the references and vs each other
│   └── t3_insitu/              # InSAR vs in-situ (not started, see its README)
└── pyproject.toml              # makes `aducat_val` installable
```

### Tiers

| Tier | Question | Typical metrics |
|---|---|---|
| **t0 inputs** | Are the inputs that all pipelines share fine (DEM, AOI, ...)? | visual checks, pixel size, coverage |
| **t1 pipeline products** | Is one pipeline run plausible on its own, from its intermediate products (interferograms, unwrapping, phase linking) to its final point file? Same for a prepared reference product. | visual checks; coverage, point density, `velocity_summary`, coherence |
| **t2 intercomparison** | Do two InSAR products agree? | `difference_metrics` on 40 m cells or point pairs, after alignment |
| **t3 in-situ** | Does InSAR agree with ground truth? | `difference_metrics` on InSAR vs station (after projection to LOS) |

`ref_InSAR/` is not a tier: its notebooks run once per delivery and write the prepared files.
In `t1_pipeline_products/` there is one subfolder per pipeline, plus `ref_InSAR/` for the reference products.

### Notebooks

| Notebook | Content | Former name |
|---|---|---|
| `ref_InSAR/Augmenterra/prep_augmenterra` | inspect the Augmenterra shapefiles, convert them to parquet, fit velocities `VEL_<start>_<end>` per period | `Augmenterra/Inspect_Augmenterra` + `Augmenterra/Calc_mean_vel_Augmenterra` |
| `t0_inputs/t0_dem` | prepared DEM (BEV DSM + COP30) over the AOI, pixel size | `06_plot_dem` |
| `t1_pipeline_products/dolphin-compass/t1_interferograms` | wrapped interferograms of a dolphin run | `dolphin/interferograms` |
| `t1_pipeline_products/dolphin-compass/t1_unwrapped_interferograms` | unwrapped interferograms of a dolphin run | `dolphin/plot_unwrapped_interferograms` |
| `t1_pipeline_products/dolphin-compass/t1_compass_dolphin_explorer` | columns, maps and S1A/S1C edge check of a COMPASS-Dolphin point file | `dolphin/dolphin_results_explorer` |
| `t1_pipeline_products/ref_InSAR/t1_reference_velocity_recalculation` | recalculated vs original velocities of Augmenterra and EGMS | `02_validation_vel_recalculation` |
| `t2_intercomparison/t2_point_geometry` | point geometry of COMPASS and ISCE2 outputs in a small area, point-pair differences | `05_visualization_point_geometry` |
| `t2_intercomparison/t2_city_wide_velocity` | all datasets on a 40 m grid, alignment, pairwise metrics and maps | `03_validation_city_wide_mean_vel` |
| `t2_intercomparison/t2_polygon_velocity_timeseries` | velocities and time series in test polygons | `01_validation_polygon_mean_vel_ts_` |
| `t2_intercomparison/t2_s1a_s1c_burst_edges_2025` | COMPASS vs ISCE2 for the 2025 S1A+S1C stack, burst-edge steps | `04_validation_pipelines_S1A-C_issue` |

The folders `t1_pipeline_products/isce2-dolphin-compass/` and `t1_pipeline_products/SNAP-StaMPs/` are still empty.
New notebooks: `<tier>_<topic>.ipynb` in the matching folder (in `t1_pipeline_products/`: the pipeline's subfolder).

## Setup

The notebooks run in the conda environment `geo_env`. Install the package once into that environment, in
editable mode so changes in `src/` take effect without reinstalling:

```bash
conda activate geo_env
pip install -e .
```

Without the installation the notebooks still work: their import cell searches the folders above the notebook
for `src/aducat_val` and imports it from there.

### Data paths

The package contains **no data paths**. Every notebook sets its file paths at the top of its configuration cell
(`DATA_DIR`, `AOI_FILE`, one `file=` per dataset). If your data is somewhere else, change them there. The readers
check that the file exists and stop with a clear message if it does not.

## Using the package in a notebook

```python
from pathlib import Path

from aducat_val import metrics, readers, spatial, alignment

DATA_DIR = Path("/home/lukas/projects/ADUCAT/data")       # where the data is on your machine

# dataset name -> file and options of its source function (velocity column, ...)
SOURCES = readers.sources({
    "EGMS": dict(file=DATA_DIR / "EGMS/vienna/EGMS_L2A_073_2020_2024.parquet", velocity="VEL_20220101_20241231"),
    "ISCE2-Dolphin-MintPy": dict(
        file=DATA_DIR / "final_outputs/isce2-dolphin-mintpy/S1_ASC_073_IW1-IW2_VV_20220101_20241228_vienna.parquet"),
})
aoi_polygon, aoi_metric = spatial.read_aoi(DATA_DIR / "AOI/Projektgebiet_ADUCAT-AOI.gpkg")
points = {name: readers.read_points(src, aoi_polygon, min_coherence=0.0) for name, src in SOURCES.items()}

grid = spatial.Grid.over(aoi_metric, 40)
cells = {name: grid.aggregate(pts, mean=("velocity", "mean"), count=("velocity", "size"))
         for name, pts in points.items()}
common = alignment.common_values(cells, "mean", min_count=3)
offsets, stable_cells, _ = alignment.stable_offsets(common, tol=1.0)
aligned = common - offsets
metrics.difference_metrics(aligned["EGMS"], aligned["ISCE2-Dolphin-MintPy"])   # ISCE2 − EGMS
```

### Readers

`readers.read_points` returns the same columns for every source:
`lon`, `lat` (EPSG:4326), `x`, `y` (EPSG:31256), `velocity` [mm/yr], `coherence`, `rg`, `row`, plus any `extras`
you ask for, with their original names. `readers.read_timeseries` returns the displacement time series [mm] of
those points (rows = points, columns = dates).

Each source function only knows the *layout* of that source's files (velocity column, coherence column,
time-series pattern, lon/lat columns or WKB), never where they are: the file is a required argument.
To add a source, write such a function in `readers.py` and add it to `SOURCES`. **SNAP-StaMPS** is registered but
raises `NotImplementedError` until its output format is fixed.

### Metrics

There is **one** `metrics.py` for all tiers, sorted by what is compared rather than by tier. InSAR vs InSAR and
InSAR vs in-situ both reduce to "two matched samples", so they use the same `difference_metrics`
(bias, median difference, MAE, RMSE, std, NMAD, share within ±2 mm/yr, Pearson r, Spearman ρ).
What differs between the tiers is how the samples are matched: grid cells, point pairs, or InSAR points around
a station projected to LOS. That matching goes into `spatial.py`, `alignment.py`, `timeseries.py` or, for
in-situ, a new module once the data format is known. It does not go into `metrics.py`.

## Status

* SNAP-StaMPS: no output yet, reader is a placeholder.
* In-situ: data type and format open; see `notebooks/t3_insitu/README.md` and the end of `docs/conventions.md`.
* EGMS download and preparation: repository `egms_download` (writes e.g. `EGMS_L2A_073_2020_2024.parquet`, which the
  EGMS reader reads directly). Older notebooks: repository `egms`.
