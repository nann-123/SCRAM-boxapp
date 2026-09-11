"""资产完整性检查（探测类 P9）—— 让这类"文档资产坏掉/过期"的问题能被自动发现。

检查四项：
  A 过期：docs/screenshots 与 docs/*_assets 的最后改动是否早于 app/（GUI 代码）；
          devkit §7 要求"改了 GUI 就重生成截图"，早于即过期。
  B 字体自检：当前环境能否渲染中文（方框检测）。用 Qt 渲染已知字符串，宽度等于
          缺字宽度即判为 tofu；并报告 app 所用的 Windows 字体是否可用。
  C 引用完整：文档里引用的资产路径是否都存在（缺失即硬失败）。
  D 影像体检：按 bytes/pixel 粗查"近空图/缺字图"（方框图压缩后异常小）。

用法：
    python scripts/linux/check_assets.py            # 只做静态检查（秒级）
    python scripts/linux/check_assets.py --render    # 额外无头渲染一份到 install_logs/ 供比对（约 40 秒）

退出码：0 = 无发现；1 = 有**新增**告警；3 = 仅有**已知项**；2 = 引用缺失或渲染失败。

已知项 = 已在 docs/BUG_TRACKING.md 登记、但修复依赖外部条件（Windows）的问题，例如 Bug #10
（发布截图需在 Windows 重生成）。这类告警照常打印，但单独计数：结论栏只反映"有没有新问题"，
不会因为同一个老问题每轮都报警而失去信号。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SS = ROOT / "docs" / "screenshots"
ASSET_DIRS = [SS, ROOT / "docs" / "user_manual_zh_assets", ROOT / "docs" / "undergrad_lab_assets"]
WINDOWS_FONT = "Microsoft YaHei UI"

# (known_tag, text)：known_tag 非空 = 已登记的已知问题（如 "bug#10"），单独计数
warnings: list[tuple[str, str]] = []
errors: list[str] = []


def warn(text: str, known: str = "") -> None:
    warnings.append((known, text))


def git_time(spec: str) -> int:
    out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%ct", "--", spec],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else 0


def check_staleness() -> None:
    app_t, shot_t = git_time("app/"), git_time("docs/screenshots/")
    if not app_t or not shot_t:
        warn("无法读取 app/ 或 docs/screenshots/ 的最后改动时间（浅克隆？）")
        return
    if app_t > shot_t:
        warn(f"截图已过期：app/ 最后改动 {app_t} 晚于 docs/screenshots/ 的 {shot_t}"
             "（devkit §7：改了 GUI 布局/按钮/文字/结果页就必须重生成截图）", "bug#10")


def check_fonts() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QGuiApplication
    except ImportError:
        warn("PySide6 不可用，跳过字体自检")
        return
    # QFontDatabase 需要先有 QGuiApplication 实例（无显示器时用 offscreen 平台）
    app = QGuiApplication.instance() or QGuiApplication([])
    families = set(QFontDatabase.families())
    if WINDOWS_FONT not in families:
        warn(f"app 指定的字体 {WINDOWS_FONT!r} 在本环境不可用；"
             "生成的截图会与 Windows 发布资产不同字形（属预期，但发布截图必须在 Windows 上生成）",
             "bug#10")

    def is_tofu(family: str | None) -> bool:
        font = QFont(family) if family else QFont()
        metrics = QFontMetrics(font)
        cjk = metrics.horizontalAdvance("测试")
        # 缺字时 Qt 回退到同一替代字形，宽度等于单字形宽度的倍数
        return cjk <= 0 or cjk <= metrics.horizontalAdvance("x") * 1.2

    if is_tofu(WINDOWS_FONT if WINDOWS_FONT in families else None):
        if not any(not is_tofu(f) for f in sorted(families)[:200]):
            errors.append("本环境没有任何能渲染中文的字体：生成的截图文字会全为方框（Bug #10 的成因）")
        else:
            warn("默认字体渲染中文为方框；存在可用中文字体，生成脚本需要设置回退链", "bug#10")


def check_references() -> None:
    pattern = re.compile(r"\]\(([^)]+\.png)\)|src=[\"']([^\"']+\.png)[\"']")
    missing = []
    for doc in list((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]:
        for match in pattern.finditer(doc.read_text(errors="replace")):
            rel = match.group(1) or match.group(2)
            if rel.startswith(("http", "/")):
                continue
            target = (doc.parent / rel).resolve()
            if not target.exists():
                missing.append(f"{doc.relative_to(ROOT)} → {rel}")
    if missing:
        errors.append("引用的资产不存在：" + "; ".join(missing))


def check_images() -> None:
    # 覆盖三个资产目录：GUI 截图与两份手册的图（手册图里既有 GUI 截图也有结果图，
    # 结果图正常密度约 0.03–0.07 B/px，方框截图约 0.006–0.012 B/px，阈值 0.015 可区分）
    for directory in ASSET_DIRS:
        for path in sorted(directory.rglob("*.png")):
            data = path.read_bytes()
            # PNG 头里读宽高（IHDR 从第 16 字节起 8 字节）
            try:
                width = int.from_bytes(data[16:20], "big")
                height = int.from_bytes(data[20:24], "big")
            except Exception:
                warn(f"{path.name}: 无法解析尺寸")
                continue
            if not width or not height:
                continue
            ratio = len(data) / (width * height)
            if ratio < 0.015:
                where = str(path.relative_to(ROOT))
                warn(f"{where}: 信息密度异常低（{ratio:.4f} B/px）→ 疑似文字渲染为方框或图为空白"
                     "（健康的 GUI 截图约 0.02–0.18 B/px，结果图约 0.03–0.07 B/px）", "bug#10")


def compare_with_render() -> None:
    """把刚渲染的检查用截图与仓库内同名资产对比（体积比），给出直接的坏图证据。"""
    out = ROOT / "install_logs" / "asset_check"
    if not out.exists():
        return
    for fresh in sorted(out.glob("*.png")):
        committed = SS / fresh.name
        if not committed.exists():
            continue
        def density(p: Path) -> float:
            b = p.read_bytes()
            w = int.from_bytes(b[16:20], "big")
            h = int.from_bytes(b[20:24], "big")
            return len(b) / max(w * h, 1)
        fresh_d, old_d = density(fresh), density(committed)
        if fresh_d > old_d * 2.5:
            warn(f"{fresh.name}: 仓库内资产密度 {old_d:.4f} 仅为新渲染 {fresh_d:.4f} 的 "
                 f"{old_d / fresh_d * 100:.0f}% → 仓库内这张图疑似缺字/空白（Bug #10 的直接证据）",
                 "bug#10")


def render_probe() -> None:
    out = ROOT / "install_logs" / "asset_check"
    out.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "capture_screenshots.py"),
                             "--out", str(out)], capture_output=True, text=True)
    if result.returncode != 0:
        errors.append("无头渲染失败：" + (result.stderr or result.stdout)[-300:])
        return
    print(f"   已渲染到 {out.relative_to(ROOT)}（与 docs/screenshots/ 对照目视或用本检查的密度指标比对）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true", help="额外无头渲染一份供比对")
    args = parser.parse_args()

    print("== P9 资产完整性检查 ==")
    check_staleness()
    check_fonts()
    check_references()
    check_images()
    if args.render:
        render_probe()
        compare_with_render()

    known = sorted({tag for tag, _ in warnings if tag})
    new_items = [text for tag, text in warnings if not tag]
    known_items = [text for tag, text in warnings if tag]
    for item in errors:
        print(f"  ERROR  {item}")
    for item in new_items:
        print(f"  WARN(新增)  {item}")
    for item in known_items:
        print(f"  WARN(已知 {known and '、'.join(known) or '?'})  {item}")
    if not errors and not warnings:
        print("  ok     文档资产完整：无过期、字体可渲染、引用齐全、影像密度正常")
    print(f"  == 汇总：硬失败 {len(errors)} / 新增告警 {len(new_items)} / "
          f"已知告警 {len(known_items)}（{'、'.join(known) if known else '无'}）==")
    print("  提示：发布用截图必须在 Windows 上生成（字体）；本检查用于在 Linux 上提前发现这类问题")
    if errors:
        return 2
    if new_items:
        return 1
    return 3 if known_items else 0


if __name__ == "__main__":
    sys.exit(main())
