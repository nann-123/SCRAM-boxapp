"""Collect the per-round metrics of a SCRAM BoxApp verification round.

Usage:
    python scripts/linux/collect_metrics.py --round-dir install_logs/auto/<timestamp>

Writes <round-dir>/baseline.json and prints a comparison against the previous
round (install_logs/auto/latest/baseline.json) and against the teaching-manual
reference values. Exit codes: 0 = pass, 1 = warn, 2 = hard failure.

只做「同案例」比较：上轮基线里的案例名（case_name|scheme）与本轮不一致时，不判回归，
改为打印 INFO 说明"无可比基线"——跨案例/跨模板/跨步数比较会得出假结论。
`--deep-baseline` 可再叠加一次与最近一次 deep 轮的同案例比较（deep 轮专用）。

Reference values come from docs/SCRAM_BoxApp_本科教学实验手册.md（标准参考结果）and
are used as an order-of-magnitude check only: the authoritative comparison is
against the previous round, which uses the identical configuration.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# 教学手册「标准参考结果」：case, scheme -> (final_mass, final_number, rel_mass_%, rel_number_%)
MANUAL_REFERENCE = {
    ("gmd_paris_full", "INTERNAL_MIXING"): (32.7327, 1.0240e10, -3.36, -10.46),
    ("gmd_paris_full", "EXTERNAL_MIXING"): (33.8691, 1.1436e10, 0.00, 0.00),
}

# 阈值：与上一轮比（同配置，紧）；与手册参考比（跨环境，宽）
TOL_VS_PREVIOUS = 0.01          # 1%
TOL_VS_MANUAL = 0.025           # 2.5%
WALLCLOCK_FACTOR = 1.5
REL_RESIDUAL_MAX = 1e-6


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def collect(round_dir: Path) -> dict:
    tests = round_dir / "standard_tests"
    data: dict = {"final_state": {}, "performance": {}, "invariants": {}, "missing": []}

    for row in read_csv(tests / "final_state_summary.csv"):
        key = f"{row['case_name']}|{row['scheme']}"
        data["final_state"][key] = {
            "mass": float(row["final_total_mass"]),
            "number": float(row["final_total_number"]),
            "rel_mass_pct": float(row["relative_difference_vs_external_mass"]) * 100,
            "rel_number_pct": float(row["relative_difference_vs_external_number"]) * 100,
            "status": row["status"],
        }

    for row in read_csv(tests / "performance_summary.csv"):
        key = f"{row['case_name']}|{row['scheme']}"
        data["performance"][key] = {
            "status": row["status"],
            "wallclock_s": float(row["wallclock"]),
            "total_steps": int(float(row["total_steps"])),
        }

    anomaly: dict[str, int] = {}
    anomaly_by_case: dict[str, dict[str, int]] = {}
    has_nan = has_inf = 0
    rows = 0
    worst_rel = 0.0
    for flag in sorted(tests.glob("runs/*/*/csv/anomaly_flags.csv")):
        scheme = flag.parts[-3]  # .../runs/<case>/<scheme>/csv/anomaly_flags.csv
        case = flag.parts[-4]
        for row in read_csv(flag):
            key = f"{scheme}|{row['anomaly_type']}"
            anomaly[key] = anomaly.get(key, 0) + 1
            per_case = anomaly_by_case.setdefault(f"{case}|{scheme.upper()}", {})
            per_case[key] = per_case.get(key, 0) + 1
    for audit in sorted(tests.glob("runs/*/*/csv/conservation_audit.csv")):
        for row in read_csv(audit):
            rows += 1
            has_nan += int(row.get("has_nan") or 0)
            has_inf += int(row.get("has_inf") or 0)
            for res, after in (("coag_mass_residual", "coag_mass_after"),
                               ("coag_number_residual", "coag_number_after")):
                value = abs(float(row.get(res) or 0.0))
                base = abs(float(row.get(after) or 0.0))
                if base:
                    worst_rel = max(worst_rel, value / base)
    data["invariants"] = {
        "anomaly_counts": anomaly,
        "anomaly_by_case": anomaly_by_case,
        "anomaly_total": sum(anomaly.values()),
        "conservation_rows": rows,
        "has_nan": has_nan,
        "has_inf": has_inf,
        "max_relative_residual": worst_rel,
    }

    for name in ("standard_tests/final_state_summary.csv",
                 "standard_tests/performance_summary.csv"):
        if not (round_dir / name).exists():
            data["missing"].append(name)
    # runs/ 逐时步 CSV 会被 Phase 8「体积纪律」在轮次结束时删除：轮内采集时它必须存在，
    # 事后重跑（人工复核）时缺失属正常，只标记"不变量不可判定"，不当作硬失败。
    data["invariants_available"] = (round_dir / "standard_tests/runs").exists()
    if not data["invariants_available"]:
        data["invariants_note"] = "standard_tests/runs 不存在（已被体积纪律清理）：anomaly/守恒项不可判定"
    return data


def compare(current: dict, previous: dict | None) -> tuple[list[str], list[str], list[str]]:
    """返回 (hard, warn, info)。info = 说明性信息（含"无可比基线"），不参与结论。"""
    hard: list[str] = []
    warn: list[str] = []
    info: list[str] = []

    for key, perf in current["performance"].items():
        if perf["status"] != "ok":
            hard.append(f"{key}: status={perf['status']}")
    inv = current["invariants"]
    if inv["has_nan"] or inv["has_inf"]:
        hard.append(f"守恒审计出现 NaN/Inf（has_nan={inv['has_nan']}, has_inf={inv['has_inf']}）")
    if inv["max_relative_residual"] > REL_RESIDUAL_MAX:
        hard.append(f"最大相对残差 {inv['max_relative_residual']:.3e} > {REL_RESIDUAL_MAX:.0e}")
    for name in current["missing"]:
        hard.append(f"缺少预期产物：{name}")

    for key, state in current["final_state"].items():
        case, scheme = key.split("|")
        # Bug #1「幽灵粒子」判据（2026-09-11 加入）：状态正常但终态质量为 0 —— 正常模拟都应有质量，
        # 出现即说明初始质量为 0 的骨架被跑起来了（旧 default 基座）；交由 agent 复核（见 hunt_plan Q-13）
        if state["status"] == "ok" and abs(state["mass"]) < 1e-300:
            warn.append(f"{key}: 状态 ok 但终态质量为 0（Bug #1「幽灵粒子」特征：初始质量为 0 的骨架；"
                        "复核夹具 docs/checktest/zero_initial_mass_{test,fixed}.cfg）")
        ref = MANUAL_REFERENCE.get((case, scheme))
        if ref:
            for label, value, expected in (("终态质量", state["mass"], ref[0]),
                                           ("终态数量", state["number"], ref[1])):
                deviation = abs(value - expected) / abs(expected)
                if deviation > TOL_VS_MANUAL:
                    warn.append(f"{key}: {label} {value:.6g} 与手册参考 {expected:.6g} "
                                f"偏差 {deviation * 100:.2f}% > {TOL_VS_MANUAL * 100:.1f}%")

    if previous:
        compared = 0
        for key, state in current["final_state"].items():
            prev = previous.get("final_state", {}).get(key)
            if not prev:
                continue
            compared += 1
            for label, field in (("终态质量", "mass"), ("终态数量", "number")):
                if prev.get(field):
                    deviation = abs(state[field] - prev[field]) / abs(prev[field])
                    if deviation > TOL_VS_PREVIOUS:
                        warn.append(f"{key}: {label} 相对上一轮变化 {deviation * 100:.2f}% "
                                    f"> {TOL_VS_PREVIOUS * 100:.0f}%")
        total = len(current["final_state"])
        if compared:
            info.append(f"终态 mass/number：与上一轮同案例可比 {compared}/{total} 项，"
                        f"判据 ≤{TOL_VS_PREVIOUS * 100:.0f}%")
        else:
            cur_cases = "、".join(sorted(current["final_state"])) or "无"
            prev_cases = "、".join(sorted(previous.get("final_state", {}))) or "无"
            info.append(f"终态 mass/number：本轮案例（{cur_cases}）与上一轮基线（{prev_cases}）不重合"
                        f" → **未做**「与上一轮 ≤{TOL_VS_PREVIOUS * 100:.0f}%」判定")

        # 键规范化：final_state 用 CSV 里的 scheme（大写），runs/ 目录名是小写；
        # 若不做规范化，"同案例"会永远匹配不上而静默跳过（这正是本函数要避免的失效模式）
        def _norm(by_case: dict | None) -> dict:
            out = {}
            for key, counts in (by_case or {}).items():
                case, _, scheme = key.partition("|")
                out[f"{case}|{scheme.upper()}"] = counts
            return out

        prev_by_case = _norm(previous.get("invariants", {}).get("anomaly_by_case"))
        cur_by_case = _norm(current["invariants"].get("anomaly_by_case"))
        anom_compared = 0
        for case_key, counts in cur_by_case.items():
            prev_counts = prev_by_case.get(case_key)
            if prev_counts is None:
                continue
            anom_compared += 1
            for key, count in counts.items():
                if count > prev_counts.get(key, 0):
                    warn.append(f"异常标记 {case_key} {key} 由 {prev_counts.get(key, 0)} 增至 {count}")
        if anom_compared:
            info.append(f"异常标记：同案例可比 {anom_compared}/{len(cur_by_case)} 项（判断依据：条目数不超上一轮）")
        else:
            prev_total = previous.get("invariants", {}).get("anomaly_total")
            cur_total = current["invariants"]["anomaly_total"]
            if prev_total is not None and prev_total != cur_total:
                info.append(f"异常标记：上一轮基线无逐案例计数（旧格式），只能给出总量 {prev_total} → {cur_total}；"
                            "跨案例/跨步数的总量差不可判回归，不作告警")
            else:
                info.append("异常标记：无可比基线")

        for key, perf in current["performance"].items():
            prev = previous.get("performance", {}).get(key)
            if prev and prev.get("wallclock_s", 0) > 0:
                factor = perf["wallclock_s"] / prev["wallclock_s"]
                if factor > WALLCLOCK_FACTOR:
                    warn.append(f"{key}: wallclock {perf['wallclock_s']:.2f}s 为上一轮 "
                                f"{prev['wallclock_s']:.2f}s 的 {factor:.2f}×")
    return hard, warn, info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round-dir", required=True)
    parser.add_argument("--deep-baseline", default="",
                        help="最近一次 deep 轮的 baseline.json（deep 轮自比用，可选）")
    args = parser.parse_args()

    round_dir = Path(args.round_dir).resolve()
    round_dir.mkdir(parents=True, exist_ok=True)
    current = collect(round_dir)

    previous_path = round_dir.parent / "latest" / "baseline.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None

    baseline_file = round_dir / "baseline.json"
    if not current.get("invariants_available", True) and baseline_file.exists():
        # 事后重跑（runs/ 已清理）：不变量会被算成 0，绝不能用它覆盖已有的好基线
        print(f"== 本轮指标（{round_dir.name}）==")
        print(f"  不可判定：{current.get('invariants_note', '')}")
        print("  为保护已有 baseline.json，本轮不写入、不判结论（轮内运行时 runs/ 存在，不受影响）")
        return 0

    baseline_file.write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n")

    hard, warn, info = compare(current, previous)
    deep_path = Path(args.deep_baseline) if args.deep_baseline else None
    if deep_path:
        if deep_path.exists():
            d_hard, d_warn, d_info = compare(current, json.loads(deep_path.read_text()))
            hard += [f"[深轮] {x}" for x in d_hard]
            warn += [f"[深轮] {x}" for x in d_warn]
            info += [f"[深轮对比 {deep_path.name}] {x}" for x in d_info]
        else:
            info.append(f"深轮对比：无历史 deep 基线（{deep_path} 不存在）")

    print(f"== 本轮指标（{round_dir.name}）==")
    for key, state in sorted(current["final_state"].items()):
        case, scheme = key.split("|")
        ref = MANUAL_REFERENCE.get((case, scheme))
        suffix = ""
        if ref:
            suffix = (f"  手册参考 {ref[0]:.4f} / {ref[1]:.4e}"
                      f"（偏差 {abs(state['mass'] - ref[0]) / ref[0] * 100:.3f}% / "
                      f"{abs(state['number'] - ref[1]) / ref[1] * 100:.3f}%）")
        print(f"  {scheme:16s} mass={state['mass']:.4f} number={state['number']:.4e} "
              f"rel={state['rel_mass_pct']:+.2f}%/{state['rel_number_pct']:+.2f}%{suffix}")
    for key, perf in sorted(current["performance"].items()):
        print(f"  {key.split('|')[1]:16s} status={perf['status']:6s} "
              f"wallclock={perf['wallclock_s']:.2f}s steps={perf['total_steps']}")
    inv = current["invariants"]
    print(f"  不变量: anomaly_total={inv['anomaly_total']} "
          f"max_rel_residual={inv['max_relative_residual']:.3e} "
          f"has_nan={inv['has_nan']} has_inf={inv['has_inf']}")
    if not current.get("invariants_available", True):
        print(f"  注意: {current.get('invariants_note', '')}")
    print(f"  基线对比: {'有（上一轮 latest/baseline.json）' if previous else '无（首轮）'}")
    for item in info:
        print(f"  INFO  {item}")

    for item in hard:
        print(f"  HARD  {item}")
    for item in warn:
        print(f"  WARN  {item}")
    if hard:
        print("结论：FAIL（硬性不满足）")
        return 2
    if warn:
        print("结论：WARN（需人工确认，见上）")
        return 1
    print("结论：PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
