Windows runtime folder.

This folder contains the Windows-native `ProgramSCRAM.exe`, the NetCDF/Fortran runtime DLLs it needs, smoke-test configs, and the copied SCRAM source tree.

`ProgramSCRAM.exe` is not the GUI entry point. It is the command-line simulation core that the packaged Windows GUI launches internally. Ordinary users should start `SCRAM BoxApp.exe` from the installer shortcut.

To rebuild `ProgramSCRAM.exe`, install a Windows Fortran/C toolchain and provide NetCDF Fortran through `NETCDF_ROOT` or `CONDA_PREFIX`, then run SCons from `source/SCRAM1.1`.
