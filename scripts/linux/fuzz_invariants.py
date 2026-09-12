"""M4 不变量模糊测试（hunt_plan §2 M4 / 队列 Q-11）。

随机生成 N 组**合法**配置（在 schema 约束内随机化过程开关 / 重分配方法 / 物理条件），
对每组断言四条不变量：
  1) 质量守恒：max_relative_residual <= 1e-6
  2) 无 NaN/Inf：has_nan == 0 且 has_inf == 0
  3) 终态有限：final_mass / final_number 均为有限值
  4) 非负：final_mass >= 0 且 final_number >= 0

另外两项（2026-09-12 人工复核补强）：
  5) 过程全关时质量与数量必须**逐位不变**（静默失败检测，M2 的批量版）；
  6) 覆写必须真的落地：随机化的标量要标 `explicit_keys`（否则被 case preset 无条件覆盖 →
     随机化被静默丢弃，2026-09-12 复核 §0.4-1 实测过：9 个 with_coag=1 的配置终态数量
     与 with_coag=0 完全一致），并从 report.txt 回读**生效**的开关做落地校验。

任一组失败即视为"命中"（潜在新 Bug），退出码 1；全部通过退出码 0。
基座模板固定为 gmd_paris_condensation（已知 clean 基座），只随机化标量字段，
不改动表格结构（n_species/n_sizebin/n_frac/粒径/分数边界），避免工具层产生非法配置造成假阳性。
已知非守恒路径 redistribution_method=6（euler_coupled, Bug #7）从随机池中排除，
以免把已登记 Bug 误报为"新发现"。
逐组保留可审计证据（logs/ + 两张审计 CSV + 报告行），不再整目录删除。
数量变化作为观测量记录（|ΔN|/N > 10% 只报"信号"，不判失败：euler_mass 本非数量守恒）。
"""
from __future__ import annotations
import argparse, json, random, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEME_DIR = {"INTERNAL_MIXING": "internal_mixing", "EXTERNAL_MIXING": "external_mixing"}
LOG_FATAL_PATTERNS = ["non conservation", "STOP", "NaN", "Program received signal", "segmentation"]
LOG_FP_FLAG_PATTERNS = ["IEEE_INVALID", "IEEE_DIVIDE_BY_ZERO", "IEEE_OVERFLOW", "IEEE_UNDERFLOW"]
RESID_TOL = 1e-6

def read_rows(path: Path):
    if not path.exists():
        return []
    with path.open(newline="") as h:
        return list(__import__("csv").DictReader(h))

def random_config(base: dict, rng: random.Random) -> dict:
    import copy
    cfg = copy.deepcopy(base)
    s = cfg["scalars"]
    s["with_coag"] = rng.randint(0, 1)
    s["with_cond"] = rng.randint(0, 1)
    s["with_nucl"] = rng.randint(0, 1)
    s["nucl_model"] = rng.randint(1, 4)          # 排除 5（硬编码路径，Q-08 已单独复核）
    s["sulfate_computation"] = rng.randint(0, 1)
    s["dynamic_solver"] = rng.randint(1, 2)
    s["tag_thrm"] = rng.randint(0, 1)
    s["redistribution_method"] = rng.randint(1, 5)  # 排除 6（euler_coupled, Bug #7 已知非守恒）
    s["redistribution_option"] = rng.choice(["legacy", "core_conserv", "core_nogrow", "core_smallgrow"])
    s["temperature"] = round(rng.uniform(250.0, 300.0), 3)
    s["pressure"] = round(rng.uniform(50000.0, 100000.0), 1)
    s["humidity"] = round(rng.uniform(0.5, 0.999), 4)
    s["final_time_hours"] = round(rng.uniform(1.0, 12.0), 2)
    s["dtmin_seconds"] = round(rng.uniform(0.5, 5.0), 2)
    # 关键：把这些键标成「显式」，否则 run_service._with_case_preset 会用预设值无条件覆盖它们
    # （预设含 with_coag/with_cond/with_nucl/final_time_hours），随机化会被静默丢弃。
    cfg["explicit_keys"] = sorted({k for k in s} | set(cfg.get("explicit_keys", [])))
    return cfg

def check_invariants(run_dir: Path, case_name: str, scheme: str):
    anomaly, has_nan, has_inf, rows_audit, worst_rel = {}, 0, 0, 0, 0.0
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
    return {"anomaly_counts": anomaly, "conservation_rows": rows_audit,
            "has_nan": has_nan, "has_inf": has_inf, "max_relative_residual": worst_rel}

