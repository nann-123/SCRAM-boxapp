# SCRAM BoxApp Internal/External Mixing

Standalone cross-platform box-model desktop application for comparing `INTERNAL_MIXING` and `EXTERNAL_MIXING` assumptions.

## Distributed package

The current copyable shared package is located at:

- `/data/Software/Models/scram_boxapp_shared_release_clean`

That package is the one to hand to other users. It contains the GUI, platform runtime folders, and the SCRAM source files needed to rerun or rebuild the native program.

## What this repository contains

This repository is the **Windows development kit** (`SCRAMBoxApp-WinDevKit`): the GUI and
Python app, the Windows runtime (`ProgramSCRAM.exe` plus the required DLLs), the SCRAM
Fortran source, the Windows launch/packaging scripts, and a Linux-native core under
`core/executables_or_wrappers/runtime/linux/`.

**Division of work** — **Linux** runs automated, scheduled troubleshooting only (build the native
core → standard tests → invariants → probes → report). **Windows** is where manual development and
debugging, verification/review of what Linux proposes, and release packaging happen. The Linux
toolchain and documents live in `scripts/linux/` and `docs/linux_debugging/`; details and the four
non-conflict rules are in
[Development and debugging](#development-and-debugging-windows-and-linux).

Parts of the full shared package described in this file are **not** included here:
`scripts/run_app_linux.sh`, `scripts/run_app_macos.sh`, `scripts/make_linux_release.sh`,
`scripts/install_linux_fresh.sh`, `scripts/check_rdb_core_invariants.py`,
`scripts/run_comparison_pipeline.sh`, `docs/linux_fresh_install.md`,
`docs/linux_shared_install.md`, and `dist/`. Where this file refers to them, use the
equivalent steps under "Install on Linux" below.

## How to use the shared package

1. Copy the whole package directory to the target machine or another shared location.
2. Keep the directory structure intact.
3. Start the GUI with the launcher that matches the platform:
   - Linux: `bash scripts/run_app_linux.sh` — not part of this repository, see "Install on Linux"
   - macOS: `bash scripts/run_app_macos.sh` — not part of this repository
   - Windows: `scripts\run_app_windows.bat`
4. If the launcher cannot find a usable bundled Python environment, set `SCRAM_PYTHON` to a Python interpreter that already has the requirements installed.
5. If the bundled `ProgramSCRAM` for the current platform is missing or cannot run, set `SCRAM_PROGRAMSCRAM` to the native executable for that system.

The GUI is the normal entry point. Use it to edit cases, select the platform runtime, and run SCRAM jobs.

## Fresh Linux machine deployment

> The release and install scripts in this section belong to the full shared package and are
> **not** part of this repository. To build and run the core on a Linux machine from this
> repository, follow "Install on Linux" below instead.

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

The upstream Linux launcher (`scripts/run_app_linux.sh`) is not part of this repository.
The equivalent steps here are:

1. Create the project virtual environment at the repository root and install the requirements:

   ```bash
   cd SCRAMBoxApp-WinDevKit
   python3 -m venv .venv
   .venv/bin/python -m pip install --upgrade pip
   .venv/bin/python -m pip install -r requirements.txt
   ```

2. Build the Linux-native simulation core and install it into the shared runtime tree:

   ```bash
   bash scripts/linux/build_runtime.sh          # add "debug" for -O0 -g -fcheck=bounds
   ```

   This compiles `ProgramSCRAM` from
   `core/executables_or_wrappers/runtime/windows/source/SCRAM1.1` with `gfortran` and the
   system NetCDF libraries (`nf-config` / `nc-config`), then installs it to
   `core/executables_or_wrappers/runtime/linux/`, where the GUI looks for the platform
   runtime. A prebuilt copy is committed there; rerun the script after changing Fortran code.

   Prerequisites (Debian/Ubuntu): `sudo apt install gfortran gcc libnetcdff-dev`.

3. Start the GUI:

   ```bash
   .venv/bin/python scripts/launch_app.py
   ```

4. Run the standard smoke suite (import, GUI, report, and real model runs):

   ```bash
   .venv/bin/python scripts/run_standard_tests.py --template gmd_paris_full --case gmd_paris_full --output-root install_logs/standard_tests
   ```

For the platform-aware runtime tree, see [docs/shared_runtime_layout.md](docs/shared_runtime_layout.md).

Notes for Linux:

- You do not need to activate `.venv` manually; call `.venv/bin/python` directly.
- The GUI needs a desktop session. Headless smoke tests can force Qt offscreen mode with `QT_QPA_PLATFORM=offscreen`.
- If Qt reports `libxcb-cursor.so.0` is missing, install `libxcb-cursor0` first.
- This repository ships a Linux-native core at `core/executables_or_wrappers/runtime/linux/ProgramSCRAM`, built from the bundled Fortran source. It replaces the macOS binary referenced by earlier revisions of this file, which could not run on Linux.
- The app uses only the current platform runtime by default and refuses incompatible binaries instead of falling back to legacy sibling builds.
- You can point the app at an explicitly chosen native SCRAM executable by setting `SCRAM_PROGRAMSCRAM=/path/to/ProgramSCRAM`; incompatible executables are rejected.
- The app stages the platform runtime into the user state directory (`~/.local/state/scram_boxapp_mixing/runtime/linux/`) with a runtime version manifest so stale cached binaries are replaced when the bundled binary/source changes.
- The runtime still expects short config filenames, so the app stages per-run configs into the runtime directory automatically.
- Running the core by hand requires a `RESULT/` directory in the working directory; the GUI creates it automatically before each run.
- The Fortran core needs `SRC/ModuleCoeffRepartitionBoxmodel.f90` (`coeff_make_dir`) to create output directories, which is why it detects the platform and uses `mkdir -p` on POSIX instead of `cmd /c mkdir`.

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

## Development and debugging (Windows and Linux)

Both platforms share the same application code; only the simulation core and the tooling differ.

**Division of work**:

- **Linux** — automated, scheduled troubleshooting only: build the native core, run standard tests,
  check invariants, run probes, and report. Toolchain in `scripts/linux/`, documents in
  `docs/linux_debugging/`, all outputs under `install_logs/auto/` (git-ignored).
- **Windows** — manual development and debugging, verification/review of what Linux proposes, and
  producing the release (installer, devkit package, release screenshots).

Both sides may edit shared application code and documents; the four rules below (enforced by
`scripts/linux/check_windows_parity.sh`) keep them from conflicting.

| | Windows | Linux |
|---|---|---|
| Environment | `.venv` at the project root (devkit README §5) | same, see [Install on Linux](#install-on-linux) |
| Simulation core | `core/executables_or_wrappers/runtime/windows/ProgramSCRAM.exe` + DLLs (committed) | `core/executables_or_wrappers/runtime/linux/ProgramSCRAM` (committed; rebuild with `scripts/linux/build_runtime.sh`) |
| Start the GUI | `scripts\run_app_windows.bat` | `.venv/bin/python scripts/launch_app.py` |
| Standard tests | `.\.venv\Scripts\python scripts\run_standard_tests.py …` (devkit README §6) | same command via `.venv/bin/python` |
| Screenshots | `python scripts\capture_screenshots.py` → writes `docs/screenshots/` | `python scripts/capture_screenshots.py --out install_logs/shots` — **never overwrite the release assets** (the script pins the Windows UI font) |
| Packaging / release | `scripts\package_app_windows.bat`, `scripts\make_windows_devkit.ps1` (devkit README §8/§13) | not available — do it on Windows |
| Parity guard | `bash scripts/linux/check_windows_parity.sh` | `bash scripts/linux/check_windows_parity.sh` |

### Linux debugging toolchain

| Script | Purpose | When |
|---|---|---|
| `scripts/linux/build_runtime.sh [safe\|debug]` | Build and install the Linux core from `source/SCRAM1.1` | after touching Fortran code |
| `scripts/linux/auto_round.sh quick\|standard\|deep` | One verification round (guard → build → tests → metrics). A content signature skips rounds where nothing changed and appends one line to `install_logs/auto/digest.md` | scheduled (see the runbook) |
| `scripts/linux/collect_metrics.py --round-dir …` | Extract invariants, compare with the previous round and the documented baselines | inside a round |
| `scripts/linux/probe_cell.py` | Run one parameter cell and collect discovery signals (status, invariants, log keywords) | when hunting for new bugs |
| `scripts/linux/probe_suggest.py [--matrix] [--mark …]` | Mine the source tree and coverage matrix for the next probes; record results in `docs/linux_debugging/probe_ledger.json` | each round |
| `scripts/linux/check_windows_parity.sh` | Fails if Linux-side work would change the Windows release | before/after any change |

All outputs are git-ignored: `install_logs/auto/<timestamp>/` (one directory per round),
`install_logs/auto/digest.md` (rolling summary), `install_logs/auto/probes/` (probe results),
`dist/linux-support/` (portable Linux bundle).

### Documents for Linux debugging and automation

| Document | Role |
|---|---|
| `docs/linux_debugging/brief.md` | The rules: acceptance baselines, per-round flow, prohibitions, known pitfalls |
| `docs/linux_debugging/runbook.md` | Day-to-day usage: the prompt to hand an agent, next-morning review, scheduling tiers |
| `docs/linux_debugging/probe_backlog.md` | How new bugs are found: probe classes, coverage matrix, anti-stagnation rules |
| `docs/linux_debugging/probe_ledger.json` | Machine-readable record of probed cells and hypotheses |
| `docs/BUG_TRACKING.md` | Open bug queue (unchanged; the probe flow feeds it) |

**Non-conflict rules** (enforced by `scripts/linux/check_windows_parity.sh`):

1. Never modify `core/executables_or_wrappers/runtime/windows/**` or the two Windows packaging
   scripts from the Linux side.
2. Keep the Windows branch in shared source — e.g. `coeff_make_dir` keeps `cmd /c ... mkdir`.
3. Linux-generated screenshots are review copies only; release screenshots are regenerated on Windows.
4. Version bumps and Windows checklist items are proposals until verified on Windows.

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
./scripts/run_comparison_pipeline.sh   # full shared package only, not in this repository
```

This pipeline runs the internal/external mixing comparison workflow, regenerates plots, and updates the Chinese report.
In this repository, use the GUI compare workflow or `scripts/run_standard_tests.py` instead.

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
- This repository verifies Windows execution (`ProgramSCRAM.exe` plus DLLs) and Linux execution
  (`runtime/linux/ProgramSCRAM`, built from the bundled Fortran source).
- Linux execution requires a Linux-native `ProgramSCRAM`; `scripts/linux/build_runtime.sh` builds
  it from `core/executables_or_wrappers/runtime/windows/source/SCRAM1.1`.
- Windows launch and packaging scripts are included, and the Windows runtime ships with a native `ProgramSCRAM.exe`.

## Troubleshooting

- If startup reports that the runtime core is missing, the installation is incomplete.
- Report export should always be visible because the app includes an offline PDF backend.
- If result generation fails on Windows, confirm that the packaged runtime is present and the chosen output directory is writable.
- If report generation says `final_state_summary.csv` or `performance_summary.csv` is missing, rerun the case from the GUI and make sure it finishes successfully, preferably with the compare workflow so both schemes are written.
- If LaTeX compilation fails, use the generated built-in PDF or install MiKTeX from `dist/windows/dependencies/basic-miktex-25.12-x64.exe`.
