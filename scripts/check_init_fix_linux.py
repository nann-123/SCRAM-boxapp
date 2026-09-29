#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""0929 内核初始化修复：Linux 上的自动判定。

跑（或读）7 个 case，核对 docs/0929linux.md §5 的断言 A1–A6，打印 PASS/FAIL，
并把逐条结果写进 `<runs>/result.json`。可选附 A5（改前/改后逐位回归）与 A7（零质量记录项）。

用法（仓库根目录）：
  python scripts/check_init_fix_linux.py                 # 生成配置 → 跑 → 判定
  python scripts/check_init_fix_linux.py --no-run        # 只判读已有 <runs>/<case>/RESULT
  python scripts/check_init_fix_linux.py --pre /tmp/ProgramSCRAM.pre --post /tmp/ProgramSCRAM.post
  python scripts/check_init_fix_linux.py --zero-mass     # 附 A7（只记录，不参与判定）

退出码：0 = 全部通过；1 = 有断言失败；2 = 环境不可用（无核 / 无配置）。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RTOL_EXACT = 1.0e-12      # 初值口径的相等判据
RTOL_REGRESS = 1.0e-15    # A5 零回归：同机同模式，未改动路径应逐位一致

CASES = [
    "T1_nl5_nf1", "T2_nl5_ext_tagext0", "T3_nl5_ext_tagext1",
    "T4_nl1_ext_tagext1", "T5_nl1_ext_tagext0_ti0", "T6_nl1_ext_tagext0_ti1",
    "T7_nl1_nf1_ti0",
]
NL5_ARMS = ["T1_nl5_nf1", "T2_nl5_ext_tagext0", "T3_nl5_ext_tagext1"]
REGRESS_CASES = ["T4_nl1_ext_tagext1", "T6_nl1_ext_tagext0_ti1"]
ZERO_MASS_CASES = ["T8_zero_mass_int", "T9_zero_mass_ext"]

# 改动前（1.1 发行核）实测值，仅用于人工对照，不参与判定
PRE_FIX_REFERENCE = {
    "T1_nl5_nf1": 37.679073599845388,
    "T2_nl5_ext_tagext0": 228.81807486240999,
    "T3_nl5_ext_tagext1": 226.07444159907240,   # = 6 × T1
    "T4_nl1_ext_tagext1": 21.583170063260344,
    "T5_nl1_ext_tagext0_ti0": 14.464046851670814,   # 第 5 族质量被覆盖 → 比 T7 少 4.2647
    "T6_nl1_ext_tagext0_ti1": 21.583170063260344,
    "T7_nl1_nf1_ti0": 18.728707753710463,
}

ERROR_PATTERNS = [
    (r"SCRAM1\.2:", "核心自报错"),
    (r"ERROR STOP", "error stop"),
    (r"orphan", "异常格体检"),
    (r"nonfinite", "非有限值体检"),
    (r"non conservation", "数量不守恒"),
    (r"SIGSEGV|segmentation", "段错误"),
    (r"NaN", "NaN"),
]


def _numbers(line: str) -> list[float] | None:
    """整行都是数字则返回浮点列表，否则 None（兼容逗号分隔）。"""
    out = []
    for token in line.replace(",", " ").split():
        try:
            out.append(float(token))
        except ValueError:
            return None
    return out


def parse_report(path: Path) -> dict:
    """取初始总质量与逐物种气溶胶质量。"""
    info: dict = {"total_mass": None, "species": {}, "exists": path.exists()}
    if not path.exists():
        return info
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "initial total mass" in line:
                values = _numbers(line.replace("initial total mass", " "))
                if values and info["total_mass"] is None:
                    info["total_mass"] = values[-1]
                continue
            values = _numbers(line)
            if values and len(values) == 5 and float(values[0]).is_integer() and 1 <= values[0] <= 40:
                info["species"][int(values[0])] = values[2]
    return info


