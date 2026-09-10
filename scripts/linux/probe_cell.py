"""探测一个参数格子：跑完两种混合假设，汇总「发现信号」而不是简单的 pass/fail。

用法示例：

    # 跑一个未覆盖的格子（模板 + 预设 + RDB 核心模式覆盖）
    python scripts/linux/probe_cell.py --template gmd_paris_condensation \
        --case gmd_paris_condensation --set redistribution_option=core_nogrow

    # 直接改数值型标量（如重分配方法 6 = euler_coupled）
    python scripts/linux/probe_cell.py --template gmd_hazy_coag_cond \
        --case gmd_hazy_coag_cond --set redistribution_method=6

    # 只跑单侧
    python scripts/linux/probe_cell.py --template tutorial_minimal --set duration_hours=0.5

（注意：探测器固定运行 internal + external 两侧，暂不支持只跑单侧。）

产出：<out>/probe.json 与终端报告（默认 out = install_logs/auto/probes/<格名>）。
退出码：0 = 无发现信号，1 = 有需要注意的信号，2 = 硬失败（status≠ok / NaN / 日志崩溃关键字）。

本脚本只做「采集」，如何判断"这是不是新 Bug"由 docs/linux_debugging/probe_backlog.md 的规则决定
（必须给出最小复现、区分已知现象与新增异常）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEME_DIR = {"INTERNAL_MIXING": "internal_mixing", "EXTERNAL_MIXING": "external_mixing"}
LOG_CRASH_PATTERNS = ["non conservation", "STOP", "NaN", "IEEE_INVALID", "IEEE_DIVIDE_BY_ZERO"]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def coerce(value: str):
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe one parameter cell.")
    parser.add_argument("--template", required=True)
    parser.add_argument("--case", default=None, help="CASE_PRESETS key (默认与模板同名)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="覆盖标量字段，可重复；数值自动转 int/float")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    from app.config_binding.config_model import ConfigModel
    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    case_name = args.case or args.template
    overrides = {}
    for item in args.set:
        key, _, raw = item.partition("=")
        overrides[key.strip()] = coerce(raw.strip())

    label = "__".join([args.template, case_name] + [f"{k}-{v}" for k, v in sorted(overrides.items())])
    out = (args.out or ROOT / "install_logs" / "auto" / "probes" / label).resolve()
    out.mkdir(parents=True, exist_ok=True)

    config = TemplateService(ROOT).load_template(args.template)
    if args.case:
        config["case_preset"] = case_name
    for key, value in overrides.items():
        if key in config.get("scalars", {}):
            config["scalars"][key] = value
        else:
            config[key] = value

    errors = ConfigModel(ROOT).validate(config)
    if errors:
        print("配置校验失败：" + "; ".join(errors))
        return 2

    runner = RunService(ROOT)
    runner.set_results_root(out)
    started = time.time()
    rows = runner.run_comparison(config, case_name)
    elapsed = time.time() - started

    findings: list[str] = []
    report = {
        "cell": {"template": args.template, "case": case_name, "overrides": overrides},
        "runs": {}, "invariants": {}, "log_keywords": {}, "elapsed_s": round(elapsed, 2),
    }
    hard_failure = False

    for row in rows:
        scheme = row["scheme"]
        key = f"{scheme}"
        report["runs"][key] = {
            "status": row["status"],
            "wallclock_s": float(row["wallclock"]),
            "total_steps": int(float(row["total_steps"])),
            "final_mass": float(row["final_mass"]),
            "final_number": float(row["final_number"]),
        }
        if row["status"] != "ok":
            findings.append(f"status={row['status']}（{scheme}）")
            hard_failure = True
        for field in ("final_mass", "final_number"):
            value = float(row[field])
            if value != value or value in (float("inf"), float("-inf")):
                findings.append(f"{scheme} 的 {field} 非有限值")
                hard_failure = True

        run_dir = out / "runs" / case_name / SCHEME_DIR.get(scheme, scheme.lower())
        anomaly: dict[str, int] = {}
        has_nan = has_inf = rows_audit = 0
        worst_rel = 0.0
        for flag in read_rows(run_dir / "csv" / "anomaly_flags.csv"):
            anomaly[flag["anomaly_type"]] = anomaly.get(flag["anomaly_type"], 0) + 1
        for audit in read_rows(run_dir / "csv" / "conservation_audit.csv"):
            rows_audit += 1
            has_nan += int(audit.get("has_nan") or 0)
            has_inf += int(audit.get("has_inf") or 0)
            for res, after in (("coag_mass_residual", "coag_mass_after"),
                               ("coag_number_residual", "coag_number_after")):
                base = abs(float(audit.get(after) or 0.0))
                if base:
                    worst_rel = max(worst_rel, abs(float(audit.get(res) or 0.0)) / base)
        report["invariants"][scheme] = {
            "anomaly_counts": anomaly, "conservation_rows": rows_audit,
            "has_nan": has_nan, "has_inf": has_inf,
            "max_relative_residual": worst_rel,
        }
        if has_nan or has_inf:
            findings.append(f"{scheme} 守恒审计出现 NaN/Inf")
            hard_failure = True
        if rows_audit == 0:
            findings.append(f"{scheme} 没有守恒审计行（可能根本没跑起来）")
            hard_failure = True

        log_path = run_dir / "logs" / "run.log"
        hits = []
        if log_path.exists():
            text = log_path.read_text(errors="replace")
            hits = [p for p in LOG_CRASH_PATTERNS if re.search(re.escape(p), text, re.IGNORECASE)]
        report["log_keywords"][scheme] = hits
        if hits:
            findings.append(f"{scheme} 日志含崩溃/异常关键字：{', '.join(hits)}")
            hard_failure = True

    (out / "probe.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    print(f"== 探测格子：{args.template} / {case_name} {overrides or ''} ==")
    print(f"   输出：{out}")
    for key, run in sorted(report["runs"].items()):
        inv = report["invariants"][key]
        print(f"   {key:16s} status={run['status']:6s} wallclock={run['wallclock_s']:7.2f}s "
              f"steps={run['total_steps']:4d} mass={run['final_mass']:.6g} number={run['final_number']:.6g}")
        print(f"   {'':16s} anomaly={sum(inv['anomaly_counts'].values())} "
              f"max_rel_residual={inv['max_relative_residual']:.3e} "
              f"has_nan={inv['has_nan']} has_inf={inv['has_inf']}")
    if findings:
        for item in findings:
            print(f"   信号：{item}")
    else:
        print("   信号：无（该格子未暴露异常；请按 probe_backlog 的规则决定是否扩大探测）")
    print("   提示：把结论按 BUG_TRACKING 的字段写入 docs/linux_debugging/probe_backlog.md 台账；"
          "若确认为新 Bug，同时补 docs/checktest/<bug>_test.cfg 与 _fixed.cfg")
    return 2 if hard_failure else (1 if findings else 0)


if __name__ == "__main__":
    sys.exit(main())
