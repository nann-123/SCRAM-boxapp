# Shared Runtime Layout

The distributable package uses a platform-aware runtime tree:

```text
core/executables_or_wrappers/runtime/
  linux/
    ProgramSCRAM
    .venv/
    source/
  mac/
    ProgramSCRAM
    .venv/
    source/
  windows/
    ProgramSCRAM.exe
    .venv/
    source/
```

## Resolution Order

The launcher and GUI resolve runtime assets in this order:

1. `SCRAM_PROGRAMSCRAM` if explicitly set.
2. Bundled `core/executables_or_wrappers/runtime/<platform>/ProgramSCRAM[.exe]`.
3. The staged per-user runtime copy under the app state directory, for example `~/.local/state/scram_boxapp_mixing/runtime/<platform>/` on Linux.

## Virtual Environment Order

1. `core/executables_or_wrappers/runtime/<platform>/.venv/` if present.
2. An auto-created venv in the same folder if the installation tree is writable.
3. A bootstrap Python interpreter only for creating the bundled venv.

The GUI runs from the selected platform venv once it exists.

## Source Copy

Each platform runtime folder can carry a copy of the upstream SCRAM source tree under `source/` so the native `ProgramSCRAM` can be rebuilt if the shipped binary cannot run on a target system.

Only the required SCRAM source and asset files are packaged into that `source/` tree:

- `README`
- `SConstruct`
- `INC/`
- `INIT/`
- `SRC/`
- `COEFF_REPARTITION/`
- `coef_s1_f1_b7.nc`
- `coef_s5_f3_b7.nc`

## Packaging Intent

This layout supports a shared read-only installation while keeping generated configs, staged runtime files, reports, and internal/external mixing results in per-user writable locations.

## Platform Roles

- `windows/` — manual development/debugging, verification/review, and release packaging.
- `linux/` — automated scheduled troubleshooting; built from `../windows/source/SCRAM1.1` via
  `scripts/linux/build_runtime.sh`.
- `mac/` — reserved (not present in this repository).

Linux-side automation must never write into `windows/`; `scripts/linux/check_windows_parity.sh`
verifies that before every scheduled round.
