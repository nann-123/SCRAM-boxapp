#!/usr/bin/env python3
"""P4 移植保真度检查：同一 cfg 跑本体 exe 与仓库 exe，比总质量/气溶胶质量。

这是"Windows 化"的核心验收指标（release gate 之一）：
  - 总质量必须逐位一致（bit-identical）
  - 气溶胶质量相对差 <= 1e-5（gate 阈值，不得放宽）

用法：
  .venv/bin/python scripts/linux/fidelity_check.py [--out DIR] [--cfg PATH]
      [--upstream-exe PATH] [--repo-exe PATH] [--coef PATH] [--timeout 900]

默认：
  - cfg      = 本体规范 cfg（~/SCRAM1.1/INIT/cfg_megapole_01072009.cfg，即手工跑出
               总质量 36.489297208418 的那份），保证两个 exe 用**同一份** cfg
  - upstream = ~/SCRAM1.1/ProgramSCRAM
  - repo     = <ROOT>/core/executables_or_wrappers/runtime/linux/ProgramSCRAM
  - coef     = ~/SCRAM1.1/coef_s5_f3_b7.nc

退出码恒为 0（信息性，不破坏轮次）；gate 是否达标写在 report.json 的 gate_pass。
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE_AERO_REL = 1e-5  # release gate 阈值（不得放宽）


def parse_run_log(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    heads = [m.start() for m in re.finditer(
        r"jesp\s+concentration_gas\s+total_aero_mass\s+total_mass", txt)]
    if len(heads) < 2:
        raise RuntimeError(f"final table header not found in {path}")
    block = txt[heads[1]:]
    m = re.search(r"Nub Nucl", block)
    block = block[:m.start()] if m else block
    aero = tot = gas = 0.0
    rows = 0
    for line in block.splitlines():
        f = line.split()
        if len(f) >= 4 and f[0].isdigit():
            try:
                g, a, t = float(f[1]), float(f[2]), float(f[3])
            except ValueError:
                continue
            aero += a; tot += t; gas += g; rows += 1
    def grab(pat):
        mm = re.search(pat, txt)
        return float(mm.group(1)) if mm else None
    return dict(aero=aero, tot=tot, gas=gas, rows=rows,
                masscond=grab(r"Mass Cond\s+([0-9.eE+-]+)"),
                init=grab(r"inital total mass\s+([0-9.eE+-]+)"),
                water=grab(r"total_water\s+([0-9.eE+-]+)"),
                nubnucl=grab(r"Nub Nucl\s+([0-9.eE+-]+)"),
                nubcoag=grab(r"Nub Coag\s+([0-9.eE+-]+)"))


def run_exe(exe: Path, cfg: Path, workdir: Path, timeout: int) -> dict:
    (workdir / "RESULT").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["SCRAM_RESULTS_DIR"] = str(workdir / "RESULT")
    t0 = time.time()
    p = subprocess.run([str(exe), cfg.name], cwd=workdir, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    log = workdir / "run.log"
    log.write_bytes(p.stdout)
    return dict(exit=p.returncode, elapsed=round(time.time() - t0, 2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "install_logs/auto/fidelity_check"))
    ap.add_argument("--cfg", default=os.path.expanduser("~/SCRAM1.1/INIT/cfg_megapole_01072009.cfg"))
    ap.add_argument("--upstream-exe", default=os.path.expanduser("~/SCRAM1.1/ProgramSCRAM"))
    ap.add_argument("--repo-exe", default=str(ROOT / "core/executables_or_wrappers/runtime/linux/ProgramSCRAM"))
    ap.add_argument("--coef", default=os.path.expanduser("~/SCRAM1.1/coef_s5_f3_b7.nc"))
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(a.out) / stamp
    up = out / "upstream"; rp = out / "repo"
    for d in (up, rp):
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy(a.cfg, d / Path(a.cfg).name)
        shutil.copy(a.coef, d / Path(a.coef).name)
        # INIT 目录（file_conc_* 等）
        init_src = Path(a.cfg).parent
        if init_src.is_dir():
            shutil.copytree(init_src, d / "INIT", dirs_exist_ok=True)

    cfg_name = Path(a.cfg).name
    up_meta = run_exe(Path(a.upstream_exe), Path(a.cfg), up, a.timeout)
    rp_meta = run_exe(Path(a.repo_exe), Path(a.cfg), rp, a.timeout)

    up_log = up / "run.log"; rp_log = rp / "run.log"
    up_m = parse_run_log(up_log) if up_log.exists() else None
    rp_m = parse_run_log(rp_log) if rp_log.exists() else None

    def rel(x, y):
        return abs(x - y) / abs(y) if y else float("nan")

    report = {
        "stamp": stamp,
        "cfg": a.cfg,
        "upstream_exe": a.upstream_exe,
        "repo_exe": a.repo_exe,
        "upstream": {**up_meta, **(up_m or {})},
        "repo": {**rp_meta, **(rp_m or {})},
    }
    if up_m and rp_m:
        report["metrics"] = {
            "total_mass_bit_identical": up_m["tot"] == rp_m["tot"],
            "total_mass_upstream": up_m["tot"],
            "total_mass_repo": rp_m["tot"],
            "aero_rel_diff": rel(rp_m["aero"], up_m["aero"]),
            "aero_upstream": up_m["aero"],
            "aero_repo": rp_m["aero"],
            "gas_rel_diff": rel(rp_m["gas"], up_m["gas"]),
            "masscond_rel_diff": rel(rp_m["masscond"], up_m["masscond"]),
            "water_rel_diff": rel(rp_m["water"], up_m["water"]),
        }
        report["gate_pass"] = (up_m["tot"] == rp_m["tot"]) and (rel(rp_m["aero"], up_m["aero"]) <= GATE_AERO_REL)
        report["gate_threshold_aero_rel"] = GATE_AERO_REL

    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    # markdown 摘要
    lines = [f"# 移植保真度检查 {stamp}", "",
             f"- cfg: `{a.cfg}`",
             f"- upstream exe: `{a.upstream_exe}`",
             f"- repo exe: `{a.repo_exe}`", ""]
    if "metrics" in report:
        m = report["metrics"]
        lines += [
            f"- 总质量逐位一致: **{'是' if m['total_mass_bit_identical'] else '否'}** "
            f"(upstream={m['total_mass_upstream']:.16g}, repo={m['total_mass_repo']:.16g})",
            f"- 气溶胶质量相对差: **{m['aero_rel_diff']:.3e}** (gate ≤ {GATE_AERO_REL:.0e})",
            f"- 气溶胶质量: upstream={m['aero_upstream']:.16g}, repo={m['aero_repo']:.16g}",
            f"- 气相质量相对差: {m['gas_rel_diff']:.3e}",
            f"- Mass Cond 相对差: {m['masscond_rel_diff']:.3e}",
            f"- total_water 相对差: {m['water_rel_diff']:.3e}",
            f"- **gate_pass: {report['gate_pass']}**",
        ]
    else:
        lines.append(f"- 解析失败：upstream exit={up_meta.get('exit')}, repo exit={rp_meta.get('exit')}")
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
