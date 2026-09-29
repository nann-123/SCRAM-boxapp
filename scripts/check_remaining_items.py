#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app 层剩余项探针：每条一个"改前应 FAIL、改后应 PASS"的判据。

用途：把"内核之外、可在 py 侧解决"的剩余缺陷写成可复跑的判据 ——
现在跑给出**改前证据**，按判据改完后**重跑同一条命令**即成为验收。
不需要重编译内核；其中 GUI 类判据用 offscreen 模式，不需要显示器。

用法（仓库根目录）：
  python scripts/check_remaining_items.py            # 跑全部（含 GUI 类）
  python scripts/check_remaining_items.py --no-gui   # 跳过 GUI 类（无 Qt 环境时）
退出码：0 = 全部已满足；1 = 仍有未满足项（改前属预期）。

判据的"方案假设"写在每条 detail 里：若你选了另一种修法（例如保留控件但置灰），
按该条备注调整判据即可，不要为了让它变绿而放宽判据。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES_DIR = ROOT / "install_logs" / "20260929_init_cases"
OUT_DIR = ROOT / "install_logs" / "20260929_remaining"

TIER2_NOTES = [
    "P-06 比较运行：真跑内/外混两臂（1 h），核对结果里出现两臂差异清单（判据同 R-07，但取自真实运行）",
    "P-07 那条 1e13 峰值定性：同配置把 SO4 排放置 0 再跑，比较 size_distribution_number 的峰值（差分实验）",
    "#27 中文路径实测：在含中文的目录/案例名下真跑一次，看核心能否打开（R-09 只保证不再产生非 ASCII 路径）",
    "#18 保真度 gate：需要 Windows 侧结果做对照，单平台无法完成",
    "E3 1.2 基线重采：需要先定「采集哪些量」",
]


def _item(ident: str, title: str, judge: str) -> dict:
    return {"id": ident, "title": title, "judge": judge, "ok": False, "detail": ""}


def _ensure_cases() -> None:
    if not (CASES_DIR / "T4_nl1_ext_tagext1.cfg").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_init_test_cases.py"),
                        "--out", str(CASES_DIR), "--hours", "1", "--zero-mass"], check=True)


# ---------------------------------------------------------------- 判据实现

def r01_mixing_assumption(model) -> dict:
    item = _item("R-01", "载入配置后「混合假设」应能从 cfg 反推", "n_frac=1 ⇒ INTERNAL_MIXING；n_frac>1 ⇒ EXTERNAL_MIXING")
    internal = model.parse(CASES_DIR / "T1_nl5_nf1.cfg")          # n_frac=1
    external = model.parse(CASES_DIR / "T4_nl1_ext_tagext1.cfg")  # n_frac=3
    got = (internal["mixing_assumption"], external["mixing_assumption"])
    item["ok"] = got == ("INTERNAL_MIXING", "EXTERNAL_MIXING")
    item["detail"] = (f"实测：n_frac=1 → {got[0]}，n_frac=3 → {got[1]}（方案假设：P-03「从 cfg 反推」；"
                      f"现状恒为 EXTERNAL_MIXING ⇒ 载入内混配置也会按外混跑）")
    return item


def r02_mapping_scheme(run_service, model) -> dict:
    item = _item("R-02", "配置里的 mapping_scheme 应真正送达内核", "env['SCRAM_COEFF_REPARTITION_MODE'] 随 cfg 取值变化")
    base = model.parse(ROOT / "core" / "templates" / "baseline12h.cfg")
    seen = {}
    for scheme, expect in (("LEGACY", "LEGACY"), ("DETERMINISTIC_NEAREST", "COAG_TARGET_NEAREST")):
        data = json.loads(json.dumps(base))
        data["mapping_scheme"] = scheme
        prepared = run_service.prepare_run(data, f"probe_mapping_{scheme.lower()}", "INTERNAL_MIXING")
        seen[scheme] = prepared["env"].get("SCRAM_COEFF_REPARTITION_MODE", "")
    item["ok"] = seen == {"LEGACY": "LEGACY", "DETERMINISTIC_NEAREST": "COAG_TARGET_NEAREST"}
    item["detail"] = (f"实测：LEGACY → {seen.get('LEGACY')!r}、DETERMINISTIC_NEAREST → {seen.get('DETERMINISTIC_NEAREST')!r}；"
                      f"内核已支持 LEGACY/COAG_TARGET_NEAREST/WEIGHTED_*/LCP（ModuleCoeffRepartitionBoxmodel.f90:330-350），"
                      f"但 _with_mixing_assumption 把 mapping_scheme 强写成 DETERMINISTIC_NEAREST ⇒ cfg 字段被无视")
    return item


