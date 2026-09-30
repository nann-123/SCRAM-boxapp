#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模板原生 / 全组合矩阵运行。

模式（2026-09-30 用户定优先级）：
  native（默认）——每个模板**原样**跑（过程开关与时长就是模板自带的值）：
                  每模板一个案例目录 <结果根>/<模板 id>/，两臂一起跑、出全套图，
                  并把"图 vs CSV"数据核查作为通过判据。
  cross——模板 × 开关/时长组合的交叉矩阵，用于探索不同过程组合下的行为。
          组合表是本脚本自己的 CROSS_CASES（2026-09-30 应用侧删除案例预设后搬到这里），
          直接写 config["scalars"] 的 with_coag/with_cond/with_nucl/final_time_hours ——
          不再经过已删除的 preset 机制。
  placements——gmd_paris_full 的"放置 × 解析"四联（单臂运行，各占一个案例目录）：
          初始放置（tag_external 0/1）× 解析（n_frac 1/3）。其中"外混放置+内混解析"
          会被内混臂按设计强制回 tag_external=0，与第一组同值——这正是要展示的事实。

用法：
  python scripts/run_all_matrix.py                    # native，写应用默认结果根
  python scripts/run_all_matrix.py --mode cross       # 交叉矩阵
  python scripts/run_all_matrix.py --mode placements  # 放置×解析四联（单臂，进 single/）
  python scripts/run_all_matrix.py --results-root X   # 指定结果根
输出：<结果根>/template_paths.txt（native）、matrix_paths.txt（cross）或 placement_paths.txt（placements）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_plot_data  # noqa: E402 —— 与标准测试同一道"图 vs CSV"数据核查
from app.services import results_layout  # noqa: E402
from app.services.deployment_paths import user_results_root
from app.services.plot_service import PlotService
from app.services.run_service import RunService
from app.services.template_service import TemplateService

# cross 矩阵的组合表：名称 → 过程开关与时长。原为应用侧 CASE_PRESETS（案例预设），
# 2026-09-30 该功能从界面与数据模型删除后，矩阵工具继续需要这些组合，故搬到这里自持。
CROSS_CASES: dict[str, dict[str, float | int]] = {
    "tutorial_minimal": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "final_time_hours": 0.25},
    "coag_only": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "final_time_hours": 0.5},
    "coag_cond": {"with_coag": 1, "with_cond": 1, "with_nucl": 0, "final_time_hours": 0.5},
    "coag_cond_nucl": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "final_time_hours": 0.5},
    "teaching_aging": {"with_coag": 1, "with_cond": 1, "with_nucl": 0, "final_time_hours": 12.0},
    "baseline12h": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "final_time_hours": 12.0},
    "gmd_hazy_condensation": {"with_coag": 0, "with_cond": 1, "with_nucl": 0, "final_time_hours": 12.0},
    "gmd_hazy_coag_cond": {"with_coag": 1, "with_cond": 1, "with_nucl": 0, "final_time_hours": 12.0},
    "gmd_paris_emission_only": {"with_coag": 0, "with_cond": 0, "with_nucl": 0, "final_time_hours": 12.0},
    "gmd_paris_coagulation": {"with_coag": 1, "with_cond": 0, "with_nucl": 0, "final_time_hours": 12.0},
    "gmd_paris_condensation": {"with_coag": 0, "with_cond": 1, "with_nucl": 0, "final_time_hours": 12.0},
    "gmd_paris_full": {"with_coag": 1, "with_cond": 1, "with_nucl": 1, "final_time_hours": 12.0},
}

# 放置 × 解析四联（单臂）：(目录名, tag_external, 解析方法, 说明)
PLACEMENT_VARIANTS = (
    ("gmd_paris_full_placeInt_resInt", 0, "INTERNAL_MIXING", "初始内混放置 + 内混解析"),
    ("gmd_paris_full_placeInt_resExt", 0, "EXTERNAL_MIXING", "初始内混放置 + 外混解析"),
    ("gmd_paris_full_placeExt_resExt", 1, "EXTERNAL_MIXING", "初始外混放置 + 外混解析"),
    ("gmd_paris_full_placeExt_resInt", 1, "INTERNAL_MIXING",
     "初始外混放置 + 内混解析（内混臂按设计强制回 tag_external=0，预期与第一组同值）"),
)


