# Validation Checklist

## Windows Desktop App

- [x] GUI starts in offscreen smoke mode on Windows.
- [x] Default new experiment opens the non-zero `gmd_paris_full` Greater Paris scenario D template.
- [x] Loading `core/templates/baseline12h.cfg` preserves species `init_gas` and initial mass values in the GUI tables.
- [x] Output directory can be changed from the experiment tab and from the settings tab.
- [x] Pressure spinner uses a practical `1000 Pa` step instead of the previous `1900 Pa` range-derived step.
- [x] Internal/external comparison runs through `RunService` and writes both result branches.
- [x] Generated figures include distinguishable line styles for overlapping internal and external curves.
- [x] Plot generation writes final mass, final number, runtime, time-series, relative-difference, and external mixing-state figures.
- [x] Report generation now surfaces TeX compiler failures and missing PDF output in the GUI instead of silently failing.
- [x] Report generation has a built-in offline PDF fallback when LaTeX is absent or broken.
- [x] Optional Windows LaTeX dependency installer is provided under `dist/windows/dependencies/`.
- [x] Windows package resources can stage the bundled runtime and complete the standard comparison.
- [x] Windows installer creates a double-clickable application with Start Menu/Desktop shortcuts.

## Scientific Workflow

- [x] User-facing comparison target is internal mixing vs external mixing.
- [x] External mixing outputs include mixed fraction and mixed/unmixed mass by size.
- [x] Greater Paris scenario D is the primary standard experiment for the manual and smoke tests.
- [x] Summary CSV columns use `relative_difference_vs_external_*` for internal/external comparison.
- [x] Old nearest/legacy language is kept only where it describes lower-level historical implementation details.
