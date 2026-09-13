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
# 致命关键字：程序真的 STOP/中止（这些才让格子判 failed）。
# 判据按上游 euler_coupled.f90 的**活 STOP** 取值：只有 :425/:434 两处 "…total !!"（其后 :429/:438
# 是活 STOP）算致命；:248/:258 的逐 bin "…ds algo!!"、以及 :371 那处（其 :375 是 `!STOP`）都是
# 信息性打印，不进这一列——旧写法只写 "non conservation" 会把它们一并判成 failed（2026-09-13 复核）。
LOG_FATAL_PATTERNS = ["non conservation du nombre total", "non conservation de la masse totale",
                      "STOP", "NaN", "Program received signal", "segmentation"]
# 信息性打印里的 STOP 字样：法语 "sans STOP"＝"不带 STOP"。裸匹配 "STOP" 会把跑满全程的正常
# 运行判成 failed（2026-09-13 复核 Q-27 的 status=failed 就是这么来的，见 review_2026-09-13.md）。
LOG_INFO_STOP_LITERAL = re.compile(r"sans\s+STOP", re.IGNORECASE)
# 浮点标志：只说明某处发生过除零/无效运算，程序通常继续（见 2026-09-12 复核 §二 7c）。
# 过去把它并进判据，导致任何走 euler_coupled 的格子永远 failed、真问题被淹没，故单列。
LOG_FP_FLAG_PATTERNS = ["IEEE_INVALID", "IEEE_DIVIDE_BY_ZERO", "IEEE_OVERFLOW", "IEEE_UNDERFLOW"]


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
    parser.add_argument("--template", default=None)
    parser.add_argument("--cfg", default=None,
                        help="直接跑一个原始 cfg 文件（与 --template 二选一）；用于 docs/checktest/ 下的夹具，"
                             "例如 Bug #1 的 zero_initial_mass_{test,fixed}.cfg")
    parser.add_argument("--case", default=None, help="CASE_PRESETS key (默认与模板同名)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="覆盖标量字段，可重复；数值自动转 int/float")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if not args.template and not args.cfg:
        parser.error("需要 --template 或 --cfg 之一")

    from app.config_binding.config_model import ConfigModel
    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    if args.cfg:
        cfg_path = Path(args.cfg)
        if not cfg_path.is_absolute():
            cfg_path = ROOT / cfg_path
        if not cfg_path.exists():
            print(f"cfg 不存在：{cfg_path}")
            return 2
        case_name = args.case or cfg_path.stem
        label = f"cfg__{case_name}"
    else:
        case_name = args.case or args.template
        label = args.template
    overrides = {}
    for item in args.set:
        key, _, raw = item.partition("=")
        overrides[key.strip()] = coerce(raw.strip())

    label = "__".join([label, case_name] + [f"{k}-{v}" for k, v in sorted(overrides.items())])
    out = (args.out or ROOT / "install_logs" / "auto" / "probes" / label).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.cfg:
        config = ConfigModel(ROOT).parse(cfg_path)
        config["template_name"] = cfg_path.stem
        # 夹具要按"文件里写的"跑：清掉 case_preset，避免被案例预设的过程开关/时长覆盖
        config["case_preset"] = ""
    else:
        config = TemplateService(ROOT).load_template(args.template)
    if args.case and not args.cfg:
        config["case_preset"] = case_name
    for key, value in overrides.items():
        if key in config.get("scalars", {}):
            config["scalars"][key] = value
        else:
            config[key] = value
    # Bug #11（2026-09-11）：把覆写的键标成显式，避免被 case preset 覆盖；
    # 覆盖不到的键由下方的"覆写落地校验"报出来，不再静默丢弃。
    if overrides:
        config["explicit_keys"] = sorted(set(config.get("explicit_keys", [])) | set(overrides))

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

    # --- 覆写落地校验（2026-09-11 新增）----------------------------------------
    # run_service._with_case_preset 会**无条件**覆盖 with_coag/with_cond/with_nucl/final_time_hours
    # （Bug #11）。不校验的话，--set 会被静默丢弃、探测"什么都没测到"却记为 clean。
    dropped: list[str] = []
    try:
        schema_data = json.loads((ROOT / "core" / "schema" / "config_schema.json").read_text())
    except Exception:
        schema_data = {}

    def _line_of(key: str) -> int | None:
        found: list[int] = []

        def walk(node) -> None:
            if isinstance(node, dict):
                if node.get("key") == key and "line_index" in node:
                    try:
                        found.append(int(node["line_index"]))
                    except (TypeError, ValueError):
                        pass
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(schema_data)
        return found[0] if found else None

    generated = Path.home() / ".cache" / "scram_boxapp_mixing" / "generated_configs"
    for okey, ovalue in overrides.items():
        line_i = _line_of(okey)
        if line_i is None:
            continue
        for mode in ("internal_mixing", "external_mixing"):
            cfg_file = generated / f"{case_name}_{mode}.cfg"
            if not cfg_file.exists():
                continue
            try:
                tokens = cfg_file.read_text(errors="replace").splitlines()[line_i].split("##")[0].split()
            except IndexError:
                continue
            if not tokens:
                continue
            # 一行可能承载多个字段（例："with_nucl nucl_model"），只比 tokens[0] 会误报
            # （2026-09-12 实测：--set nucl_model=5 被报"未落地"，实际写进了第二个 token）。
            # 故：只要该行的任一 token 等于请求值就算落地。
            def _eq(token: str) -> bool:
                try:
                    return abs(float(token) - float(ovalue)) < 1e-12
                except (TypeError, ValueError):
                    return str(token) == str(ovalue)

            if not any(_eq(t) for t in tokens):
                dropped.append(f"{okey}={ovalue} 未落地（{cfg_file.name} 该行为 {' '.join(tokens)}）")
    if dropped:
        print("  !! 覆写未生效：请求的参数没有写进生成的 cfg（可能被 case preset 覆盖，见 Bug #11）")
        for item in dict.fromkeys(dropped):
            print(f"     - {item}")
        print("     → 本次运行**不能**作为该参数的探测结论（实际跑的是别的配置）")
        findings.append("覆写未生效：" + "; ".join(dict.fromkeys(dropped)))

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
        fatal, flags = [], []
        if log_path.exists():
            text = log_path.read_text(errors="replace")
            # 先把信息性的 "sans STOP" 字面量摘掉，再匹配致命关键字（否则裸 "STOP" 必中）
            scanned = LOG_INFO_STOP_LITERAL.sub("INFO_NO_HALT", text)
            fatal = [p for p in LOG_FATAL_PATTERNS if re.search(re.escape(p), scanned, re.IGNORECASE)]
            flags = [p for p in LOG_FP_FLAG_PATTERNS if re.search(re.escape(p), text, re.IGNORECASE)]
        report["log_keywords"][scheme] = fatal + flags
        report.setdefault("log_fp_flags", {})[scheme] = flags
        if fatal:
            findings.append(f"{scheme} 日志含致命关键字：{', '.join(fatal)}")
            hard_failure = True
        elif flags:
            # 只报信号、不判失败：浮点标志本身不代表数值错了
            findings.append(f"{scheme} 浮点标志（非崩溃，程序继续）：{', '.join(flags)}")

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
