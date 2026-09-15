#!/usr/bin/env python
"""绘图正确性自动排查（2026-09-15）。

只读：不写任何运行产物，仅扫描既有的 install_logs 输出目录，把"图上的数"与
"数据源里的数"逐项对账，并把 plot_service.py 里所有无法从数据推出的假设找出来。

判据分三层：
  C 层（结构）：数据完备性、缺数据分支、时间轴/终值与 authoritative CSV 的一致性
  P 层（物理）：t=0 纯外混配置的 mixed fraction 必须为 0（fractions.txt 推出的规则）
  S 层（呈现）：轴标签单位、图里的常量与配置是否一致、异常是否可见、量级守卫

退出码：0 = 全部通过；3 = 仅有已登记项；1 = 出现新问题。
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_INIT = ROOT / "core" / "executables_or_wrappers" / "runtime" / "windows" / "INIT"
PLOT_SERVICE = ROOT / "app" / "services" / "plot_service.py"

# plot_service.py 里硬编码的"未混合"组成档编号（待证伪的对象）
HARDCODED_UNMIXED = {1, 3, 6, 11, 20}

results: list[tuple[str, str, str]] = []  # (层, 级别, 描述)


def add(layer: str, level: str, text: str) -> None:
    results.append((layer, level, text))


def read_rows(path: Path):
    with path.open(encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


# 核心写出的 CSV 里存在畸形的非规格化浮点数：Fortran 列表输出把 1.03e-297 写成
# "1.0332900803284679-297"（丢了指数标记 E）。plot_service.read_csv 直接 float() 会崩，
# 这里容错解析，同时把命中次数记下来作为独立缺陷报告。
BAD_FLOAT = re.compile(r"^([-+]?[0-9]*\.?[0-9]+)([-+][0-9]{2,3})$")
bad_float_hits: list[tuple[str, str]] = []


def safe_float(text: str) -> float:
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        m = BAD_FLOAT.match(text)
        if m:
            bad_float_hits.append((text, f"{m.group(1)}E{m.group(2)}"))
            return float(f"{m.group(1)}E{m.group(2)}")
        raise


# --------------------------------------------------------------------------
# 规则：从 core 配送的 INIT/fractions.txt 推出"哪些组成档是未混合"
# --------------------------------------------------------------------------
def recover_n_frac(path: Path) -> tuple[int, float]:
    """从 fractions.txt 恢复 n_frac。

    区间上下界只可能取 {0, 1/n_frac, 2/n_frac, …, 1}，所以"文件里出现过的最小正下界"
    就是 1/n_frac（例如出现 0.2/0.8 时 n_frac=3）。返回 (n_frac, 该下界)。
    """
    lowers = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 2:
            lowers.add(round(float(parts[0]), 9))
    positives = sorted(v for v in lowers if v > 0)
    if not positives:
        return 1, 1.0
    step = positives[0]
    return max(round(1.0 / step), 1), step


def derive_unmixed_bins(n_groups: int, path: Path) -> tuple[set[int], list[float], int]:
    """按核心的组分离散语义，推出"哪些组成档是未混合"。

    规则：某分组在这一组合里只含单一物种 ⇔ 该分组的质量分数区间不跨过配置里的 fraction 边界，
    且落在**某一个** fraction 格内；单物种分组的粒子占满整段 [0,1]。

    注意：fraction 边界只取 fractions.txt 里出现过的值（本仓库实测是 {0, 0.2, 0.8, 1}，
    对应 baseline12h 的 [0,0.2,0.8,1]，**不是**均匀的 1/n，所以不能按 1/n 的等分推）。
    """
    pairs = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 2:
            pairs.append((round(float(parts[0]), 9), round(float(parts[1]), 9)))
    bounds = sorted({v for pair in pairs for v in pair})
    n_combo = len(pairs) // max(n_groups, 1)
    cells = list(zip(bounds, bounds[1:]))
    unmixed = set()
    for c in range(n_combo):
        groups = pairs[c * n_groups:(c + 1) * n_groups]
        ok = True
        for lo, hi in groups:
            if (lo, hi) in cells:
                continue
            if lo == 0.0 and hi == 1.0:  # 单物种分组：占满整段
                continue
            ok = False
            break
        if ok:
            unmixed.add(c + 1)
    return unmixed, bounds, n_combo


def main() -> int:
    runs: list[Path] = []
    for runs_root in sorted(ROOT.glob("install_logs/**/runs")):
        for case_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            for scheme_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
                if (scheme_dir / "csv").exists() or (scheme_dir / "logs").exists():
                    runs.append(scheme_dir)
    if not runs:
        print("没有找到任何运行产物（install_logs/**/runs/<case>/<scheme>）")
        return 1
    print(f"扫描 {len(runs)} 个 scheme 目录\n")

    # ---------- S1：轴标签单位 ----------
    src = PLOT_SERVICE.read_text(encoding="utf-8")
    # 有量纲的物理量必须在标签里带单位；无量纲量（分数、个数、档号）用 "(-)" 或词组明确即可
    DIMENSIONED = ("mass", "number", "time", "temperature", "pressure", "humidity", "diameter", "wallclock")
    bare_labels = []
    for m in re.finditer(r'plt\.(?:x|y)label\("([^"]*)"\)', src):
        label = m.group(1)
        if re.search(r"[\(\[]", label):
            continue
        if any(word in label.lower() for word in DIMENSIONED):
            bare_labels.append(label)
    if bare_labels:
        add("S", "新问题", f"有量纲轴标签未标单位：{sorted(set(bare_labels))}")

    # ---------- S2：图里的硬编码常量是否与配置一致 ----------
    if "unmixed_bins = {1, 3, 6, 11, 20}" in src or "{1, 3, 6, 11, 20}" in src:
        add("S", "新问题", "plot_service.py 里仍存在硬编码的未混合档集合 {1, 3, 6, 11, 20}（见下 P 层判定）")

    for run in runs:
        case = run.parent.name
        scheme = run.name
        csv_dir = run / "csv"
        if not csv_dir.exists():
            continue

        # ---------- C1：核心产出的数据完备性 ----------
        need = ["timestep_summary.csv", "size_composition_mass.csv",
                "size_composition_number.csv", "conservation_audit.csv", "anomaly_flags.csv"]
        missing = [n for n in need if not (csv_dir / n).exists()]
        if missing:
            add("C", "新问题", f"{case}/{scheme}: 缺 CSV {missing}（绘图会静默跳过或抛异常）")

        # ---------- C2：timestep_summary 与 size_composition 的自洽 ----------
        ts_path = csv_dir / "timestep_summary.csv"
        num_path = csv_dir / "size_composition_number.csv"
        mass_path = csv_dir / "size_composition_mass.csv"
        if ts_path.exists() and num_path.exists():
            ts = read_rows(ts_path)
            per_ts_num = defaultdict(float)
            for r in read_rows(num_path):
                per_ts_num[int(safe_float(r["timestep"]))] += safe_float(r["number"])
            worst = None
            for r in ts:
                t = int(safe_float(r["timestep"]))
                a, b = safe_float(r["total_number"]), per_ts_num.get(t, 0.0)
                if max(abs(a), abs(b), 1e-300) > 0:
                    rel = abs(a - b) / max(abs(a), abs(b), 1e-300)
                    if worst is None or rel > worst[1]:
                        worst = (t, rel, a, b)
            if worst and worst[1] > 1e-9:
                add("C", "新问题",
                    f"{case}/{scheme}: timestep_summary.total_number 与 size_composition_number 求和不一致 "
                    f"(t={worst[0]}, 相对差={worst[1]:.3g})")

        # ---------- C3：相对差图跨臂插值的标架 ----------
        # 两臂步长不同 → np.interp 把 A 的曲线插到 B 的时间网格上，属未校验假设
        steps = {}
        for other in sorted(run.parent.glob("*/csv/timestep_summary.csv")):
            steps[other.parent.parent.name] = len(read_rows(other))
        if len(set(steps.values())) > 1:
            add("C", "已登记", f"{case}: 两臂步数不同 {steps} ⇒ 相对差图的 np.interp 标架未校验（P7）")

        # ---------- C4：终态图 vs 时序图 ----------
        # _plot_final_state 读 final_state_summary.csv，_plot_case_timeseries 读 timestep_summary.csv
        # 两者应能对上；此处只报告是否存在 final_state_summary 供上层对账
        if scheme == sorted(run.parent.glob("*"))[0].name:
            root = run.parent.parent
            fss = root / "final_state_summary.csv"
            if (root / "performance_summary.csv").exists() and not fss.exists():
                add("C", "新问题",
                    f"{case}: 有 performance_summary.csv 但缺 final_state_summary.csv（终态两张图会静默不出）")

        # ---------- P 层：混合分数分类 ----------
        if scheme != "external_mixing":
            continue
        if not (mass_path.exists() and num_path.exists()):
            continue
        groups = 5
        frac_file = RUNTIME_INIT / "fractions.txt"
        if not frac_file.exists():
            add("C", "新问题", f"{case}: 找不到核配送的 {frac_file}（无法判定组成档分类规则）")
            continue

        agg_m = defaultdict(lambda: defaultdict(float))
        tot_m = defaultdict(float)
        for r in read_rows(mass_path):
            t = int(safe_float(r["timestep"])); cb = int(safe_float(r["composition_bin"]))
            agg_m[t][cb] += safe_float(r["mass"]); tot_m[t] += safe_float(r["mass"])
        agg_n = defaultdict(lambda: defaultdict(float))
        tot_n = defaultdict(float)
        for r in read_rows(num_path):
            t = int(safe_float(r["timestep"])); cb = int(safe_float(r["composition_bin"]))
            agg_n[t][cb] += safe_float(r["number"]); tot_n[t] += safe_float(r["number"])

        max_cb = max((int(safe_float(r["composition_bin"])) for r in read_rows(mass_path)), default=1)
        nonzero_t0_all = sorted(cb for cb in agg_m[0] if agg_m[0][cb] > 0)
        unmixed_file, bounds, n_combo = derive_unmixed_bins(groups, frac_file)

        def mixed_frac(agg, tot, t, bins):
            if tot.get(t, 0.0) <= 0:
                return 0.0
            mixed = sum(v for cb, v in agg[t].items() if cb not in bins)
            return mixed / tot[t]

        # 物理不变量：纯外混初值（tag_external=1）在 t=0 没有任何混合态粒子。
        # 数据里 t=0 有质量的组成档 = 该配置的"未混合档"；据此得到经验集合。
        observed_unmixed = set(nonzero_t0_all)
        f_hard_m = mixed_frac(agg_m, tot_m, 0, HARDCODED_UNMIXED)
        f_obs_m = mixed_frac(agg_m, tot_m, 0, observed_unmixed)
        f_hard_n = mixed_frac(agg_n, tot_n, 0, HARDCODED_UNMIXED)

        bad = (f_hard_m > 1e-9) or (f_hard_n > 1e-9)
        add("P", "新问题" if bad else "通过",
            f"{case}: t=0（纯外混初值）混合分数 —— 硬编码规则 质量={f_hard_m:.4f}/数量={f_hard_n:.4f}"
            f"（应为 0）；经验规则 质量={f_obs_m:.4f}。硬编码={sorted(HARDCODED_UNMIXED)}，"
            f"t=0 实际非零档={nonzero_t0_all}（N_fracmax={max_cb}）⇒ "
            f"硬编码多算的档={sorted(HARDCODED_UNMIXED - observed_unmixed)}，漏算的档="
            f"{sorted(observed_unmixed - HARDCODED_UNMIXED)}")
        # 只用经验集合做判定；规则推导（fractions.txt）只作信息性说明 —— 它对"单个分组跨整格"
        # 的组合会误判为未混合，不足以当判据。
        add("P", "通过",
            f"{case}: 信息 —— fractions.txt（{n_combo} 组合/边界 {bounds}）按规则推得 "
            f"{len(unmixed_file)} 个未混合档（仅供参考，不作判据）")

        # ---------- S3：异常是否可见 ----------
        anomalies = read_rows(csv_dir / "anomaly_flags.csv") if (csv_dir / "anomaly_flags.csv").exists() else []
        if anomalies:
            kinds = {r["anomaly_type"] for r in anomalies}
            plotted = "anomaly_flags" in src
            add("S", "新问题" if not plotted else "通过",
                f"{case}/{scheme}: 数据里有 {len(anomalies)} 条异常 {sorted(kinds)}，"
                f"绘图是否读取 anomaly_flags.csv = {plotted}")

        # ---------- S4：量级守卫 ----------
        if ts_path.exists():
            rows = read_rows(ts_path)
            vals = [(int(safe_float(r["timestep"])), safe_float(r["total_number"]), safe_float(r["time_seconds"])) for r in rows]
            if vals and vals[0][1] > 0:
                peak = max(vals, key=lambda x: x[1])
                ratio = peak[1] / max(abs(vals[-1][1]), 1e-300)
                if ratio > 2.0:
                    add("S", "新问题",
                        f"{case}/{scheme}: 总粒数峰值/终值 = {ratio:.1f}×（峰值 {peak[1]:.4g}@t={peak[0]}, "
                        f"t={peak[2]:.0f}s；终值 {vals[-1][1]:.4g}）—— 图上无任何提示")

    # ---------- C5b：runtime/INIT/fractions.txt 是否被本次运行刷新过 ----------
    if RUNTIME_INIT.exists():
        frac_mtime = (RUNTIME_INIT / "fractions.txt").stat().st_mtime
        newer_logs = 0
        newest = 0.0
        newest_name = ""
        for log in ROOT.glob("install_logs/**/run.log"):
            mtime = log.stat().st_mtime
            if mtime > frac_mtime:
                newer_logs += 1
                if mtime > newest:
                    newest, newest_name = mtime, log.parent.parent.parent.name
        if newer_logs:
            add("S", "新问题",
                f"runtime 的 INIT/fractions.txt 比 {newer_logs} 份 run.log 都旧"
                f"（最新的是 {newest_name}）⇒ 该文件是历史运行留下的；核在每次运行读到的是它，"
                f"若与当次配置的 fraction_bounds 不一致，组成档分类会静默错位")

    # ---------- C5：畸形浮点数（核心写出格式缺陷）----------
    if bad_float_hits:
        samples = sorted({f"{a} -> {b}" for a, b in bad_float_hits})[:3]
        add("C", "新问题",
            f"核心 CSV 里存在畸形非规格化浮点数（Fortran 列表输出丢指数标记 E），"
            f"共 {len(bad_float_hits)} 处，样例 {samples}；plot_service.read_csv 直接 float() 会抛异常")

    # ---------- 汇总 ----------
    order = {"新问题": 0, "已登记": 1, "通过": 2}
    results.sort(key=lambda r: (order.get(r[1], 3), r[0]))
    print("=" * 100)
    for layer, level, text in results:
        mark = {"新问题": "✗", "已登记": "·", "通过": "✓"}[level]
        print(f"[{layer}/{level}]{mark} {text}")
    print("=" * 100)
    new = sum(1 for _, lv, _ in results if lv == "新问题")
    known = sum(1 for _, lv, _ in results if lv == "已登记")
    print(f"新问题 {new} 项，已登记 {known} 项，通过 {sum(1 for _, lv, _ in results if lv == '通过')} 项")
    return 1 if new else (3 if known else 0)


if __name__ == "__main__":
    raise SystemExit(main())
