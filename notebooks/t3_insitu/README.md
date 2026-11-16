# t3: validation against in-situ data

Empty so far: the type and format of the in-situ data are not decided yet.

When they are:

1. Add a reader to `src/aducat_val/readers.py`, with `kind="insitu"` and the same core columns where they make sense
   (`lon`, `lat`, `x`, `y`, time series in mm).
2. Put matching steps (projection to LOS, pairing InSAR points to a station, temporal alignment) in
   `src/aducat_val/` as well, not in the notebooks.
3. Compare with the metrics from `src/aducat_val/metrics.py`, mainly `difference_metrics`.

Open questions are listed at the end of `docs/conventions.md`.
