from __future__ import annotations

import json
from pathlib import Path

from app.services import deployment_paths


class SettingsService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = deployment_paths.user_settings_path()
        self.legacy_path = root / "app" / "resources" / "settings.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, object]:
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return self._merge_defaults(loaded)
        if self.legacy_path.exists():
            loaded = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            return self._merge_defaults(loaded)
        return self._merge_defaults({})

    def save(self, data: dict[str, object]) -> None:
        self.path.write_text(json.dumps(self._merge_defaults(data), indent=2, ensure_ascii=False), encoding="utf-8")

    def _merge_defaults(self, data: dict[str, object]) -> dict[str, object]:
        default_output_directory = str(deployment_paths.user_results_root())
        requested_output_text = str(data.get("default_output_directory", default_output_directory)).strip() or default_output_directory
        requested_output_directory = Path(requested_output_text).expanduser()
        output_directory = requested_output_directory if requested_output_directory.exists() else Path(default_output_directory)
        last_template = str(data.get("last_template", "gmd_paris_full"))
        return {
            "language": data.get("language", "zh_CN"),
            "default_output_directory": str(output_directory),
            "ui_mode": data.get("ui_mode", "basic"),
            "recent_configs": list(data.get("recent_configs", [])),
            "recent_results": list(data.get("recent_results", [])),
            "last_template": last_template,
        }
