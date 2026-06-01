from __future__ import annotations

import os
import sys
from pathlib import Path


APP_SLUG = "scram_boxapp_mixing"


def _xdg_dir(env_name: str, fallback_suffix: str) -> Path:
    base_dir = os.environ.get(env_name)
    if base_dir:
        return Path(base_dir).expanduser() / APP_SLUG
    return Path.home() / fallback_suffix / APP_SLUG


def _windows_dir(env_name: str, fallback_suffix: str) -> Path:
    base_dir = os.environ.get(env_name)
    if base_dir:
        return Path(base_dir).expanduser() / APP_SLUG
    return Path.home() / fallback_suffix / APP_SLUG


def user_config_dir() -> Path:
    if sys.platform.startswith("win"):
        return _windows_dir("APPDATA", "AppData/Roaming")
    return _xdg_dir("XDG_CONFIG_HOME", ".config")


def user_state_dir() -> Path:
    if sys.platform.startswith("win"):
        return _windows_dir("LOCALAPPDATA", "AppData/Local")
    return _xdg_dir("XDG_STATE_HOME", ".local/state")


def user_cache_dir() -> Path:
    if sys.platform.startswith("win"):
        return _windows_dir("LOCALAPPDATA", "AppData/Local") / "cache"
    return _xdg_dir("XDG_CACHE_HOME", ".cache")


def user_settings_path() -> Path:
    return user_config_dir() / "settings.json"


def user_results_root() -> Path:
    return user_state_dir() / "results" / "internal_external_mixing"


def user_report_root() -> Path:
    return user_state_dir() / "report"


def user_runtime_dir() -> Path:
    return user_state_dir() / "runtime"


def platform_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def runtime_platform_dir() -> Path:
    return user_runtime_dir() / platform_name()


def shared_runtime_root(root: Path) -> Path:
    return root / "core" / "executables_or_wrappers" / "runtime"


def shared_runtime_platform_dir(root: Path) -> Path:
    return shared_runtime_root(root) / platform_name()


def user_generated_configs_root() -> Path:
    return user_cache_dir() / "generated_configs"
