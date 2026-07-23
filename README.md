# SCRAM BoxApp Internal/External Mixing

Standalone cross-platform box-model desktop application for comparing `INTERNAL_MIXING` and `EXTERNAL_MIXING` assumptions.

## Distributed package

The current copyable shared package is located at:

- `/data/Software/Models/scram_boxapp_shared_release_clean`

That package is the one to hand to other users. It contains the GUI, platform runtime folders, and the SCRAM source files needed to rerun or rebuild the native program.

## How to use the shared package

1. Copy the whole package directory to the target machine or another shared location.
2. Keep the directory structure intact.
3. Start the GUI with the launcher that matches the platform:
   - Linux: `bash scripts/run_app_linux.sh`
   - macOS: `bash scripts/run_app_macos.sh`
   - Windows: `scripts\run_app_windows.bat`
4. If the launcher cannot find a usable bundled Python environment, set `SCRAM_PYTHON` to a Python interpreter that already has the requirements installed.
5. If the bundled `ProgramSCRAM` for the current platform is missing or cannot run, set `SCRAM_PROGRAMSCRAM` to the native executable for that system.

The GUI is the normal entry point. Use it to edit cases, select the platform runtime, and run SCRAM jobs.

## Fresh Linux machine deployment

For a completely blank Linux server or workstation, create a source-first release tarball on the development machine:

```bash
bash scripts/make_linux_release.sh
```

Copy `dist/scram_boxapp_linux_fresh_*.tar.gz` to the target Linux machine, then run:

```bash
tar -xzf scram_boxapp_linux_fresh_*.tar.gz
cd scram_boxapp_linux_fresh_*
bash scripts/install_linux_fresh.sh
./scram-boxapp
```

The installer detects the Linux package manager, installs compilers/NetCDF/Python/Qt runtime libraries, creates the bundled venv, compiles `ProgramSCRAM` from the included Fortran source, deploys it, and runs smoke tests. Details are in [docs/linux_fresh_install.md](docs/linux_fresh_install.md).

## Supported user-facing assumptions

- `INTERNAL_MIXING`
- `EXTERNAL_MIXING`

The runtime still contains lower-level RDB implementation options such as `legacy`, `core_conserv`, `core_nogrow`, and `core_smallgrow`. These are implementation details; the normal GUI workflow is the internal/external mixing comparison.

For RDB invariant smoke testing on Linux, run `python scripts/check_rdb_core_invariants.py` after rebuilding `ProgramSCRAM`.

Weighted or LCP research paths are intentionally excluded from the user app.

## Install on macOS

```bash
cd scram_boxapp_shared_release_clean
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

## Install on Linux

```bash
cd scram_boxapp_shared_release_clean
bash scripts/run_app_linux.sh
```

For shared installations, see [docs/linux_shared_install.md](docs/linux_shared_install.md).

For the platform-aware runtime tree and packaging helper, see [docs/shared_runtime_layout.md](docs/shared_runtime_layout.md).

Notes for Linux:

- You do not need to activate `.venv` manually. The launcher uses `.venv/bin/python` directly.
- The launcher is for the desktop GUI. If you run from a plain tty with no `DISPLAY` or `WAYLAND_DISPLAY`, it now stops with a clear message instead of letting Qt abort.
- For headless smoke tests only, you can force Qt offscreen mode with `QT_QPA_PLATFORM=offscreen bash scripts/run_app_linux.sh`.
- If Qt reports `libxcb-cursor.so.0` is missing, install `libxcb-cursor0` first.
- The copied `core/executables_or_wrappers/runtime/ProgramSCRAM` in this repository came from macOS and cannot run on Linux.
- The app uses only the current platform runtime by default and refuses incompatible binaries instead of falling back to legacy sibling builds.
- You can point the app at an explicitly chosen native SCRAM executable by setting `SCRAM_PROGRAMSCRAM=/path/to/ProgramSCRAM`; incompatible executables are rejected.
- The app stages the platform runtime into the user state directory with a runtime version manifest so stale cached binaries are replaced when the bundled binary/source changes.
- The runtime still expects short config filenames, so the app stages per-run configs into the runtime directory automatically.

## Install on Windows

For normal Windows users, use the generated installer:

```bat
dist\windows\SCRAMBoxApp-Setup-windows-x64.exe
```

It installs the app to `%LOCALAPPDATA%\Programs\SCRAM BoxApp` and creates
Desktop and Start Menu shortcuts. Start the GUI from `SCRAM BoxApp.exe` or the
shortcut. Do not double-click `ProgramSCRAM.exe`; that file is the command-line
simulation core used internally by the GUI.

To rebuild the Windows GUI app, portable zip, and installer from source:

```bat
scripts\package_app_windows.bat
```

The build outputs are:

- `dist\windows\SCRAM BoxApp\SCRAM BoxApp.exe`
- `dist\windows\SCRAMBoxApp-windows-x64.zip`
- `dist\windows\SCRAMBoxApp-Setup-windows-x64.exe`

### Development setup

Create a virtual environment at the **project root** (the standard location for
development, packaging, and CESM coupling):

```bat
cd SCRAMBoxApp-WinDevKit
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

