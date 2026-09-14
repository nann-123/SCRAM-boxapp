from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Bug #10 修复：offscreen 平台插件的字体库是空的，截图里所有字形都会退化成
# "□"。Windows 上必须用真实平台插件（windows）才能枚举系统字体；Linux 无显示
# 会话时仍用 offscreen。
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform.startswith("win") else "offscreen")

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
import platform

from app.views.main_window import MainWindow

# T1: platform-aware CJK font fallback chain.
# Windows: Microsoft YaHei UI -> SimSun ; Linux: Noto Sans CJK SC -> Droid Sans Fallback.
_FONT_CHAIN = {
    "Windows": ["Microsoft YaHei UI", "Microsoft YaHei", "SimSun", "SimHei"],
    "Linux": ["Noto Sans CJK SC", "Noto Sans CJK TC", "Droid Sans Fallback",
              "AR PL UMing CN", "WenQuanYi Micro Hei"],
    "Darwin": ["PingFang SC", "Hiragino Sans GB", "STHeiti"],
}


_FONT_FILES = {
    "Windows": ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc",
                "C:/Windows/Fonts/Deng.ttf"],
    "Linux": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"],
}


def pick_cjk_font(app: QApplication) -> str:
    """Return the first available family in the platform CJK chain.

    Bug #10：字体库为空（例如 Windows 上的 offscreen 插件）时，先尝试显式注册
    字体文件；若仍拿不到任何 CJK 字体则直接失败，避免静默产出满屏方框的截图。
    """
    chain = _FONT_CHAIN.get(platform.system(), _FONT_CHAIN["Linux"])
    fams = set(QFontDatabase.families())
    for name in chain:
        if name in fams:
            return name
    # 家族名拿不到时，尝试按文件注册
    for path in _FONT_FILES.get(platform.system(), []):
        if Path(path).exists():
            font_id = QFontDatabase.addApplicationFont(path)
            if font_id >= 0:
                added = QFontDatabase.applicationFontFamilies(font_id)
                for name in added:
                    if name in chain:
                        return name
                if added:
                    return added[0]
    raise SystemExit(
        f"没有可用的 CJK 字体（平台 {platform.system()}，字体库 {len(fams)} 个家族）。\n"
        f"缺字体会让截图中所有文字渲染成方框。请安装以下任一字体后重试：{chain}"
    )


def _image_density(path: Path) -> float:
    """Bytes-per-pixel of a saved PNG (proxy for text-rendering density)."""
    try:
        from PIL import Image
        im = Image.open(path)
        w, h = im.size
        if w * h == 0:
            return 0.0
        return path.stat().st_size / float(w * h)
    except Exception:
        return -1.0


def self_check_shot(path: Path, label: str = "") -> None:
    """Post-generation tofu/blank self-check: warn if density is abnormally low."""
    d = _image_density(path)
    if d < 0:
        print(f"[font-selfcheck] {label or path.name}: 无法读取图像密度（PIL 缺失？）")
        return
    if d < 0.02:
        print(f"[font-selfcheck] WARN {label or path.name}: 密度 {d:.4f} B/px 过低，"
              f"疑似文字渲染为方框或空白（健康 GUI 截图约 0.02-0.18 B/px）")
    else:
        print(f"[font-selfcheck] ok {label or path.name}: 密度 {d:.4f} B/px")



def save_shot(window: MainWindow, path: Path) -> None:
    window.show()
    QApplication.processEvents()
    window.grab().save(str(path))
    self_check_shot(path, label=path.name)


def point_to_result_root(window: MainWindow, result_root: Path) -> None:
    if result_root.exists():
        window.current_results_root = result_root
        window.output_dir_edit.setText(str(result_root))
        window.report_results_dir.setText(str(result_root))
        window.plot_service.set_results_root(result_root)
        window.report_service.set_results_root(result_root)


def main() -> int:
    out = ROOT / "docs" / "screenshots"
    argv = sys.argv[1:]
    if "--out" in argv:
        index = argv.index("--out")
        if index + 1 >= len(argv):
            print("usage: capture_screenshots.py [--out <dir>]", file=sys.stderr)
            return 2
        out = Path(argv[index + 1]).expanduser().resolve()

    app = QApplication([])
    # Windows UI font: other platforms fall back to their own fonts, so the
    # committed release screenshots must be regenerated on Windows. Use --out
    # to write review copies elsewhere (e.g. install_logs/) on Linux.
    _font = pick_cjk_font(app)
    print(f"[font] 使用 CJK 字体: {_font}（平台 {platform.system()}）")
    app.setFont(QFont(_font, 9))
    window = MainWindow(ROOT)
    result_root = ROOT / "install_logs" / "audit_standard_tests_report2"
    point_to_result_root(window, result_root)
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
