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
    # 2026-09-30：案例预设已删除 ⇒ 原先按预设名跑四组（run_batch_comparison）不再有意义，
    # 改为对当前配置跑一次内外混对比（过程开关与时长由配置/界面直接给出，不再被预设改写）。
    rows = runner.run_comparison(config, "pipeline")
    PlotService(ROOT).generate_all()
    ReportService(ROOT).generate()
    print(f"completed {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
