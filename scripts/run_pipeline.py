from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config_binding.config_model import ConfigModel
from app.services.plot_service import PlotService
from app.services.report_service import ReportService
from app.services.run_service import RunService


def main() -> int:
    config = ConfigModel(ROOT).new_default()
    runner = RunService(ROOT)
    rows = runner.run_batch_comparison(config)
    PlotService(ROOT).generate_all()
    ReportService(ROOT).generate()
    print(f"completed {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
