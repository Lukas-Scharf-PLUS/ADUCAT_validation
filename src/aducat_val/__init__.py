"""Shared code of the ADUCAT validation notebooks: readers, metrics and helpers.

Modules
-------
config     paths and project-wide defaults (data directory, AOI, metric CRS)
readers    one function per data source -> common point table (core columns + extras)
metrics    statistics of one dataset and agreement metrics between two datasets
spatial    AOI, point-in-polygon, regular grid, nearest-neighbour pairing, line coordinates
alignment  common reference of several datasets (offset on commonly stable cells)
timeseries time-series columns, re-referencing, linear rates
display    table formatting and small plotting helpers used by several notebooks
"""