The launcher (`scripts\launch_app.py`) searches for Python in this order:
1. `SCRAM_PYTHON` environment variable (if set)
2. Project-root `.venv` (recommended)
3. `core\executables_or_wrappers\runtime\windows\.venv` (legacy fallback)
4. If none found, auto-creates `.venv` at the project root

Start the GUI:

```bat
scripts\run_app_windows.bat
```

The Windows runtime includes a native `ProgramSCRAM.exe` plus the required
NetCDF/Fortran runtime DLLs. If Python is not on `PATH`, set `SCRAM_PYTHON` to
a Python 3.10+ interpreter.

Run the standard smoke suite on Windows with:

```bat
.\.venv\Scripts\python scripts\run_standard_tests.py --template gmd_paris_full --case gmd_paris_full --output-root install_logs\standard_tests
```

## GUI workflow

1. Open the app and choose `中文` or `English`.
2. Start from the default Greater Paris full-dynamics template or load a saved `.cfg`.
3. Pick a reference template from the dropdown or load a custom `.cfg` via the
   "Load Config" button on the experiment tab. Available templates:
   - minimal BC + sulfate teaching case
   - GMD hazy condensation validation
   - GMD hazy coagulation + condensation validation
   - GMD Greater Paris scenarios A/B/C/D
4. Edit experiment cards in the top workflow view.
5. Edit structured tables in `Structure Editor`.
6. Run a single mixing assumption or compare internal vs external mixing.
7. Inspect runtime feedback in `Run Monitor`.
8. Review summary cards, plots, CSV, and logs in `Results Analysis`.
9. Generate the PDF report from `Report`; the app has an offline PDF backend and does not require LaTeX for ordinary use.

## Config matching

The GUI keeps the current SCRAM config semantics intact:

- scalar runtime/process/environment fields are edited through cards and forms
- species metadata, size bins, fraction bounds, emissions, and initial mass are edited in real tables
- GUI dimension controls rebuild table structures and serialize back to a compatible `.cfg`
- the user-facing mixing assumption is `INTERNAL_MIXING` or `EXTERNAL_MIXING`

## Results and comparison pipeline

```bash
./scripts/run_comparison_pipeline.sh
```

This pipeline runs the internal/external mixing comparison workflow, regenerates plots, and updates the Chinese report.

## Report behavior

- The GUI does not expose a user-facing LaTeX path field.
- PDF reports work offline through the built-in matplotlib/PdfPages backend.
- If `xelatex` or `tectonic` is available, the app first tries the LaTeX backend and automatically falls back to the built-in backend on failure.
- Optional LaTeX installers are provided in `dist/windows/dependencies/` and copied into `report_dependencies/` in the packaged app.
- The report generator reads `performance_summary.csv` and `final_state_summary.csv` from the current results directory.
- Those summary files are written only after a run completes successfully.
- `performance_summary.csv` is written for a completed run batch; `final_state_summary.csv` is written when both `INTERNAL_MIXING` and `EXTERNAL_MIXING` results exist for the same case.
- If you run a single scheme or the simulation aborts early, the report step will not find both files.

## Platform notes

- The bundled runtime in `core/executables_or_wrappers/runtime/` is managed internally by the app.
- The current development environment verified real macOS and Windows execution.
- Linux execution requires a Linux-native `ProgramSCRAM` because the copied macOS binary is Mach-O and cannot run on Linux.
- When a copied macOS `.venv` is detected, the Linux launcher recreates it automatically.
- Windows launch and packaging scripts are included, and the Windows runtime ships with a native `ProgramSCRAM.exe`.

## Troubleshooting

- If startup reports that the runtime core is missing, the installation is incomplete.
- Report export should always be visible because the app includes an offline PDF backend.
- If result generation fails on Windows, confirm that the packaged runtime is present and the chosen output directory is writable.
- If report generation says `final_state_summary.csv` or `performance_summary.csv` is missing, rerun the case from the GUI and make sure it finishes successfully, preferably with the compare workflow so both schemes are written.
- If LaTeX compilation fails, use the generated built-in PDF or install MiKTeX from `dist/windows/dependencies/basic-miktex-25.12-x64.exe`.
