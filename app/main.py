from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


ROOT = _application_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(ROOT)
    window.resize(1480, 980)
    window.show()
    if os.environ.get("SCRAM_GUI_SMOKE_TEST") == "1":
        QTimer.singleShot(800, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
