#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""UI 运行编排回归（09-30 绘图竞态的回归闸门）。

背景：run_standard_tests 直接调 RunService/PlotService，不经过 UI 的运行编排层；
而 09-30 用户实测的 bug 恰恰在这层——运行（后台线程）期间任何控件刷新都会把
绘图根改回全局结果根，运行完成后图画到全局根 figures/（全是旧案例重画）、
本次运行目录反而没有图。

本脚本离屏驱动真实的 _start_runs → RunWorker → _on_run_completed 链路：
  1) 单跑一次 tutorial_minimal；
  2) 断言图落在本次运行目录的 figures/ 下；
  3) 断言 latest_run_root 指向本次运行目录（结果分析页据此浏览）。

运行期间刻意触发一次预览刷新（模拟用户动控件），覆盖"运行中改根"的场景。
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import app.views.main_window as mwm
from app.config_binding.config_model import ConfigModel
from app.views.main_window import MainWindow


class FakeQM:
    """离屏环境下自动应答弹窗，并记录弹窗内容用于诊断。"""

    Yes = 1
    No = 0
    calls: list[str] = []

    @classmethod
    def question(cls, *args, **kwargs):
        cls.calls.append(str(args[2] if len(args) > 2 else kwargs))
        return cls.No

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.calls.append("critical: " + str(args[2] if len(args) > 2 else kwargs))
        return cls.Ok

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.calls.append("warning: " + str(args[2] if len(args) > 2 else kwargs))
        return cls.Ok


def main() -> int:
    mwm.QMessageBox = FakeQM
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ROOT)
    baseline = ConfigModel(ROOT).parse(ROOT / "core" / "templates" / "baseline12h.cfg")
    window.data = baseline
    window.data["template_name"] = "gmd_paris_full"
    window.refresh_all()
    app.processEvents()

    out_root = ROOT / "install_logs" / "ui_flow_check"
    window.current_results_root = out_root
    window.output_dir_edit.setText(str(out_root))
    # 2026-09-30：案例预设删除 ⇒ 过程开关与时长直接由控件给出（短跑：只凝并 0.25 h）
    window.with_coag_box.setChecked(True)
    window.with_cond_box.setChecked(False)
    window.with_nucl_box.setChecked(False)
    window.field_widgets["final_time_hours"].setValue(0.25)
    window.experiment_name_edit.setText("ui_flow")
    app.processEvents()

    window._start_runs(compare=False)
    # 运行刚启动就触发一次预览刷新，模拟"运行期间用户动了控件"（竞态场景）
    window._sync_visibility()

    loop = QEventLoop()
    QTimer.singleShot(180_000, loop.quit)
    window.run_worker.completed.connect(lambda _rows: loop.quit())
    window.run_worker.failed.connect(lambda _message: loop.quit())
    loop.exec()
    app.processEvents()

    problems: list[str] = []
    if FakeQM.calls:
        problems.append(f"运行编排弹出对话框（不应发生）: {FakeQM.calls}")
    latest = getattr(window, "latest_run_root", None)
    if latest is None:
        problems.append("latest_run_root 未设置（运行未完成？）")
    else:
        figures = sorted((latest / "figures").glob("*.png"))
        print(f"latest_run_root: {latest}")
        print(f"本次运行图数: {len(figures)}")
        if not figures:
            problems.append("本次运行目录没有图（绘图竞态回归？）")
        if window.plot_service.results_root != latest:
            problems.append("plot_service 结果根未指向本次运行目录")
        # 2026-09-30 新布局：latest 就是案例目录，臂目录是它的子目录（不再有 runs/<案例>/）。
        # 这里不写死名字，按臂目录逐个查。
        from app.services import results_layout

        collected = [arm / "csv" / "mass_init.txt"
                     for arm in results_layout.iter_arms(latest)
                     if (arm / "csv" / "mass_init.txt").exists()]
        if not collected:
            problems.append("mass_init.txt 未被采集到运行 csv 目录（tag_init=0 参考显示的数据源）")
        if window.csv_list.count() == 0:
            problems.append("结果分析页 CSV 列表为空（junction 遍历回归？）")
    if problems:
        for problem in problems:
            print("!!", problem)
        print("ui_run_flow_check: FAIL")
        return 1
    print("ui_run_flow_check: ok —— 图落在本次运行目录，未泄漏到全局根")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
