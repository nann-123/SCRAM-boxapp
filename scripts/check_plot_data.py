#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图 vs CSV 数据核查（绘图核查 20260915 的持续化落地，接替已退役的 scripts/linux/audit_plots.py）。

背景：`docs/绘图正确性核查_20260915.md` 的结论是"出图链路能跑通，但'图上的数'没有一道数值判据"，
当时靠一次性人工核查发现并修掉 1 处确定画错（mixed/unmixed 组成档硬编码 {1,3,6,11,20}）。
本脚本把那次核查变成**每次标准测试都跑**的自动判据：plot_service 画进图里的每一个数，
都与数据源 CSV **独立重算**后逐项对账。

对账项（对应核查文档 §一 的图-数据源清单）：
  1) 时序曲线 time/mass/number 逐点 == timestep_summary.csv 对应列（防列拿错/列拿丢）；
  2) 终态柱 mass/number == final_state_summary.csv 对应单元格；缺失格 == 实际缺数据的 (case, scheme)；
  3) 相对差曲线 == 两臂曲线在并集网格上的独立重算（插值口径与 plot_service 相同）；
     参考臂不得有相对差条目，非参考臂必须有；
  4) 未混合档 == "t=0 有质量的组成档"独立推导——当年 0.94 误报（硬编码集合漏档）会被这道拦下；
  5) 混合分数序列 == 按 timestep 分档的 mixed/total 独立重算，且取值必须在 [0, 1]；
  6) 逐粒径连续混合度：每档质量与质量加权混合度 == 独立重算；各粒径质量之和 ≈ 该臂终态总质量（P3 口径；容差 1e-9）；
  7) 异常计数 == anomaly_flags.csv 独立重数。

独立性的边界：CSV 容错解析（丢指数标记补 E）与 plot_service 同策略但独立实现；
聚合 / 选档 / 插值 / 求和逻辑全部在本文件重写，不调用 plot_service 的任何函数——
两条计算路径只有在"数对"时才会相等。

用法：
  python scripts/check_plot_data.py <results_root>     # 对既有运行产物核查（会重画一遍图）
  标准测试已内置：run_standard_tests.py 的 runtime_smoke 在出图后自动调用 verify_plot_data。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 与 plot_service 同策略、独立实现：Fortran 列表输出会把 1.03E-297 写成 "1.03...-297"，补回 E。
_MALFORMED_FLOAT = re.compile(r"^([-+]?[0-9]*\.?[0-9]+)([-+][0-9]{2,3})$")


def _to_float(text: str) -> float:
    value = str(text).strip()
    try:
        return float(value)
    except ValueError:
        match = _MALFORMED_FLOAT.match(value)
        if match:
            return float(f"{match.group(1)}E{match.group(2)}")
        raise


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def _schemes_with_csv(case_dir: Path) -> list[str]:
    """独立列出该 case 下真有 timestep_summary.csv 的臂（不经过 plot_service）。"""
    names = []
    for scheme_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
        if (scheme_dir / "csv" / "timestep_summary.csv").exists():
            names.append(scheme_dir.name)
    return names


def _pick_reference(schemes: list[str]) -> str | None:
    for preferred in ("external_mixing", "EXTERNAL_MIXING"):
        if preferred in schemes:
            return preferred
    return schemes[0] if schemes else None


def _timestep_series(path: Path) -> dict[str, list[float]]:
    rows = _read(path)
    return {
        "time": [_to_float(r["time_seconds"]) for r in rows],
        "mass": [_to_float(r["total_mass"]) for r in rows],
        "number": [_to_float(r["total_number"]) for r in rows],
    }


def _relative_curve(arm: dict[str, list[float]], ref: dict[str, list[float]]) -> dict[str, list[float]]:
    """相对差独立重算：两臂插值到并集网格，rel = (arm-ref)/max(|ref|,1e-20)。"""
    times = np.array(arm["time"], dtype=float)
    ref_times = np.array(ref["time"], dtype=float)
    grid = np.union1d(times, ref_times)
    out: dict[str, list[float]] = {}
    for key in ("mass", "number"):
        arm_v = np.array(arm[key], dtype=float)
        ref_v = np.array(ref[key], dtype=float)
        rel = (np.interp(grid, times, arm_v) - np.interp(grid, ref_times, ref_v)) / np.maximum(
            np.abs(np.interp(grid, ref_times, ref_v)), 1.0e-20
        )
        out[key] = rel.tolist()
    out["grid"] = grid.tolist()
    return out