def parse_mass_init(path: Path) -> list[float] | None:
    """每行最后一列 = 该粒径档的总质量；返回逐档列表。"""
    if not path.exists():
        return None
    bins = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            values = _numbers(line)
            if values:
                bins.append(values[-1])
    return bins


def scan_log(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return [f"{label}: {pattern}" for pattern, label in ERROR_PATTERNS if re.search(pattern, text)]


def rel_diff(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1.0e-300)
    return abs(a - b) / scale


def run_case(name: str, cfg: Path, runtime_dir: Path, run_dir: Path, binary: Path | None,
             timeout: float) -> dict:
    """把运行时目录复制成独立运行目录后跑一次（避免污染共享运行时）。"""
    if run_dir.exists():
        shutil.rmtree(run_dir)
    shutil.copytree(runtime_dir, run_dir)
    (run_dir / "RESULT").mkdir(exist_ok=True)
    exe = run_dir / _exe_name(runtime_dir)
    if binary:
        shutil.copy2(binary, exe)
    log_path = run_dir / "run.log"
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        try:
            proc = subprocess.run([str(exe), str(cfg.resolve())], cwd=str(run_dir),
                                  stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            exit_code = -1
            log.write("\n[checker] 超时被中止\n")
    return {"exit_code": exit_code}


def _exe_name(runtime_dir: Path) -> str:
    return "ProgramSCRAM.exe" if "windows" in runtime_dir.name else "ProgramSCRAM"


def collect(run_dir: Path) -> dict:
    report = parse_report(run_dir / "RESULT" / "report.txt")
    return {
        "total_mass": report["total_mass"],
        "species": report["species"],
        "mass_init_bins": parse_mass_init(run_dir / "RESULT" / "mass_init.txt"),
        "errors": scan_log(run_dir / "run.log"),
        "exit_code": None,
    }


def _fmt(value) -> str:
    return "—" if value is None else "%.10g" % value


def assertions(data: dict[str, dict]) -> list[dict]:
    out: list[dict] = []

    def add(ident: str, ok: bool, detail: str):
        out.append({"id": ident, "ok": bool(ok), "detail": detail})

    # A1 三臂初始总质量相等
    arms = [(name, data[name]["total_mass"]) for name in NL5_ARMS]
    if any(value is None for _, value in arms):
        add("A1", False, "有臂没有 report.txt / 没有初始总质量：" +
            ", ".join(f"{n}={_fmt(v)}" for n, v in arms))
    else:
        base = arms[0][1]
        worst = max(rel_diff(base, value) for _, value in arms)
        add("A1", worst <= RTOL_EXACT,
            "总量 " + ", ".join(f"{n}={_fmt(v)}" for n, v in arms) + f"；最大相对差 {worst:.3g}")

    # A2 逐粒径档总质量相等
    ref = data[NL5_ARMS[0]]["mass_init_bins"]
    if not ref:
        add("A2", False, "内混臂缺少 RESULT/mass_init.txt")
    else:
        bad = []
        for name in NL5_ARMS[1:]:
            bins = data[name]["mass_init_bins"]
            if not bins or len(bins) != len(ref):
                bad.append(f"{name}: 档数 {len(bins) if bins else '—'}≠{len(ref)}")
                continue
            worst = max(rel_diff(a, b) for a, b in zip(ref, bins))
            if worst > RTOL_EXACT:
                bad.append(f"{name}: 最大相对差 {worst:.3g}")
        add("A2", not bad, f"逐档比较（基准 {NL5_ARMS[0]}）；" + ("；".join(bad) if bad else "全部一致"))

    # A3 逐物种（黑碳=2、硫酸盐=4）
    problems = []
    for species in (2, 4):
        values = [(name, data[name]["species"].get(species)) for name in NL5_ARMS]
        if any(value is None for _, value in values):
            problems.append(f"物种 {species} 缺失：" + ", ".join(f"{n}={_fmt(v)}" for n, v in values))
            continue
        base = values[0][1]
        worst = max(rel_diff(base, value) for _, value in values)
        if worst > RTOL_EXACT:
            problems.append(f"物种 {species} 三臂不一致（最大相对差 {worst:.3g}）："
                            + ", ".join(f"{n}={_fmt(v)}" for n, v in values))
        total = data[NL5_ARMS[0]]["total_mass"]
        if total:
            ratio = base / total
            if rel_diff(ratio, 0.5) > 1.0e-9:
                problems.append(f"物种 {species} 不占总量的 1/2（实测 {ratio:.6f}）")
    add("A3", not problems, "；".join(problems) if problems else "黑碳与硫酸盐三臂一致且各占总量一半")

    # A4 无错误停机：全部 case 都扫日志；退出码除 T7（已知可能极慢/异常退出，只作观察）外都要求 0
    assert_cases = [name for name in CASES if name != "T7_nl1_nf1_ti0"]
    problems = []
    unknown = []
    for name in CASES:
        if data[name]["errors"]:
            problems.append(f"{name}: " + "; ".join(data[name]["errors"]))
    for name in assert_cases:
        code = data[name]["exit_code"]
        if code is None:
            unknown.append(name)
        elif code != 0:
            problems.append(f"{name}: 退出码 {code}")
    detail = ("；".join(problems) if problems
              else f"已扫 {len(CASES)} 份 run.log，无报错；除 T7（只作观察）外退出码均为 0")
    if unknown and not problems:
        detail = (f"已扫 {len(CASES)} 份 run.log，无报错"
                  f"（注：--no-run 模式未采集退出码，已跑模式下会一并检查：{', '.join(unknown)}）")
    add("A4", not problems, detail)

    # A6 隐患路：修复后应与内混对照臂一致
    t5, t7 = data["T5_nl1_ext_tagext0_ti0"], data["T7_nl1_nf1_ti0"]
    if t5["total_mass"] is None or t7["total_mass"] is None:
        add("A6", False, "缺少 T5 或 T7 的 report.txt")
    else:
        diff = t5["total_mass"] - t7["total_mass"]
        detail = (f"T5={_fmt(t5['total_mass'])}，T7={_fmt(t7['total_mass'])}，差 {diff:.6g}")
        lost = [f"物种 {s}: T5={_fmt(t5['species'].get(s))} T7={_fmt(t7['species'].get(s))}"
                for s in sorted(set(t5["species"]) | set(t7["species"]))
                if abs(t5["species"].get(s, 0.0) - t7["species"].get(s, 0.0)) > 1.0e-9]
        if lost:
            detail += "；差异物种：" + "；".join(lost[:5])
        add("A6", rel_diff(t5["total_mass"], t7["total_mass"]) <= RTOL_EXACT, detail)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="0929 内核初始化修复的自动判定")
    parser.add_argument("--cases-dir", default=str(ROOT / "install_logs" / "20260929_init_cases"))
    parser.add_argument("--runs-dir", default=str(ROOT / "install_logs" / "20260929_runs"))
    parser.add_argument("--runtime-dir",
                        default=str(ROOT / "core" / "executables_or_wrappers" / "runtime" / "linux"))
    parser.add_argument("--no-run", action="store_true", help="不跑，只判读已有 runs 目录")
    parser.add_argument("--hours", type=float, default=1.0, help="生成配置用的模拟时长（默认 1 h）")
    parser.add_argument("--n-frac", type=int, default=3, help="外混臂组成档段数")
    parser.add_argument("--zero-mass", action="store_true", help="附 A7 零质量记录项")
    parser.add_argument("--pre", help="改动前的核（A5 用）")
    parser.add_argument("--post", help="改动后的核（A5 用）")
    parser.add_argument("--timeout", type=float, default=1800.0, help="单 case 超时秒数")
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir).resolve()
    runs_dir = Path(args.runs_dir).resolve()
    runtime_dir = Path(args.runtime_dir).resolve()
    cases = list(CASES) + (ZERO_MASS_CASES if args.zero_mass else [])

    if not args.no_run:
        generator = ROOT / "scripts" / "make_init_test_cases.py"
        cmd = [sys.executable, str(generator), "--out", str(cases_dir),
               "--hours", str(args.hours), "--n-frac", str(args.n_frac)]
        if args.zero_mass:
            cmd.append("--zero-mass")
        print("生成测试配置：", " ".join(cmd[1:]))
        subprocess.run(cmd, check=True)
        if not runtime_dir.exists():
            print(f"找不到运行时目录 {runtime_dir}；先跑 bash scripts/linux/build_runtime.sh safe", file=sys.stderr)
            return 2
        missing = [name for name in cases if not (cases_dir / f"{name}.cfg").exists()]
        if missing:
            print(f"缺少配置：{missing}", file=sys.stderr)
            return 2

    data: dict[str, dict] = {}
    for name in cases:
        run_dir = runs_dir / name
        if not args.no_run:
            result = run_case(name, cases_dir / f"{name}.cfg", runtime_dir, run_dir, None, args.timeout)
        else:
            result = {"exit_code": None}
        entry = collect(run_dir)
        entry["exit_code"] = result["exit_code"]
        data[name] = entry
        print(f"  {name:<26} 初始总质量 {_fmt(entry['total_mass']):<20} 退出码 {result['exit_code']}")

    results = assertions(data)

    if args.pre and args.post:
        problems = []
        for name in REGRESS_CASES:
            if not (cases_dir / f"{name}.cfg").exists():
                problems.append(f"{name}: 缺配置")
                continue
            for tag, binary in (("pre", args.pre), ("post", args.post)):
                run_dir = runs_dir / f"{name}__{tag}"
                run_case(name, cases_dir / f"{name}.cfg", runtime_dir, run_dir, Path(binary), args.timeout)
                data[f"{name}__{tag}"] = collect(run_dir)
            pre, post = data[f"{name}__pre"], data[f"{name}__post"]
            if pre["total_mass"] is None or post["total_mass"] is None:
                problems.append(f"{name}: 缺 report.txt")
                continue
            worst = rel_diff(pre["total_mass"], post["total_mass"])
            bins_worst = 0.0
            if pre["mass_init_bins"] and post["mass_init_bins"]:
                bins_worst = max(rel_diff(a, b) for a, b in zip(pre["mass_init_bins"], post["mass_init_bins"]))
            if max(worst, bins_worst) > RTOL_REGRESS:
                problems.append(f"{name}: 总量相对差 {worst:.3g}、逐档最大相对差 {bins_worst:.3g}")
        results.append({"id": "A5", "ok": not problems,
                        "detail": "；".join(problems) if problems else
                                  "T4/T6 在改前/改后两版核上逐位一致"})

    if args.zero_mass:
        notes = []
        for name in ZERO_MASS_CASES:
            entry = data[name]
            notes.append(f"{name}: 退出码 {entry['exit_code']}，"
                         f"总质量 {_fmt(entry['total_mass'])}，报错 {entry['errors'] or '无'}")
        results.append({"id": "A7", "ok": True,
                        "detail": "（记录项，不参与判定）" + "；".join(notes)})

    print("")
    for item in results:
        print("[%s] %-3s %s" % ("PASS" if item["ok"] else "FAIL", item["id"], item["detail"]))
    print("")
    print("改动前（1.1 发行核）实测参照：" +
          "，".join(f"{n}={value:.6g}" for n, value in PRE_FIX_REFERENCE.items()))
    print("（T3/T1 应为 6.0000；T2 为叠加了配置质量的垃圾初值；T5 比 T7 少 4.2647）")

    runs_dir.mkdir(parents=True, exist_ok=True)
    payload = {"assertions": results, "cases": data, "reference_pre_fix": PRE_FIX_REFERENCE}
    (runs_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print(f"\n明细已写入 {runs_dir / 'result.json'}")
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