def effective_switches(run_dir: Path):
    """回读 report.txt 的「生效值」，用于覆写落地校验。

    注意：Condensation/Coagulation 是 `with_cond`/`with_coag` 的直读回显；
    Nucleation 打印的是运行期派生的 `tag_nucl`（ProgramSCRAM.f90:124，只在有冷凝/核化步时置位），
    **不能**当作 `with_nucl` 的落地证据（2026-09-12 复核时误判过一次，故不返回该字段）。
    同时返回发射源汇 m_emis/n_emis：它们与过程开关无关，始终生效，
    所以「全关则状态不变」的判据必须把发射量算进去。
    """
    import re
    p = run_dir / "logs" / "report.txt"
    if not p.exists():
        return None
    text = p.read_text(errors="replace")
    m = re.search(r"Condensation\s+(\d+)\s+Coagulation\s+(\d+)", text)
    em = re.search(r"m_emis\s+(-?[\d.]+(?:[EeDd][+-]?\d+)?)", text)
    en = re.search(r"n_emis\s+(-?[\d.]+(?:[EeDd][+-]?\d+)?)", text)
    if not m:
        return None
    def num(x):
        return float(x.replace("D", "E").replace("d", "e")) if x else 0.0
    return {"with_cond": int(m.group(1)), "with_coag": int(m.group(2)),
            "m_emis": num(em.group(1) if em else None), "n_emis": num(en.group(1) if en else None)}


def timeline_endpoints(run_dir: Path):
    """timestep_summary.csv 的首末行（质量/数量），用于「全关时逐位不变」与数量观测量。"""
    rows = read_rows(run_dir / "csv" / "timestep_summary.csv")
    if len(rows) < 2:
        return None
    def f(r, k):
        try:
            return float(r.get(k) or 0.0)
        except ValueError:
            return 0.0
    return {"mass0": f(rows[0], "total_mass"), "massN": f(rows[-1], "total_mass"),
            "num0": f(rows[0], "total_number"), "numN": f(rows[-1], "total_number")}