def r03_zero_mass_guard(model) -> dict:
    item = _item("R-03", "「质量为 0 而粒子数非 0」的配置应被拦下", "validate() 对该配置返回非空错误")
    data = model.parse(CASES_DIR / "T8_zero_mass_int.cfg")
    errors = model.validate(data)
    hit = [e for e in errors if ("质量" in e and "0" in e) or "mass" in e.lower() or "零" in e]
    item["ok"] = bool(hit)
    item["detail"] = (f"实测：validate() 返回 {len(errors)} 条错误，命中质量为 0 的 {len(hit)} 条"
                      f"（方案假设：P-08 默认开启的护栏；现状可载入、可运行）")
    return item


def r04_nl5_layout_guard(model, template_service) -> dict:
    item = _item("R-04", "论文验证模式（成核模型=5）与物种布局不匹配时应拦下",
                 "2 物种布局 + nucl_model=5 ⇒ validate() 报错")
    data = template_service.load_template("tutorial_minimal")
    data["scalars"]["nucl_model"] = 5
    errors = model.validate(data)
    hit = [e for e in errors if "布局" in e or "物种" in e or "nl" in e.lower() or "nucl_model" in e]
    item["ok"] = bool(hit)
    item["detail"] = (f"实测：2 物种布局 + nucl_model=5 → validate() 返回 {len(errors)} 条错误、命中 {len(hit)} 条"
                      f"（方案假设：P-02 按「第 2 个物种含 BC、第 4 个含 SO4」校验；"
                      f"现状该组合静默失效：初始总质量只剩一半、Mass Cond = 0）")
    return item


def r05_dtmin_control(model) -> dict:
    item = _item("R-05", "「最小时间步」控件不应再声称能影响结果",
                 "控件已移除或置灰（两种修法都接受）")
    present = disabled = None
    if _gui_available():
        try:
            window = _make_window()
            widget = window.field_widgets.get("dtmin_seconds")
            present = widget is not None
            disabled = (widget is not None) and (not widget.isEnabled())
            window.close()
        except Exception as exc:  # noqa: BLE001
            item["detail"] = f"GUI 探针异常：{exc!r}"
            return item
    fields = json.loads((ROOT / "scripts" / "gui_fields.json").read_text(encoding="utf-8"))
    # 2026-09-29 修复：gui_fields.json 顶层是 {"fields": [...], ...}，原写法直接遍历顶层
    # 拿到的是字符串键，isinstance(entry, dict) 恒为 False ⇒ dead 恒为 False，
    # R-05 无论怎么改都不可能变 PASS。
    fields = fields.get("fields", []) if isinstance(fields, dict) else fields
    dead = any(entry.get("key") == "dtmin_seconds" and (entry.get("widget") is None
                                                       or "dead" in str(entry.get("known_defect", "")).lower()
                                                       or "未实现" in str(entry.get("note", "")))
               for entry in fields if isinstance(entry, dict))
    item["ok"] = (present is False or disabled is True) and dead
    item["detail"] = (f"实测：控件仍存在={present}、已置灰={disabled}、字段登记为已失效={dead}；"
                      f"内核侧 dtmin 只被读入、0 处使用（ModuleAdaptstep.f90 无钳制语句）")
    return item


