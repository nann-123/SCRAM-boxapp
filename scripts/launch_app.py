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


def venv_python(platform_dir: Path) -> Path:
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
    explicit = explicit_python()
    if explicit:
        return explicit

    python_bin = venv_python(platform_dir)
    if python_bin.exists():
        return python_bin

    if not platform_dir.exists() or not os.access(platform_dir, os.W_OK):
        raise SystemExit(
            f"Bundled virtual environment not found: {python_bin}\n"
            "Install the shared package with a prebuilt venv, or make the runtime directory writable so it can be created."
        )

    bootstrap = os.environ.get("SCRAM_PYTHON") or bootstrap_python()
    if bootstrap is None:
        raise SystemExit("No bootstrap Python interpreter was found to create the bundled virtual environment.")

    subprocess.run([bootstrap, "-m", "venv", str(platform_dir / ".venv")], check=True)
    subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    return python_bin


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
