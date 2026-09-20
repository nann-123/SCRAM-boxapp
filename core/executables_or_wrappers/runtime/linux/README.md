Linux runtime folder.

This folder contains a Linux-native `ProgramSCRAM` built from the bundled
source tree (`../windows/source/SCRAM1.2`), together with the smoke-test
configs, the NetCDF coefficient file and the SCRAM initialization data.

`ProgramSCRAM` is not the GUI entry point. It is the command-line simulation
core that the GUI launches internally. The Windows DLLs bundled in
`../windows/` are not needed here: the Linux build links against the system
NetCDF libraries reported by `nf-config` / `nc-config`.

Build recipe used here (Debian 12, gfortran 12.2, netCDF-Fortran 4.5.4,
netCDF 4.9.0):

    cd ../windows/source/SCRAM1.2
    FC=gfortran CC=gcc scons            # add mode=debug for -O0 -g -fcheck=bounds

Portability note: `SRC/ModuleCoeffRepartitionBoxmodel.f90` (`coeff_make_dir`)
creates output directories through the shell, so it uses `mkdir -p` on POSIX
and keeps the original `cmd /c ... mkdir` on Windows. Everywhere else the
core is plain Fortran + NetCDF and compiles unchanged.

The core expects a `RESULT/` directory next to the working directory (the GUI
creates it before each run); smoke tests run by hand must create it first.

## Role in the workflow

This folder is the **Linux** runtime: the native core built from the bundled Fortran source, used
for the standard tests and comparison runs on this platform. Rebuild it after touching Fortran code:

    bash scripts/linux/build_runtime.sh          # `debug` for -O0 -g -fcheck=bounds

**Windows** is the side for manual development and debugging, verification/review, and release
packaging (`scripts/package_app_windows.ps1`, `scripts/make_windows_devkit.ps1`).

Linux must never modify `../windows/**` or the Windows packaging scripts. This was enforced by
`scripts/linux/check_windows_parity.sh` until that guard was retired on 2026-09-20 — follow the
rule by hand.
