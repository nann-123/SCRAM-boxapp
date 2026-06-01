from __future__ import annotations

import json
from pathlib import Path


class I18nService:
    def __init__(self, root: Path, language: str = "zh_CN") -> None:
        self.root = root
        self.language = language
        self._cache: dict[str, dict[str, str]] = {}

    def set_language(self, language: str) -> None:
        self.language = language

    def load(self, language: str) -> dict[str, str]:
        if language not in self._cache:
            path = self.root / "app" / "i18n" / f"{language}.json"
            self._cache[language] = json.loads(path.read_text(encoding="utf-8"))
        return self._cache[language]

    def t(self, key: str) -> str:
        active = self.load(self.language)
        if key in active:
            return active[key]
        fallback = self.load("en_US")
        return fallback.get(key, key)
