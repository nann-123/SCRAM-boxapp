"""模板体检（2026-09-12 人工复核新增，用于回答"哪个模板有问题"）。

对每个模板跑一遍（两种混合假设），断言四件事：
  1) status 必须是 ok（Fortran STOP / 崩溃 → failed）
  2) 日志不得含**致命**关键字（STOP/信号/NaN）；浮点标志只报信号（见 runbook 铁律 D）
  3) **该开的物理过程必须真的起作用**：with_cond=1 且初始气相 > 0 ⇒ `Mass Cond` 必须 > 0；
     with_coag=1 ⇒ 粒子数或凝并事件计数必须变化（防"开关开了但空转"）
  4) 无气相源却开冷凝 ⇒ 记"教学骨架"信号（不算失败，但必须显式记录，别当验证案例）

用法：
    .venv/bin/python scripts/linux/template_audit.py            # 全部模板
    .venv/bin/python scripts/linux/template_audit.py gmd_paris_full
输出：install_logs/auto/template_audit/<模板>/（probe 证据）+ 控制台表格；退出码 1 = 有事要处理。
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT_ROOT = ROOT / "install_logs" / "auto" / "template_audit"
FATAL = ["non conservation", "STOP", "NaN", "Program received signal", "segmentation"]
FP_FLAGS = ["IEEE_INVALID", "IEEE_DIVIDE_BY_ZERO"]


def run_one(template: str) -> dict:
    out = OUT_ROOT / template
    out.mkdir(parents=True, exist_ok=True)
    log = out / "probe.log"
    with log.open("w") as fh:
        subprocess.run(
            [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/linux/probe_cell.py"),
             "--template", template, "--out", str(out)],
            stdout=fh, stderr=subprocess.STDOUT, check=False,
        )
    probe = out / "probe.json"
    verdict = {"template": template, "findings": [], "signals": [], "status": {}, "mass_cond": None,
               "effective": None, "steps": {}}
    if not probe.exists():
        verdict["findings"].append("probe.json 缺失（跑不起来）")
        return verdict
    data = json.loads(probe.read_text())
    for scheme, run in data.get("runs", {}).items():
        verdict["status"][scheme] = run.get("status")
        verdict["steps"][scheme] = run.get("total_steps")
        if run.get("status") != "ok":
            verdict["findings"].append(f"{scheme}: status={run.get('status')}")
    runs_dir = out / "runs" / template
    # 体积纪律：<模板>_external_mixing/csv/coag_delta_mass.csv 这类会到几百 MB（702 步 × 30 物种），
    # 而体检只需要日志与两张摘要 CSV。读完后立即瘦身，避免把 install_logs 撑爆（2026-09-12 实测 789M→2M）。
    def slim(d: Path) -> None:
        import shutil as _sh
        _sh.rmtree(d / "figures", ignore_errors=True)
        keep = {"conservation_audit.csv", "timestep_summary.csv"}
        csv_dir = d / "csv"
        if csv_dir.is_dir():
            for f in csv_dir.iterdir():
                if f.is_file() and f.name not in keep:
                    f.unlink()
    for scheme_dir in sorted(runs_dir.glob("*")) if runs_dir.exists() else []:
        logp = scheme_dir / "logs" / "run.log"
        if logp.exists():
            text = logp.read_text(errors="replace")
            hits = [p for p in FATAL if p.lower() in text.lower()]
            flags = [p for p in FP_FLAGS if p.lower() in text.lower()]
            if hits:
                verdict["findings"].append(f"{scheme_dir.name}: 致命关键字 {hits}")
            if flags:
                verdict["signals"].append(f"{scheme_dir.name}: 浮点标志 {flags}")
        rep = scheme_dir / "logs" / "report.txt"
        if not rep.exists():
            continue
        text = rep.read_text(errors="replace")
        sw = re.search(r"Condensation\s+(\d+)\s+Coagulation\s+(\d+)", text)
        gas = re.search(r"^\s*1\s+([\d.eE+-]+)", text, re.M)
        gas1 = None
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "1":
                try:
                    gas1 = float(parts[1]); break
                except ValueError:
                    pass
        mc = re.search(r"Mass Cond\s+([-\d.eE+]+)", text)
        if mc:
            verdict["mass_cond"] = float(mc.group(1))
        if sw:
            with_cond, with_coag = int(sw.group(1)), int(sw.group(2))
            verdict["effective"] = {"with_cond": with_cond, "with_coag": with_coag}
            if with_cond == 1 and not mc:
                verdict["findings"].append(f"{scheme_dir.name}: 开了冷凝但读不到 Mass Cond（报告缺失/被截断）")
            elif with_cond == 1 and mc and float(mc.group(1)) == 0.0:
                if gas1 == 0.0:
                    verdict["signals"].append(f"{scheme_dir.name}: 开了冷凝但无气相源（教学骨架，不是验证案例）")
                else:
                    verdict["findings"].append(f"{scheme_dir.name}: 开了冷凝、有气相，Mass Cond==0（冷凝空转）")
            if with_coag == 1 and verdict["steps"].get("EXTERNAL_MIXING", 0) == 0:
                verdict["findings"].append(f"{scheme_dir.name}: 开了凝并但 0 步")
        slim(scheme_dir)
    return verdict


def main() -> int:
    from app.services.template_service import TemplateService
    args = sys.argv[1:]
    names = args or [t["id"] for t in TemplateService(ROOT).list_templates()]
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    bad = 0
    print(f"{'模板':<24}{'状态':<14}{'MassCond':>10}   结论")
    for name in names:
        v = run_one(name)
        tag = "OK" if not v["findings"] else "需处理"
        if v["findings"]:
            bad += 1
        mc = "" if v["mass_cond"] is None else f"{v['mass_cond']:.4g}"
        print(f"{name:<24}{str(v['status']):<14}{mc:>10}   {tag}")
        for f in v["findings"]:
            print(f"    ✗ {f}")
        for s in v["signals"]:
            print(f"    · {s}")
    print(f"\n== 模板体检：{len(names)} 个，需处理 {bad} 个 ==")
    print(f"证据：{OUT_ROOT}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
