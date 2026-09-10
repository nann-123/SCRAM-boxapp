Windows runtime folder.

This folder contains the Windows-native `ProgramSCRAM.exe`, the NetCDF/Fortran runtime DLLs it needs, smoke-test configs, and the copied SCRAM source tree.

`ProgramSCRAM.exe` is not the GUI entry point. It is the command-line simulation core that the packaged Windows GUI launches internally. Ordinary users should start `SCRAM BoxApp.exe` from the installer shortcut.

To rebuild `ProgramSCRAM.exe`, install a Windows Fortran/C toolchain and provide NetCDF Fortran through `NETCDF_ROOT` or `CONDA_PREFIX`, then run SCons from `source/SCRAM1.1`.

## Platform split (Windows vs Linux)

This folder is the **Windows** runtime. Windows is the side for manual development and debugging,
verification/review, and producing the installer and devkit packages. Do not modify it from Linux
tooling — `scripts/linux/check_windows_parity.sh` fails if you do.

The **Linux** side runs automated, scheduled troubleshooting only (build -> standard tests ->
invariants -> probes). Its runtime lives in `../linux/`, its toolchain in `scripts/linux/`, and its
documents in `docs/linux_debugging/`. See "Development and debugging" in the root `README.md`.