def _initial_bins(mass_rows: list[dict[str, str]]) -> set[int]:
    """独立推导：t=0 有质量的组成档（旧口径"偏移"的基准）。"""
    return {
        int(_to_float(row["composition_bin"]))
        for row in mass_rows
        if int(_to_float(row["timestep"])) == 0 and _to_float(row["mass"]) > 0.0
    }


def _drift_series(rows: list[dict[str, str]], column: str, initial: set[int]) -> list[list[float]]:
    """独立重算"距初始档偏移"序列（旧口径保留版）。"""
    totals: dict[int, dict[str, float]] = defaultdict(lambda: {"time": 0.0, "total": 0.0, "outside": 0.0})
    for row in rows:
        timestep = int(_to_float(row["timestep"]))
        value = _to_float(row[column])
        totals[timestep]["time"] = _to_float(row["time_seconds"])
        totals[timestep]["total"] += value
        if int(_to_float(row["composition_bin"])) not in initial:
            totals[timestep]["outside"] += value
    return [
        [totals[t]["time"], totals[t]["outside"] / totals[t]["total"]]
        for t in sorted(totals)
        if totals[t]["total"] > 0.0
    ]


def _grid_degrees(grid_spec_path, fractions_path) -> dict[int, dict] | None:
    """独立重建"档 → 代表组成 → 混合度"（本文件内重写公式，不复用 plot_service 的实现）。

    口径（与 app/services/composition_grid.py 相同，但此处独立实现以便交叉验证）：
    代表组成 = 从各组下界出发按剩余容量比例填充；混合度 = 1 − 最大组份额。
    """
    try:
        spec = json.loads(Path(grid_spec_path).read_text(encoding="utf-8"))
        n_groups = int(spec["n_groups"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    pairs = []
    for line in Path(fractions_path).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            pairs.append((float(parts[0]), float(parts[1])))
    if n_groups <= 0 or len(pairs) == 0 or len(pairs) % n_groups != 0:
        return None
    out: dict[int, dict] = {}
    for index in range(1, len(pairs) // n_groups + 1):
        raw = pairs[(index - 1) * n_groups:index * n_groups]
        intervals = [[lo, hi] for lo, hi in raw]
        if len(intervals) >= 2:
            others = intervals[:-1]
            last_lo = max(0.0, 1.0 - sum(item[1] for item in others))
            last_hi = max(0.0, 1.0 - sum(item[0] for item in others))
            intervals[-1] = [last_lo, max(last_hi, last_lo)]
        lo = [item[0] for item in intervals]
        hi = [item[1] for item in intervals]
        base = sum(lo)
        capacity = sum(h - l for l, h in zip(lo, hi))
        remaining = max(0.0, 1.0 - base)
        if capacity <= 1e-12:
            reps = [v / base if base > 0 else 0.0 for v in lo]
        else:
            fill = min(remaining, capacity)
            reps = [l + fill * (h - l) / capacity for l, h in zip(lo, hi)]
            total = sum(reps)
            if abs(total - 1.0) > 1e-9:
                reps = [v / total for v in reps]
        out[index] = {"representative": reps, "mixing_degree": 1.0 - max(reps), "max_share": max(reps)}
    return out


def _mixing_degree(rows: list[dict[str, str]], column: str, degrees: dict[int, dict]) -> list[list[float]]:
    """独立重算混合度序列：按 timestep 分组做加权平均（total<=0 跳过）。"""
    totals: dict[int, dict[str, float]] = defaultdict(lambda: {"time": 0.0, "total": 0.0, "weighted": 0.0})
    for row in rows:
        timestep = int(_to_float(row["timestep"]))
        value = _to_float(row[column])
        index = int(_to_float(row["composition_bin"]))
        if index not in degrees:
            continue
        totals[timestep]["time"] = _to_float(row["time_seconds"])
        totals[timestep]["total"] += value
        totals[timestep]["weighted"] += value * degrees[index]["mixing_degree"]
    return [
        [totals[t]["time"], totals[t]["weighted"] / totals[t]["total"]]
        for t in sorted(totals)
        if totals[t]["total"] > 0.0
    ]


def _close(a: float, b: float, rel: float = 1e-9) -> bool:
    return abs(a - b) <= rel * max(abs(a), abs(b), 1.0)


def verify_plot_data(plot) -> list[str]:
    """对已 generate_all 的 PlotService 逐项对账，返回违规清单（空 = 全部一致）。"""
    problems: list[str] = []
    root = plot.results_root
    data = plot.plot_data

    # 1) runtime 柱：标签序与值序 == performance_summary.csv
    perf_path = root / "performance_summary.csv"
    if perf_path.exists():
        entry = data.get("runtime")
        if entry is None:
            problems.append("runtime: performance_summary.csv 存在但图未收录数据")
        else:
            rows = _read(perf_path)
            if entry["labels"] != [f"{r['case_name']}\n{r['scheme']}" for r in rows]:
                problems.append("runtime: 柱标签与 CSV 行序不一致")
            if entry["wallclock"] != [_to_float(r["wallclock"]) for r in rows]:
                problems.append("runtime: 墙钟值与 CSV 不一致")

    # 2) 终态柱：逐单元格 == final_state_summary.csv
    final_path = root / "final_state_summary.csv"
    if final_path.exists():
        entry = data.get("final_state")
        if entry is None:
            problems.append("final_state: final_state_summary.csv 存在但图未收录数据")
        else:
            rows = _read(final_path)
            exp_mass: dict = defaultdict(dict)
            exp_number: dict = defaultdict(dict)
            for r in rows:
                exp_mass[r["case_name"]][r["scheme"]] = _to_float(r["final_total_mass"])
                exp_number[r["case_name"]][r["scheme"]] = _to_float(r["final_total_number"])
            cases = sorted(exp_mass)
            if entry["cases"] != cases:
                problems.append("final_state: case 列表与 CSV 不一致")
            for c in cases:
                for s in exp_mass[c]:
                    if entry["mass"].get(c, {}).get(s) != exp_mass[c][s]:
                        problems.append(f"final_state: {c}/{s} 终态质量与 CSV 不一致")
                    if entry["number"].get(c, {}).get(s) != exp_number[c][s]:
                        problems.append(f"final_state: {c}/{s} 终态粒子数与 CSV 不一致")
            schemes = {r["scheme"] for r in rows}
            exp_missing = sorted({(c, s) for c in cases for s in schemes if s not in exp_mass[c]})
            if entry["missing"] != [list(cell) for cell in exp_missing]:
                problems.append("final_state: 缺失格标注与实际不一致")

    # 3)~7) 逐 case：时序 / 相对差 / 外混状态 / 异常计数
    from app.services import results_layout

    # 2026-09-30 新布局：结果根 = 案例目录，臂目录是它的子目录（不再有 runs/<案例>/）。
    # 旧布局（<根>/runs/<案例>/）仍兼容遍历，便于核查历史存档。
    legacy_root = root / "runs"
    case_dirs = [root] if results_layout.iter_arms(root) else []
    if legacy_root.is_dir():
        case_dirs.extend(sorted(p for p in legacy_root.iterdir() if p.is_dir()))
    for case_dir in case_dirs:
        schemes = _schemes_with_csv(case_dir)
        if not schemes:
            continue
        # 与 plot_service 口径一致：零数据案例（CSV 只有表头）不画图，也不参与对账
        if all(not _read(case_dir / s / "csv" / "timestep_summary.csv") for s in schemes):
            continue
        label = case_dir.name
        entry = (data.get("cases") or {}).get(label)
        if entry is None:
            problems.append(f"{label}: 有时序数据但绘图清单缺失（图未按预期生成）")
            continue
        if entry["schemes"] != schemes:
            problems.append(f"{label}: 参与绘图的臂清单与目录实况不一致")
        series = {}
        for s in schemes:
            series[s] = _timestep_series(case_dir / s / "csv" / "timestep_summary.csv")
            got = entry["series"].get(s)
            if got is None:
                problems.append(f"{label}/{s}: 曲线数据未收录")
                continue
            for key in ("time", "mass", "number"):
                if got.get(key) != series[s][key]:
                    problems.append(f"{label}/{s}: {key} 曲线与 timestep_summary.csv 逐点不一致")
        # 相对差：参考臂挑选 + 独立重算
        exp_ref = _pick_reference(schemes)
        if entry.get("ref") != exp_ref:
            problems.append(f"{label}: 参考臂为 {entry.get('ref')}，独立挑选结果为 {exp_ref}")
        if len(schemes) > 1 and exp_ref is not None:
            rel_entry = entry.get("relative") or {}
            recomputed = {s: _relative_curve(series[s], series[exp_ref]) for s in schemes if s != exp_ref}
            for kind in ("mass", "number"):
                got_kind = rel_entry.get(kind) or {}
                for s in schemes:
                    if s == exp_ref:
                        if s in got_kind:
                            problems.append(f"{label}: 参考臂 {exp_ref} 不应有 {kind} 相对差曲线")
                        continue
                    got = got_kind.get(s)
                    if got is None:
                        problems.append(f"{label}: {kind} 相对差曲线缺 {s}")
                        continue
                    if got["grid"] != recomputed[s]["grid"]:
                        problems.append(f"{label}/{s}: {kind} 相对差公共网格与独立重算不一致")
                    if not np.array_equal(np.array(got["rel"]), np.array(recomputed[s][kind])):
                        problems.append(f"{label}/{s}: {kind} 相对差曲线与独立重算不一致")
        # 外混状态图（仅当数据文件存在时要求收录；单臂内混运行不生成该图，与 plot_service 口径一致）
        if exp_ref is not None and "external" in exp_ref.lower():
            mass_csv = case_dir / exp_ref / "csv" / "size_composition_mass.csv"
            number_csv = case_dir / exp_ref / "csv" / "size_composition_number.csv"
            em = entry.get("external_mixing")
            if not mass_csv.exists() or not number_csv.exists():
                if em is not None:
                    problems.append(f"{label}: 外混状态图有清单但 size_composition CSV 缺失")
            elif em is None:
                problems.append(f"{label}: size_composition CSV 存在但外混状态图未收录")
            else:
                mass_rows = _read(mass_csv)
                number_rows = _read(number_csv)
                # (1) 旧口径保留版：距初始档的偏移（不依赖档映射，任何运行都应有）
                exp_initial = _initial_bins(mass_rows)
                if exp_initial:
                    if em.get("initial_bins") != sorted(exp_initial):
                        problems.append(f"{label}: 初始档清单与独立推导不一致")
                    for key, column, rows in (
                        ("drift_mass", "mass", mass_rows),
                        ("drift_number", "number", number_rows),
                    ):
                        expected = _drift_series(rows, column, exp_initial)
                        if em.get(key) != expected:
                            problems.append(f"{label}: {key}（距初始档偏移）与独立重算不一致")
                elif em.get("drift_mass") is not None:
                    problems.append(f"{label}: t=0 无有质量档，偏移图不应生成")
                # (2) 新口径：混合度（需要内核落盘的档→组成映射；老运行无存档则图不生成）
                grid_path = case_dir / exp_ref / "csv" / "composition_grid.json"
                fractions_path = case_dir / exp_ref / "csv" / "fractions.txt"
                degrees = (
                    _grid_degrees(grid_path, fractions_path)
                    if grid_path.exists() and fractions_path.exists()
                    else None
                )
                if degrees is None:
                    continue
                if em.get("mixing_degree_mass") is None:
                    problems.append(f"{label}: 有档映射存档但混合度图未收录")
                    continue
                # 映射自检：代表组成必须是合法组成（Σ=1、组份额落在 [0,1]）
                for index, item in degrees.items():
                    total = sum(item["representative"])
                    if abs(total - 1.0) > 1e-6:
                        problems.append(f"{label}: 档{index} 代表组成 Σ={total:.6f} ≠ 1（映射表缺陷）")
                    if not all(0.0 <= v <= 1.0 for v in item["representative"]):
                        problems.append(f"{label}: 档{index} 代表组成越界")
                for key, column, rows in (
                    ("mixing_degree_mass", "mass", mass_rows),
                    ("mixing_degree_number", "number", number_rows),
                ):
                    expected = _mixing_degree(rows, column, degrees)
                    if em[key] != expected:
                        problems.append(f"{label}: {key} 与独立重算不一致")
                    bad = [pt for pt in expected if not (0.0 <= pt[1] <= 1.0)]
                    if bad:
                        problems.append(f"{label}: {key} 出现 [0,1] 之外的值（首例 {bad[0]}）")
                # 逐粒径连续混合度：独立重算"该档质量"与"该档质量加权混合度"
                final_timestep = max(int(_to_float(r["timestep"])) for r in mass_rows)
                exp_size_mass: dict = defaultdict(float)
                exp_size_weighted: dict = defaultdict(float)
                for r in mass_rows:
                    if int(_to_float(r["timestep"])) != final_timestep:
                        continue
                    index = int(_to_float(r["composition_bin"]))
                    if index not in degrees:
                        continue
                    value = _to_float(r["mass"])
                    size = int(_to_float(r["size_bin"]))
                    exp_size_mass[size] += value
                    exp_size_weighted[size] += value * degrees[index]["mixing_degree"]
                if set(em.get("by_size_mass") or {}) != {str(k) for k in exp_size_mass}:
                    problems.append(f"{label}: 逐粒径质量档集合与独立重算不一致")
                else:
                    for size_key, mass_value in em["by_size_mass"].items():
                        size = int(size_key)
                        if mass_value != exp_size_mass[size]:
                            problems.append(f"{label}: 逐粒径 size={size_key} 质量与独立重算不一致")
                        expected_degree = (
                            exp_size_weighted[size] / exp_size_mass[size] if exp_size_mass[size] > 0.0 else 0.0
                        )
                        if em["by_size_degree"].get(size_key) != expected_degree:
                            problems.append(f"{label}: 逐粒径 size={size_key} 混合度与独立重算不一致")
                        if not (0.0 <= expected_degree <= 1.0):
                            problems.append(f"{label}: 逐粒径 size={size_key} 混合度越界")
                    # 画柱集合 == 质量高于"总量 1e-6"的档（痕量档不画，与绘图口径一致）
                    total_final = sum(exp_size_mass.values())
                    floor = total_final * 1e-6 if total_final > 0.0 else 0.0
                    exp_drawn = sorted(s for s in exp_size_mass if exp_size_mass[s] > floor)
                    if em.get("drawn_bins") != exp_drawn:
                        problems.append(f"{label}: 逐粒径画柱集合 {em.get('drawn_bins')} 与独立重算 {exp_drawn} 不一致")
                    # P3 口径：各粒径质量之和 ≈ 该臂终态总质量（求和次序不同，用容差）
                    total = sum(em["by_size_mass"].values())
                    final_state = (root / "final_state_summary.csv").exists()
                    if final_state:
                        ext_rows = [r for r in _read(root / "final_state_summary.csv") if r["scheme"] == exp_ref]
                        if ext_rows and label in {r["case_name"] for r in ext_rows}:
                            ref_total = [
                                _to_float(r["final_total_mass"])
                                for r in ext_rows
                                if r["case_name"] == label
                            ][0]
                            if not _close(total, ref_total):
                                problems.append(
                                    f"{label}: 逐粒径质量之和 {total} 与终态总质量 {ref_total} 偏差超容差（P3 判据）"
                                )
        # 异常计数
        exp_anomaly: dict = defaultdict(int)
        for s in schemes:
            path = case_dir / s / "csv" / "anomaly_flags.csv"
            if path.exists():
                for row in _read(path):
                    exp_anomaly[row.get("anomaly_type", "unknown")] += 1
        if entry.get("anomaly_counts", {}) != dict(exp_anomaly):
            problems.append(f"{label}: 异常计数与 anomaly_flags.csv 独立重数不一致")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="图 vs CSV 数据核查（独立重算，逐项对账）")
    parser.add_argument("results_root", type=Path, help="比较运行的结果根目录（含 runs/ 与 summary CSV）")
    args = parser.parse_args()

    from app.services.plot_service import PlotService

    plot = PlotService(ROOT)
    plot.generate_all(args.results_root)
    problems = verify_plot_data(plot)
    if problems:
        for problem in problems:
            print("!!", problem)
        print(f"plot_data_check: FAIL（{len(problems)} 项不一致）")
        return 1
    cases = len((plot.plot_data.get("cases") or {}))
    print(f"plot_data_check: ok —— 图上每一个数都与 CSV 独立重算一致（{cases} 个 case）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
