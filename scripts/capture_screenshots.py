from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.views.main_window import MainWindow


def save_shot(window: MainWindow, path: Path) -> None:
    window.show()
    QApplication.processEvents()
    window.grab().save(str(path))


def point_to_result_root(window: MainWindow, result_root: Path) -> None:
    if result_root.exists():
        window.current_results_root = result_root
        window.output_dir_edit.setText(str(result_root))
        window.report_results_dir.setText(str(result_root))
        window.plot_service.set_results_root(result_root)
        window.report_service.set_results_root(result_root)


def main() -> int:
    app = QApplication([])
    app.setFont(QFont("Microsoft YaHei UI", 9))
    window = MainWindow(ROOT)
    result_root = ROOT / "install_logs" / "audit_standard_tests_report2"
    point_to_result_root(window, result_root)
    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    window.resize(1600, 1020)

    save_shot(window, out / "main_zh.png")
    window.change_language("en_US")
    save_shot(window, out / "main_en.png")
    window.change_language("zh_CN")
    window.data = window.template_service.load_template("gmd_paris_full")
    window.data["experiment_name"] = "gmd_paris_full"
    point_to_result_root(window, result_root)
    window.refresh_all()
    point_to_result_root(window, result_root)

    window.tabs.setCurrentIndex(0)
    save_shot(window, out / "config_setup_panel.png")

    window.tabs.setCurrentIndex(1)
    save_shot(window, out / "structure_editor.png")

    window.tabs.setCurrentIndex(2)
    window.monitor_labels["status"].setText("运行中")
    window.monitor_labels["current_case"].setText("gmd_paris_full")
    window.monitor_labels["current_scheme"].setText("EXTERNAL_MIXING")
    window.monitor_labels["elapsed_wallclock"].setText("1.8 s")
    window.monitor_labels["simulated_hours"].setText("0.12 h")
    window.monitor_labels["eta"].setText("0.9 s")
    window.monitor_labels["current_total_mass"].setText("1.48e-03")
    window.monitor_labels["current_total_number"].setText("4.12e+09")
    window.log_view.append("gmd_paris_full / EXTERNAL_MIXING")
    save_shot(window, out / "running_state.png")

    window.refresh_results_assets()
    if window.figure_list.count():
        window.figure_list.setCurrentRow(0)
    window.tabs.setCurrentIndex(3)
    save_shot(window, out / "results_view.png")

    if window.report_service.available():
        window.refresh_report_assets()
        window.report_log.append("internal_external_mixing_report.pdf")
        report_index = 4
        window.tabs.setCurrentIndex(report_index)
        save_shot(window, out / "report_panel.png")
        settings_index = 5
        help_index = 6
    else:
        settings_index = 4
        help_index = 5
    window.tabs.setCurrentIndex(settings_index)
    save_shot(window, out / "settings_panel.png")
    window.tabs.setCurrentIndex(help_index)
    save_shot(window, out / "help_panel.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
