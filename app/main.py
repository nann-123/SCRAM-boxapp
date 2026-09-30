from __future__ import annotations

import json
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


def _run_smoke_checks(window) -> None:
    """冒烟自检（发布测试用）：把出厂模板逐个载入 + 校验，结果写成 JSON 报告。

    2026-09-30：原先的冒烟只"开窗 800 ms 就退"，打包版缺资产（漏 examples 基座、
    config_schema 被 --add-data 建成了目录）它一律发现不了 —— 现在真的把每个模板
    载入并校验一遍，失败就记进报告（SCRAM_GUI_SMOKE_REPORT 指定的文件）。
    """
    report: dict = {"root": str(ROOT), "templates": {}, "ok": True}
    try:
        templates = window.template_service.list_templates()
    except Exception as exc:  # 模板服务本身起不来
        report["ok"] = False
        report["error"] = f"list_templates failed: {exc}"
        templates = []
    for template in templates:
        template_id = str(template.get("id", "?"))
        try:
            data = window.template_service.load_template(template_id)
            errors = window.config_model.validate(data)
            report["templates"][template_id] = {
                "loaded": True,
                "validation_errors": errors,
            }
            if errors:
                report["ok"] = False
        except Exception as exc:
            report["ok"] = False
            report["templates"][template_id] = {"loaded": False, "error": f"{type(exc).__name__}: {exc}"}
    if os.environ.get("SCRAM_GUI_SMOKE_RUN") == "1":
        # 发布测试：真的跑一次最快的对比算例（含"从随包运行时暂存内核"这条路），
        # 结果写进报告。跑在临时结果根里，不碰用户的结果目录。
        import tempfile

        try:
            smoke_root = Path(tempfile.mkdtemp(prefix="scram_smoke_"))
            window.run_service.set_results_root(smoke_root)
            config = window.template_service.load_template("gmd_paris_emission_only")
            rows = window.run_service.run_comparison(config, "smoke_case")
            case_root = Path(rows[0]["case_root"])
            window.plot_service.set_results_root(case_root)
            window.plot_service.generate_all(case_root)
            report["run"] = {
                "case_root": str(case_root),
                "figures": len(list((case_root / "figures").glob("*.png"))),
                "arms": [
                    {"scheme": row["scheme"], "status": row["status"], "final_mass": row.get("final_mass")}
                    for row in rows
                ],
            }
            if any(row["status"] != "ok" for row in rows):
                report["ok"] = False
        except Exception as exc:
            report["ok"] = False
            report["run"] = {"error": f"{type(exc).__name__}: {exc}"}

    target = os.environ.get("SCRAM_GUI_SMOKE_REPORT")
    if target:
        Path(target).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["ok"]:
        print("GUI smoke check FAILED: " + json.dumps(report, ensure_ascii=False))


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(ROOT)
    window.resize(1480, 980)
    window.show()
    if os.environ.get("SCRAM_GUI_SMOKE_TEST") == "1":
        _run_smoke_checks(window)
        QTimer.singleShot(800, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
