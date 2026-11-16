"""Project-wide defaults (CRS, colour maps).

No data paths here: every notebook sets its own file paths in its configuration cell, so the data can be
anywhere on each machine.
"""

# CRS of all metric work (areas, distances, grids, maps); see docs/conventions.md
METRIC_CRS = "EPSG:31256"          # MGI / Austria GK East
LONLAT_CRS = "EPSG:4326"

VELOCITY_CMAP = "turbo_r"          # red = negative (away from the satellite), blue = positive
DIFFERENCE_CMAP = "RdBu"
