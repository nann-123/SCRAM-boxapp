from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "core" / "executables_or_wrappers" / "runtime"


def platform_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def root_venv_python() -> Path:
    """Return the Python executable inside the project-root ``.venv`` (the standard location)."""
    if sys.platform.startswith("win"):
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def platform_venv_python(platform_dir: Path) -> Path:
    """Return the Python executable inside the platform-specific legacy ``.venv``."""
    if sys.platform.startswith("win"):
        return platform_dir / ".venv" / "Scripts" / "python.exe"
    return platform_dir / ".venv" / "bin" / "python"


def program_name() -> str:
    return "ProgramSCRAM.exe" if sys.platform.startswith("win") else "ProgramSCRAM"


def bundled_program(platform_dir: Path) -> Path:
    return platform_dir / program_name()


def explicit_python() -> Path | None:
    raw_path = os.environ.get("SCRAM_PYTHON")
    if not raw_path:
        return None
    python_path = Path(raw_path).expanduser()
    if python_path.exists():
        return python_path
    resolved = shutil.which(raw_path)
    if resolved:
        return Path(resolved)
    raise SystemExit(f"SCRAM_PYTHON points to a missing Python interpreter: {raw_path}")


def bootstrap_python() -> str | None:
    candidates = [sys.executable]
    if sys.platform.startswith("win"):
        candidates.extend(["python", "py", "python3"])
    else:
        candidates.extend(["python3", "python", "py"])
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def ensure_venv(platform_dir: Path) -> Path:
    # 1) Explicit SCRAM_PYTHON override — always wins.
    explicit = explicit_python()
    if explicit:
        return explicit

    # 2) Project-root .venv — the standard, portable location.
    root_python = root_venv_python()
    if root_python.exists():
        return root_python

    # 3) Platform-specific legacy .venv — backwards compatibility.
    legacy_python = platform_venv_python(platform_dir)
    if legacy_python.exists():
        return legacy_python

    # 4) Nothing found — create .venv at the project root.
    if not ROOT.exists() or not os.access(ROOT, os.W_OK):
        raise SystemExit(
            f"Project root is not writable: {ROOT}\n"
            "Make the project directory writable so the virtual environment can be created."
        )

    bootstrap = os.environ.get("SCRAM_PYTHON") or bootstrap_python()
    if bootstrap is None:
        raise SystemExit("No bootstrap Python interpreter was found to create the virtual environment.")

    subprocess.run([bootstrap, "-m", "venv", str(ROOT / ".venv")], check=True)
    subprocess.run([str(root_python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    return root_python


def main() -> int:
    platform_dir = RUNTIME_ROOT / platform_name()
    python_bin = ensure_venv(platform_dir)

    if sys.platform.startswith("linux") and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise SystemExit(
                "No graphical session was detected. Run inside a desktop session, or set QT_QPA_PLATFORM=offscreen for headless smoke tests."
            )

    env = os.environ.copy()
    if bundled_program(platform_dir).exists():
        env.setdefault("SCRAM_PROGRAMSCRAM", str(bundled_program(platform_dir)))
    env.setdefault("SCRAM_RUNTIME_PLATFORM", platform_name())
    env.setdefault("SCRAM_RUNTIME_ROOT", str(RUNTIME_ROOT))

    app_main = ROOT / "app" / "main.py"
    os.execvpe(str(python_bin), [str(python_bin), str(app_main)], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