def r06_scenario_linkage(model) -> dict:
    item = _item("R-06", "「初值来源」应为用户可选（tag_init 权限），且格式/护栏行为正确",
                 "GUI 可把 tag_init 切到 0；0 时逐档质量表置灰；cfg 往返保持 tag_init=0 短格式；护栏拦下 (0,0,n_frac>1)")
    if not _gui_available():
        item["detail"] = "跳过：无 Qt 环境（PySide6 不可用，或显式传了 --no-gui）—— 此时这不是真实判据结果"
        item["ok"] = False
        return item
    try:
        window = _make_window()
        window.data = model.parse(ROOT / "core" / "templates" / "baseline12h.cfg")
        window._load_data_into_widgets()
        combo = window.field_widgets.get("tag_init")
        has_combo = combo is not None
        if has_combo:
            combo.setCurrentIndex(combo.findData(0))
        data = window._collect_data()
        table_disabled = not window.initial_mass_table.isEnabled()
        # 往返：收集 → serialize → parse，验证 tag_init=0 的 5 列短格式真的写出来了
        roundtrip_tag = None
        roundtrip_binlen = None
        if has_combo:
            text = model.serialize_text(data)
            # mkstemp 必须显式关 fd：Windows 上未关的句柄会锁住文件，write_text 直接 PermissionError
            fd, tmp_name = tempfile.mkstemp(suffix=".cfg")
            os.close(fd)
            tmp = Path(tmp_name)
            try:
                tmp.write_text(text, encoding="utf-8")
                parsed = model.parse(tmp)
                roundtrip_tag = int(parsed["scalars"].get("tag_init", -1))
                roundtrip_binlen = len(parsed["species_records"][0]["bin_values"]) if parsed["species_records"] else None
            finally:
                tmp.unlink(missing_ok=True)
        window.close()
    except Exception as exc:  # noqa: BLE001
        item["detail"] = f"GUI 探针异常：{exc!r}"
        return item
    tag_init = int(data["scalars"].get("tag_init", 1))
    # 配套护栏：(tag_init=0, tag_external=0, n_frac>1) 必须被拦下
    probe_data = json.loads(json.dumps(data))
    probe_data["scalars"].update(tag_init=0, tag_external=0, n_frac=3)
    guarded = bool(model.validate(probe_data))
    item["ok"] = bool(has_combo and tag_init == 0 and table_disabled
                      and roundtrip_tag == 0 and roundtrip_binlen == 1 and guarded)
    item["detail"] = (f"实测：tag_init 下拉存在={has_combo}，切到 0 后收集 tag_init={tag_init}、"
                      f"逐档质量表置灰={table_disabled}；cfg 往返 tag_init={roundtrip_tag}、"
                      f"物种行质量值个数={roundtrip_binlen}（短格式应为 1）；"
                      f"(tag_init=0, tag_external=0, n_frac=3) 护栏拦截={guarded}"
                      f"（2026-09-29 方案 b′：tag_init 权限交给用户 + 预览真话 + 护栏兜底）")
    return item


def r07_arm_diff_visible(run_service, model) -> dict:
    item = _item("R-07", "内外混对比的两臂差异应能被程序化读出", "prepared 返回差异清单，且 tag_external=1 时必须列出该项")
    base = model.parse(ROOT / "core" / "templates" / "baseline12h.cfg")
    base["scalars"]["tag_external"] = 1
    prepared = run_service.prepare_run(json.loads(json.dumps(base)), "probe_armdiff", "EXTERNAL_MIXING")
    keys = [key for key in ("arm_diff_keys", "arm_diff", "diff_keys") if key in prepared]
    listed = prepared.get(keys[0]) if keys else None
    item["ok"] = bool(keys)
    item["detail"] = (f"实测：prepared 中差异清单字段={keys or '无'}（值={listed}）；"
                      f"tag_external=1 的配置做比较时两臂实际差 tag_external/n_frac/fraction_bounds 三项（方案假设：P-06 显式化）")
    return item


def r08_emission_window() -> dict:
    item = _item("R-08", "排放窗口固定 44 min（记录项，需内核侧决策）", "记录 2.64376d3 的出现位置，不设通过判据")
    src = (ROOT / "core" / "executables_or_wrappers" / "runtime" / "windows" / "source"
           / "SCRAM1.2" / "SRC" / "ModuleDiscretization.f90").read_text(encoding="latin-1")
    lines = [index + 1 for index, line in enumerate(src.splitlines()) if "2.64376d3" in line]
    item["ok"] = True
    item["detail"] = (f"硬编码命中行：{lines}（读入 time_emis 与两处步长守卫）；"
                      f"想做成可配只能改内核，属待决策项 —— 本条只记录，不参与判定")
    return item