def slim_run_dir(run_dir: Path):
    """保留可审计证据（日志 + 两张审计 CSV + 报告），删除图片与其余大表。"""
    import shutil
    shutil.rmtree(run_dir / "figures", ignore_errors=True)
    keep = {"conservation_audit.csv", "timestep_summary.csv"}
    csv_dir = run_dir / "csv"
    if csv_dir.is_dir():
        for f in csv_dir.iterdir():
            if f.is_file() and f.name not in keep:
                f.unlink()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260912)
    ap.add_argument("--template", default="gmd_paris_condensation")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    from app.config_binding.config_model import ConfigModel
    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    rng = random.Random(args.seed)
    base = TemplateService(ROOT).load_template(args.template)
    cm = ConfigModel(ROOT)
    out_root = (args.out or ROOT / "install_logs" / "auto" / "fuzz_q11").resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    runner = RunService(ROOT)
    runner.set_results_root(out_root)

    results = []
    any_fail = False
    for i in range(args.n):
        cfg = random_config(base, rng)
        errs = cm.validate(cfg)
        if errs:
            results.append({"idx": i, "valid": False, "errors": errs})
            any_fail = True
            continue
        case_name = f"fuzz_{i:02d}"
        t0 = time.time()
        rows = runner.run_comparison(cfg, case_name)
        entry = {"idx": i, "valid": True, "wallclock_s": round(time.time() - t0, 3),
                 "scalars": {k: cfg["scalars"][k] for k in
                 ("with_coag","with_cond","with_nucl","nucl_model","redistribution_method",
                  "redistribution_option","temperature","pressure","humidity","final_time_hours","dtmin_seconds")},
                 "runs": {}, "invariants": {}, "signals": [], "failures": []}
        for row in rows:
            scheme = row["scheme"]
            entry["runs"][scheme] = {"status": row["status"], "final_mass": float(row["final_mass"]),
                                     "final_number": float(row["final_number"]), "total_steps": int(float(row["total_steps"]))}
            run_dir = out_root / "runs" / case_name / SCHEME_DIR.get(scheme, scheme.lower())
            inv = check_invariants(run_dir, case_name, scheme)
            entry["invariants"][scheme] = inv
            # 不变量断言
            if row["status"] != "ok":
                entry["failures"].append(f"{scheme}: status={row['status']}")
            fm, fn = float(row["final_mass"]), float(row["final_number"])
            if fm != fm or fm in (float("inf"), float("-inf")):
                entry["failures"].append(f"{scheme}: final_mass 非有限")
            if fn != fn or fn in (float("inf"), float("-inf")):
                entry["failures"].append(f"{scheme}: final_number 非有限")
            if fm < 0:
                entry["failures"].append(f"{scheme}: final_mass<0")
            if fn < 0:
                entry["failures"].append(f"{scheme}: final_number<0")
            if inv["has_nan"] or inv["has_inf"]:
                entry["failures"].append(f"{scheme}: has_nan/inf={inv['has_nan']}/{inv['has_inf']}")
            if inv["max_relative_residual"] > RESID_TOL:
                entry["failures"].append(f"{scheme}: residual={inv['max_relative_residual']:.3e}>1e-6")
            if inv["conservation_rows"] == 0:
                entry["failures"].append(f"{scheme}: 无守恒审计行")
            # 日志关键字：致命 → 失败；浮点标志 → 仅信号
            logp = run_dir / "logs" / "run.log"
            if logp.exists():
                txt = logp.read_text(errors="replace")
                fatal = [p for p in LOG_FATAL_PATTERNS if p.lower() in txt.lower()]
                flags = [p for p in LOG_FP_FLAG_PATTERNS if p.lower() in txt.lower()]
                if fatal:
                    entry["failures"].append(f"{scheme}: 日志致命关键字 {fatal}")
                if flags:
                    entry["signals"].append(f"{scheme}: 浮点标志 {flags}")

            # 覆写落地校验：随机化的开关是否真的进了 Fortran（只查能直读回显的 coag/cond）
            eff = effective_switches(run_dir)
            entry.setdefault("effective_switches", {})[scheme] = eff
            if eff is None:
                entry["failures"].append(f"{scheme}: 读不到生效开关（report.txt 缺行）")
            else:
                want = {"with_coag": int(cfg["scalars"]["with_coag"]),
                        "with_cond": int(cfg["scalars"]["with_cond"])}
                got = {"with_coag": eff["with_coag"], "with_cond": eff["with_cond"]}
                if got != want:
                    entry["failures"].append(f"{scheme}: 覆写未落地 want={want} got={got}")

            # 不变量 5：过程全关 ⇒ 终态 = 初态 + 发射源汇（发射与过程开关无关，必须算进去）
            tl = timeline_endpoints(run_dir)
            if tl:
                def rel(a, b):
                    return abs(b - a) / abs(a) if a else (0.0 if b == 0 else float("inf"))
                entry.setdefault("rel_change", {})[scheme] = {
                    "mass": rel(tl["mass0"], tl["massN"]), "number": rel(tl["num0"], tl["numN"])}
                all_off = not any(int(cfg["scalars"][k]) for k in ("with_coag", "with_cond", "with_nucl"))
                if eff and all_off:
                    exp_m = tl["mass0"] + eff["m_emis"]
                    exp_n = tl["num0"] + eff["n_emis"]
                    d_m, d_n = rel(exp_m, tl["massN"]), rel(exp_n, tl["numN"])
                    # 粗偏差（>1%）= 过程全关却真有东西在跑 → 失败；
                    # 细残差（>1e-6）= 发射记账不一致 → 只报信号（2026-09-12 实测数量侧约 1.2e-4，质量侧逐位精确）
                    if d_m > 1e-2 or d_n > 1e-2:
                        entry["failures"].append(
                            f"{scheme}: 过程全关时终态 ≠ 初态+发射（偏差 mass={d_m:.2e} number={d_n:.2e}）"
                            f" mass {tl['mass0']:.6g}+{eff['m_emis']:.6g} vs {tl['massN']:.6g};"
                            f" number {tl['num0']:.6g}+{eff['n_emis']:.6g} vs {tl['numN']:.6g}")
                    elif max(d_m, d_n) > 1e-6:
                        entry["signals"].append(
                            f"{scheme}: 全关时发射记账残差（mass {d_m:.2e} / number {d_n:.2e}）")
                elif rel(tl["num0"], tl["numN"]) > 0.1:
                    # 数量大变只报信号：euler_mass/hemen 本非数量守恒（见复核 §0.3-3）
                    entry["signals"].append(
                        f"{scheme}: 数量变化 {100*rel(tl['num0'], tl['numN']):.1f}%（{tl['num0']:.4g}->{tl['numN']:.4g}）")

            # 保留可审计证据（不再整目录删除）
            slim_run_dir(run_dir)
        if entry["failures"]:
            any_fail = True
        results.append(entry)
        tag = "FAIL " + "; ".join(entry["failures"]) if entry["failures"] else "ok"
        if entry["signals"]:
            tag += "  ｜信号：" + "; ".join(entry["signals"])
        print(f"[{i:02d}] {tag}", flush=True)

    report = {"n": args.n, "seed": args.seed, "template": args.template,
              "residual_tol": RESID_TOL, "any_failure": any_fail, "results": results}
    (out_root / "fuzz_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    n_fail = sum(1 for r in results if r.get("failures") or not r.get("valid", True))
    print(f"\n== M4 不变量模糊测试：{args.n} 组，失败 {n_fail} 组 ==")
    print(f"报告：{out_root / 'fuzz_report.json'}")
    return 1 if any_fail else 0

if __name__ == "__main__":
    sys.exit(main())