def _execute(run_service, plot_service, config, case_name, results_root, scheme=None):
    """跑一次运行（scheme=None → 两臂比较；否则单臂）+ 出图 + 数据核查。

    `results_root` 是**结果根**（案例目录 = <结果根>/<案例名>，与 App 的语义一致；
    2026-09-30 修：此前传的是案例目录本身，会多套一层同名目录）。
    返回 (case_root, figures|None, detail, elapsed)。
    """
    case_root = results_layout.case_root(results_root, run_service.ascii_name(case_name))
    if case_root.exists():
        shutil.rmtree(case_root)
    case_root.mkdir(parents=True, exist_ok=True)
    run_service.set_results_root(results_root)
    started = time.perf_counter()
    try:
        if scheme is None:
            rows = run_service.run_comparison(config, case_name)
        else:
            rows = [run_service.run_single(config, case_name, scheme)]
    except Exception as exc:  # 护栏拦截等：记录原因不算崩溃
        return case_root, None, f"异常: {str(exc).splitlines()[0][:120]}", time.perf_counter() - started
    elapsed = time.perf_counter() - started
    bad = [r for r in rows if r.get("status") != "ok"]
    if bad or len(rows) < 1:
        return case_root, None, f"arms={len(rows)} statuses={[r.get('status') for r in rows]}", elapsed
    plot_service.set_results_root(case_root)
    plot_service.generate_all(case_root)
    figures = len(list(results_layout.figures_dir(case_root).glob("*.png")))
    problems = check_plot_data.verify_plot_data(plot_service)
    if problems:
        return case_root, figures, "数据核查: " + " | ".join(problems[:3]), elapsed
    return case_root, figures, "", elapsed


