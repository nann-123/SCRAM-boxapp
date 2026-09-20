Windows runtime folder.

This folder contains the Windows-native `ProgramSCRAM.exe`, the NetCDF/Fortran runtime DLLs it needs, smoke-test configs, and the copied SCRAM source tree.

`ProgramSCRAM.exe` is not the GUI entry point. It is the command-line simulation core that the packaged Windows GUI launches internally. Ordinary users should start `SCRAM BoxApp.exe` from the installer shortcut.

To rebuild `ProgramSCRAM.exe`, install a Windows Fortran/C toolchain and provide NetCDF Fortran through `NETCDF_ROOT` or `CONDA_PREFIX`, then run SCons from `source/SCRAM1.2`.

## Platform split (Windows vs Linux)

This folder is the **Windows** runtime. Windows is the side for manual development and debugging,
verification/review, and producing the installer and devkit packages.

The **Linux** side builds the native core from the bundled Fortran source and runs the standard
tests / comparison runs; its runtime lives in `../linux/`. Do not modify `../windows/**` or the
Windows packaging scripts from Linux. That rule was enforced by
`scripts/linux/check_windows_parity.sh` until the guard was retired on 2026-09-20 — follow it by
hand. See "Development and debugging" in the root `README.md`.