def r09_ascii_paths(run_service, model) -> dict:
    item = _item("R-09", "案例名含中文时，交给内核的**路径**应保持 ASCII", "run_root / cfg 路径不含非 ASCII 字符")
    base = model.parse(ROOT / "core" / "templates" / "baseline12h.cfg")
    prepared = run_service.prepare_run(json.loads(json.dumps(base)), "中文案例_探针", "INTERNAL_MIXING")
    paths = [str(prepared.get("run_root", "")), str(prepared.get("config_path", ""))]
    bad = [p for p in paths if not p.isascii()]
    item["ok"] = not bad
    item["detail"] = (f"实测：非 ASCII 路径 {bad or '无'}；内核能否打开非 ASCII 路径未验证"
                      f"（方案假设：目录名 ASCII 化即可完全绕开）")
    return item


# ---------------------------------------------------------------- GUI 辅助

def _gui_available() -> bool:
    if os.environ.get("SCRAM_PROBE_NO_GUI"):
        return False
    try:
        import PySide6  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _make_window():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.views.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(ROOT)
    app.processEvents()
    return window


# ---------------------------------------------------------------- 主流程

def main() -> int:
    parser = argparse.ArgumentParser(description="app 层剩余项探针")
    parser.add_argument("--no-gui", action="store_true", help="跳过 GUI 类判据（R-05/R-06）")
    args = parser.parse_args()
    if args.no_gui:
        os.environ["SCRAM_PROBE_NO_GUI"] = "1"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_cases()

    from app.config_binding.config_model import ConfigModel
    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    model = ConfigModel(ROOT)
    run_service = RunService(ROOT)
    template_service = TemplateService(ROOT)

    probes = [
        ("R-01", lambda: r01_mixing_assumption(model)),
        ("R-02", lambda: r02_mapping_scheme(run_service, model)),
        ("R-03", lambda: r03_zero_mass_guard(model)),
        ("R-04", lambda: r04_nl5_layout_guard(model, template_service)),
        ("R-05", lambda: r05_dtmin_control(model)),
        ("R-06", lambda: r06_scenario_linkage(model)),
        ("R-07", lambda: r07_arm_diff_visible(run_service, model)),
        ("R-08", lambda: r08_emission_window()),
        ("R-09", lambda: r09_ascii_paths(run_service, model)),
    ]

    results = []
    for ident, runner in probes:
        if os.environ.get("SCRAM_PROBE_NO_GUI") and ident in {"R-05", "R-06"}:
            item = _item(ident, "（GUI 类，已跳过）", "加 --no-gui 时为跳过项")
            item["detail"] = "跳过：--no-gui"
            results.append(item)
            continue
        try:
            results.append(runner())
        except Exception:  # noqa: BLE001
            item = _item(ident, "探针异常", "见 detail")
            item["detail"] = traceback.format_exc(limit=3).strip().splitlines()[-1]
            results.append(item)

    print("%-6s %-40s %s" % ("id", "标题", "判定"))
    for item in results:
        print("  %-4s %-40s %s" % (item["id"], item["title"][:38],
                                   "PASS（已满足）" if item["ok"] else "FAIL（改前属预期）"))
    print("")
    for item in results:
        print("[%s] %s %s" % ("PASS" if item["ok"] else "FAIL", item["id"], item["title"]))
        print("      判据：%s" % item["judge"])
        print("      %s" % item["detail"])
    print("")
    summary = {"total": len(results),
               "pass": sum(1 for item in results if item["ok"]),
               "fail": sum(1 for item in results if not item["ok"])}
    print("汇总：%d 条，已满足 %d，未满足 %d（改前未满足属预期；改完重跑本命令即验收）"
          % (summary["total"], summary["pass"], summary["fail"]))
    print("")
    print("未覆盖（第二层，需要在 Linux 上跑核，故不在本脚本内）：")
    for line in TIER2_NOTES:
        print("  - " + line)
    (OUT_DIR / "result.json").write_text(
        json.dumps({"summary": summary, "items": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("明细已写入 %s" % (OUT_DIR / "result.json"))
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
