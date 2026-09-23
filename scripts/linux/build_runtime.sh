#!/usr/bin/env bash
#
# Build the Linux-native ProgramSCRAM and install it into the shared runtime
# tree so the GUI can run SCRAM jobs on this machine.
#
#   bash scripts/linux/build_runtime.sh [safe|debug]
#
# "debug" builds with -O0 -g -fcheck=bounds -fbacktrace (useful when debugging
# the Fortran core); the default "safe" mode is what the shipped runtime uses.
#
# See README.md ("Install on Linux") and
# core/executables_or_wrappers/runtime/linux/README.md for background.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DIR="$ROOT/core/executables_or_wrappers/runtime/windows/source/SCRAM1.2"
RUNTIME_DIR="$ROOT/core/executables_or_wrappers/runtime/linux"
DATA_DIR="$ROOT/core/executables_or_wrappers/runtime/windows"
MODE="${1:-safe}"

say() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || die "this script builds the Linux runtime. On Windows there
  is no one-click build script: build source/SCRAM1.2 with SCons yourself and overwrite
  runtime/windows/ProgramSCRAM.exe (see docs/windows_devkit_readme_zh.md, section 9).
  Beware: scripts/package_app_windows.ps1 only packages, it does NOT build the core.
  Verify the result with: python scripts/check_runtime_version.py"

# --- prerequisites ----------------------------------------------------------
command -v gfortran  >/dev/null 2>&1 || die "gfortran not found        (Debian/Ubuntu: sudo apt install gfortran)"
command -v gcc       >/dev/null 2>&1 || die "gcc not found             (Debian/Ubuntu: sudo apt install gcc)"
command -v nf-config >/dev/null 2>&1 || die "NetCDF Fortran not found  (Debian/Ubuntu: sudo apt install libnetcdff-dev)"

if [ -x "$ROOT/.venv/bin/scons" ]; then
  SCONS="$ROOT/.venv/bin/scons"
elif command -v scons >/dev/null 2>&1; then
  SCONS="$(command -v scons)"
else
  die "SCons not found. Create the project venv first (README, 'Install on Linux') or install scons."
fi

[ -f "$SOURCE_DIR/SConstruct" ] || die "source tree missing: $SOURCE_DIR"

# --- build ------------------------------------------------------------------
say "== Building ProgramSCRAM (mode=$MODE) =="
say "   source : $SOURCE_DIR"
say "   scons  : $SCONS"
say "   netcdf : $(nf-config --version 2>/dev/null || echo '?')"
say "   fc/cc  : $(gfortran -dumpversion) / $(gcc -dumpversion)"
(
  cd "$SOURCE_DIR"
  FC="${FC:-gfortran}" CC="${CC:-gcc}" "$SCONS" "mode=$MODE"
)
[ -x "$SOURCE_DIR/ProgramSCRAM" ] || die "build reported success but $SOURCE_DIR/ProgramSCRAM is missing"

# --- install ----------------------------------------------------------------
say "== Installing into $RUNTIME_DIR =="
mkdir -p "$RUNTIME_DIR"
install -m 755 "$SOURCE_DIR/ProgramSCRAM" "$RUNTIME_DIR/ProgramSCRAM"

# Runtime data (configs, coefficient file, initial fields). These are committed
# with the repository, so they are only copied when missing.
for f in coef_s5_f3_b7.nc tutorial_linux.cfg baseline12h_boxapp.cfg coag_only_short.cfg; do
  if [ ! -f "$RUNTIME_DIR/$f" ] && [ -f "$DATA_DIR/$f" ]; then
    cp "$DATA_DIR/$f" "$RUNTIME_DIR/$f"
  fi
done
if [ ! -d "$RUNTIME_DIR/INIT" ] && [ -d "$DATA_DIR/INIT" ]; then
  cp -r "$DATA_DIR/INIT" "$RUNTIME_DIR/INIT"
fi

say "== Done =="
say "Native core : $RUNTIME_DIR/ProgramSCRAM"
say "Smoke test  :"
say "    cd \"$RUNTIME_DIR\" && mkdir -p RESULT && ./ProgramSCRAM tutorial_linux.cfg"
say "              (the core writes into RESULT/, so create it before running by hand)"
say "GUI         : $ROOT/.venv/bin/python scripts/launch_app.py"
say "Refresh     : the GUI re-stages the runtime when this folder changes; to force it,"
say "              rm -rf ~/.local/state/scram_boxapp_mixing/runtime/linux"
