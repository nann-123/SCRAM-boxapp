from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _clean_dir(path: Path) -> None:
    resolved = path.resolve()
    allowed_root = (ROOT / "install_logs").resolve()
    if allowed_root != resolved and allowed_root not in resolved.parents:
        raise ValueError(f"refusing to clean output outside install_logs: {resolved}")
    if path.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_import_smoke() -> None:
    import matplotlib  # noqa: F401
    import PySide6  # noqa: F401

    from app.config_binding.config_model import ConfigModel
    from app.services.run_service import RunService

    config = ConfigModel(ROOT).new_default()
    errors = ConfigModel(ROOT).validate(config)
    _assert(not errors, "default config validation failed: " + "; ".join(errors))
    _assert(RunService(ROOT).executable_available(), "ProgramSCRAM executable is not available")
    print("import_smoke: ok")


def run_gui_smoke() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.config_binding.config_model import ConfigModel
    from app.views.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(ROOT)
    window.resize(900, 600)
    window.show()
    app.processEvents()
    baseline = ConfigModel(ROOT).parse(ROOT / "core" / "templates" / "baseline12h.cfg")
    window.data = baseline
    window.data["template_name"] = "gmd_paris_full"
    window.refresh_all()
    app.processEvents()
    _assert(abs(float(window._table_text(window.species_meta_table, 3, 3)) - 0.000795035914052) < 1.0e-14, "baseline species init_gas was not loaded into the GUI table")
    _assert(float(window._table_text(window.initial_mass_table, 3, 3)) > 0.0, "baseline initial mass matrix was not loaded into the GUI table")
    _assert(abs(float(window.field_widgets["pressure"].singleStep()) - 1000.0) < 1.0e-9, "pressure spinner step should be 1000 Pa")
    window.close()
    app.processEvents()
    print("gui_smoke: ok")


def run_runtime_smoke(output_root: Path, template_name: str, case_name: str, skip_report: bool) -> None:
    from app.config_binding.config_model import ConfigModel
    from app.services.plot_service import PlotService
    from app.services.report_service import ReportService
    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    _clean_dir(output_root)
    config = TemplateService(ROOT).load_template(template_name)
    errors = ConfigModel(ROOT).validate(config)
    _assert(not errors, "template validation failed: " + "; ".join(errors))
    runner = RunService(ROOT)
    runner.set_results_root(output_root)
    rows = runner.run_comparison(config, case_name)
    _assert(len(rows) == 2, f"expected two comparison rows, got {len(rows)}")
    for row in rows:
        _assert(row["status"] == "ok", f"{row['case_name']} / {row['scheme']} failed")
        _assert(int(row["total_steps"]) > 0, f"{row['scheme']} produced no timestep rows")
        _assert(math.isfinite(float(row["final_mass"])), f"{row['scheme']} final_mass is not finite")
        _assert(math.isfinite(float(row["final_number"])), f"{row['scheme']} final_number is not finite")

    perf = output_root / "performance_summary.csv"
    final = output_root / "final_state_summary.csv"
    _assert(perf.exists(), "performance_summary.csv was not written")
    _assert(final.exists(), "final_state_summary.csv was not written")

    PlotService(ROOT).generate_all(output_root)
    expected_figures = [
        "runtime_comparison.png",
        "final_mass_comparison.png",
        "final_number_comparison.png",
        f"{case_name}_total_mass.png",
        f"{case_name}_total_number.png",
        f"{case_name}_relative_mass_vs_external.png",
        f"{case_name}_relative_number_vs_external.png",
        f"{case_name}_external_mixed_fraction.png",
        f"{case_name}_external_mixing_mass_by_size.png",
        "internal_vs_external_mixing_logic.png",
    ]
    for name in expected_figures:
        _assert((output_root / "figures" / name).exists(), f"missing figure: {name}")
    if not skip_report:
        report = ReportService(ROOT)
        report.set_results_root(output_root)
        if report.available():
            _tex_path, pdf_path = report.generate()
            _assert(pdf_path.exists(), f"missing report PDF: {pdf_path}")
            _tex_path, builtin_pdf_path = report.generate(prefer_latex=False)
            _assert(builtin_pdf_path.exists(), f"missing built-in report PDF: {builtin_pdf_path}")
            print("report_smoke: ok")
        else:
            print("report_smoke: skipped (no xelatex or tectonic)")
    print(f"runtime_smoke: ok ({template_name} / {case_name})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SCRAM BoxApp standard smoke tests.")
    parser.add_argument("--template", default="gmd_paris_coagulation", help="TemplateService template id to load")
    parser.add_argument("--case", default="coag_only", help="CASE_PRESETS key to run")
    parser.add_argument("--output-root", type=Path, default=ROOT / "install_logs" / "standard_tests")
    parser.add_argument("--skip-gui", action="store_true", help="Skip offscreen GUI construction")
    parser.add_argument("--skip-report", action="store_true", help="Skip report generation even if TeX is available")
    args = parser.parse_args()

    run_import_smoke()
    if not args.skip_gui:
        run_gui_smoke()
    run_runtime_smoke(args.output_root.resolve(), args.template, args.case, args.skip_report)
    print("standard_tests: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