def _run_placements(results_root, run_service, plot_service) -> int:
    """gmd_paris_full 的"放置 × 解析"四联（单臂运行，按应用约定进 single/）。"""
    started = time.perf_counter()
    ok_list: list[tuple[str, Path, int, float, str]] = []
    failed: list[tuple[str, str]] = []
    for index, (name, tag_external, scheme, label) in enumerate(PLACEMENT_VARIANTS, start=1):
        config = TemplateService(ROOT).load_template("gmd_paris_full")
        config["scalars"]["tag_external"] = tag_external
        case_root = results_layout.case_root(results_root, run_service.ascii_name(name))
        out_root = results_root
        tag = f"[{index}/{len(PLACEMENT_VARIANTS)}] {label}"
        case_root, figures, detail, elapsed = _execute(run_service, plot_service, config, name, out_root, scheme=scheme)
        if figures is None:
            failed.append((tag, detail))
            print(f"{tag}: FAIL（{detail}）")
            continue
        note = detail
        external = (plot_service.plot_data.get("cases") or {}).get(name, {}).get("external_mixing")
        if external and external.get("mixing_degree_mass"):
            series = external["mixing_degree_mass"]
            note = (detail + "；" if detail else "") + (
                f"质量加权混合度 t=0 {series[0][1]:.3f} → 终态 {series[-1][1]:.3f}"
            )
        ok_list.append((tag, case_root, figures, elapsed, note))
        print(f"{tag}: ok（{figures} 图，{elapsed:.1f}s{('；' + note) if note else ''}）→ {out_root}")

    manifest = results_root / "placement_paths.txt"
    with manifest.open("w", encoding="utf-8") as handle:
        handle.write("SCRAM BoxApp gmd_paris_full 放置 × 解析 四联（单臂运行）\n")
        handle.write(f"结果根: {results_root}\n")
        handle.write(f"组合: {len(ok_list)} ok / {len(failed)} 失败\n\n")
        for tag, path, figures, elapsed, note in ok_list:
            handle.write(f"[ok] {tag}\n     运行目录: {path}\n"
                         f"     图片目录: {path / 'figures'}（{figures} 图，{elapsed:.1f}s）\n")
            if note:
                handle.write(f"     备注: {note}\n")
        for tag, reason in failed:
            handle.write(f"[失败] {tag}: {reason}\n")

    print(f"\n==== 放置四联完成（总 {time.perf_counter() - started:.0f}s）====")
    print(f"ok {len(ok_list)} / 失败 {len(failed)}；路径清单: {manifest}")
    return 0 if not failed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="模板原生 / 全组合矩阵运行")
    parser.add_argument("--mode", choices=("native", "cross", "placements"), default="native",
                        help="native=每模板原样跑（默认，不改案例预设）；cross=模板×全部案例预设；"
                             "placements=gmd_paris_full 放置×解析四联（单臂，进 single/）")
    parser.add_argument("--results-root", type=Path, default=None,
                        help="结果根目录（默认应用默认结果根 internal_external_mixing）")
    args = parser.parse_args()

    results_root = Path(args.results_root).expanduser() if args.results_root else user_results_root()
    results_root.mkdir(parents=True, exist_ok=True)
    templates = TemplateService(ROOT).list_templates()
    run_service = RunService(ROOT)
    plot_service = PlotService(ROOT)

    if args.mode == "placements":
        return _run_placements(results_root, run_service, plot_service)

    if args.mode == "native":
        combos = [(template["id"], None) for template in templates]
        manifest_name = "template_paths.txt"
    else:
        combos = [(template["id"], case) for template in templates for case in CROSS_CASES]
        manifest_name = "matrix_paths.txt"

    started = time.perf_counter()
    ok_list: list[tuple[str, Path, int, float, str]] = []
    failed: list[tuple[str, str]] = []

    for index, (template_id, case_name) in enumerate(combos, start=1):
        config = TemplateService(ROOT).load_template(template_id)
        if case_name is None:
            # native：完全不动 config —— 过程开关与时长就是模板自带的值（预设机制已删除）
            scalars = config["scalars"]
            applied = (f"凝并={scalars['with_coag']} 冷凝={scalars['with_cond']} 成核={scalars['with_nucl']} "
                       f"时长={scalars['final_time_hours']}h")
            tag = f"[{index:2d}/{len(combos)}] {template_id}（模板原样：{applied}）"
            run_case = template_id
        else:
            # cross：显式写入开关/时长（组合表见 CROSS_CASES）。案例名带上模板 id，
            # 否则同一预设组合在不同模板间会撞同一个案例目录。
            for key, value in CROSS_CASES[case_name].items():
                config["scalars"][key] = value
            tag = f"[{index:2d}/{len(combos)}] {template_id} × {case_name}"
            run_case = f"{template_id}_{case_name}"
        # 案例目录 = <结果根>/<案例名>（_execute 内部推导，第二个参数是结果根）
        case_root, figures, detail, elapsed = _execute(run_service, plot_service, config, run_case, results_root)
        if figures is None:
            failed.append((tag, detail))
            print(f"{tag}: FAIL（{detail}）")
            continue
        ok_list.append((tag, case_root, figures, elapsed, detail))
        note = f"，{detail}" if detail else ""
        print(f"{tag}: ok（两臂 ok，{figures} 图，{elapsed:.1f}s{note}）→ {case_root}")

    manifest = results_root / manifest_name
    title = "模板原生" if args.mode == "native" else "交叉组合"
    with manifest.open("w", encoding="utf-8") as handle:
        handle.write(f"SCRAM BoxApp {title}运行结果路径\n")
        handle.write(f"结果根: {results_root}\n")
        handle.write(f"组合: {len(ok_list)} ok / {len(failed)} 失败\n\n")
        for tag, path, figures, elapsed, detail in ok_list:
            handle.write(f"[ok] {tag}\n     运行目录: {path}\n"
                         f"     图片目录: {path / 'figures'}（{figures} 图，{elapsed:.1f}s）\n")
            if detail:
                handle.write(f"     备注: {detail}\n")
        for tag, reason in failed:
            handle.write(f"[失败] {tag}: {reason}\n")

    print(f"\n==== {title}运行完成（总 {time.perf_counter() - started:.0f}s）====")
    print(f"ok {len(ok_list)} / 失败 {len(failed)}；路径清单: {manifest}")
    for tag, path, figures, _elapsed, detail in ok_list:
        note = f"（{detail}）" if detail else ""
        print(f"  [ok] {tag} → {path / 'figures'}（{figures} 图）{note}")
    for tag, reason in failed:
        print(f"  [失败] {tag}: {reason}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
