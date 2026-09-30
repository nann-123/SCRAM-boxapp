from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.services import composition_grid, deployment_paths, results_layout

# 核心写出的 CSV 由 Fortran 列表输出产生，少数非规格化值会丢掉指数标记：
# 1.0332900803284679E-297 被写成 "1.0332900803284679-297"。直接用 float() 会抛 ValueError，
# 让整张图（以及该 case 后续所有图）全丢。这里补回 E 再解析。
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


def _mass_label(value: float) -> str:
    """柱上质量标注：随量级自适应（教学基座是 1e-3 量级，写死两位小数会全部印成 0.00）。"""
    if value == 0.0:
        return "0"
    if abs(value) >= 1.0:
        return f"{value:.2f}"
    if abs(value) >= 0.01:
        return f"{value:.3f}"
    return f"{value:.2e}"


def _mixing_degree_series(rows: list[dict[str, str]], grid: dict, column: str) -> list[tuple[float, float]]:
    """按时刻做"档混合度"的加权平均：degree(t) = Σ_c w_c(t) · m_c（w 为该档质量/数量份额）。"""
    columns = grid["columns"]
    totals: dict[int, dict[str, float]] = defaultdict(lambda: {"time": 0.0, "total": 0.0, "weighted": 0.0})
    for row in rows:
        timestep = int(_to_float(row["timestep"]))
        value = _to_float(row[column])
        index = int(_to_float(row["composition_bin"]))
        if index < 1 or index > len(columns):
            continue
        totals[timestep]["time"] = _to_float(row["time_seconds"])
        totals[timestep]["total"] += value
        totals[timestep]["weighted"] += value * columns[index - 1]["mixing_degree"]
    return [
        (totals[timestep]["time"], totals[timestep]["weighted"] / totals[timestep]["total"])
        for timestep in sorted(totals)
        if totals[timestep]["total"] > 0.0
    ]


class PlotService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.plot_data: dict = {}
        self.set_results_root(deployment_paths.user_results_root())

    def set_results_root(self, results_root: Path) -> None:
        self.results_root = results_root
        # figures 目录推迟到 generate_all 时创建：浏览/切换根目录不应顺手建空壳目录
        # （09-30 用户反馈：compare 同级出现空 figures 文件夹）。
        self.figure_root = results_root / "figures"
        # 图的分辨率：应用内 160 dpi（省空间）；报告导出时用 generate_all(dpi=300)
        # 重绘一份高清版，避免 PDF 放大后是马赛克。
        self.figure_dpi = 160

    def read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return list(csv.DictReader(handle))

    def generate_all(self, results_root: Path | None = None, figure_root: Path | None = None,
                     dpi: int | None = None) -> dict:
        # 画图的同时把"画进图里的数"收进 self.plot_data，供 scripts/check_plot_data.py
        # 与数据源 CSV 独立对账（绘图核查 20260915 的持续化落地）。
        # figure_root/dpi 由报告导出使用：把同一批图重绘到报告目录、用更高分辨率。
        if results_root is not None:
            self.set_results_root(results_root)
        if figure_root is not None:
            self.figure_root = Path(figure_root)
        if dpi is not None:
            self.figure_dpi = int(dpi)
        self.figure_root.mkdir(parents=True, exist_ok=True)
        # figures 目录整体重画：先清掉旧 PNG，否则上一轮（或已删除案例）的图会残留，
        # 与新图混在一起误导阅读（09-30 用户反馈"好多空白图"的成因之一）。
        for stale in self.figure_root.glob("*.png"):
            stale.unlink()
        self.plot_data = {}
        self._plot_runtime()
        self._plot_final_state()
        self._plot_case_timeseries()
        self._plot_logic_schematic()
        return self.plot_data

    # ------------------------------------------------------------------
    # 辅助：读取一臂的时序 / 组成态数据
    # ------------------------------------------------------------------
    def _scheme_names(self, case_dir: Path) -> list[str]:
        """列出该 case 下**真的有 timestep_summary.csv** 的臂（缺数据的臂不参与绘图）。"""
        names = []
        for scheme_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            if (scheme_dir / "csv" / "timestep_summary.csv").exists():
                names.append(scheme_dir.name)
        return names

    def _pick_reference_scheme(self, names: list[str]) -> str | None:
        """参考臂从实际存在的臂里挑，而不是假设目录名。"""
        for preferred in ("external_mixing", "EXTERNAL_MIXING"):
            if preferred in names:
                return preferred
        return names[0] if names else None

    def _anomaly_counts(self, case_dir: Path) -> dict[str, int]:
        """汇总该 case 各臂的 anomaly_flags（核心自己判定的异常）。"""
        counts: dict[str, int] = defaultdict(int)
        for scheme_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            path = scheme_dir / "csv" / "anomaly_flags.csv"
            if not path.exists():
                continue
            for row in self.read_csv(path):
                counts[row.get("anomaly_type", "unknown")] += 1
        return dict(counts)

    def _plot_runtime(self) -> None:
        perf_path = results_layout.case_csv_dir(self.results_root) / "performance_summary.csv"
        if not perf_path.exists():
            return
        rows = self.read_csv(perf_path)
        # 单臂运行也写 performance_summary.csv（记录墙钟），但"运行耗时对比"至少要两条才有意义。
        if len(rows) < 2:
            return
        labels = [f"{row['case_name']}\n{row['scheme']}" for row in rows]
        values = [_to_float(row["wallclock"]) for row in rows]
        self.plot_data["runtime"] = {"labels": labels, "wallclock": list(values)}
        colors = [self._scheme_color(row["scheme"]) for row in rows]
        plt.figure(figsize=(10, 5))
        plt.bar(range(len(values)), values, color=colors)
        plt.xticks(range(len(values)), labels, rotation=90, fontsize=7)
        # 单位是秒，且这是机器墙钟时间（含负载噪声），不是模型算力的度量
        plt.ylabel("Wallclock (s)")
        plt.title("Internal vs external mixing runtime comparison (wallclock, machine-dependent)")
        plt.tight_layout()
        plt.savefig(self.figure_root / "runtime_comparison.png", dpi=self.figure_dpi)
        plt.close()

    def _plot_final_state(self) -> None:
        final_path = results_layout.case_csv_dir(self.results_root) / "final_state_summary.csv"
        if not final_path.exists():
            return
        rows = self.read_csv(final_path)
        cases = sorted(set(row["case_name"] for row in rows))
        schemes = self._ordered_schemes(rows)
        mass = defaultdict(dict)
        number = defaultdict(dict)
        for row in rows:
            mass[row["case_name"]][row["scheme"]] = _to_float(row["final_total_mass"])
            number[row["case_name"]][row["scheme"]] = _to_float(row["final_total_number"])
        x = np.arange(len(cases))
        width = min(0.8 / max(len(schemes), 1), 0.35)
        # 缺失的臂用 0 高度 + 标注（原来用 np.nan，bar 会静默跳过，看起来像"没跑"而不是"缺数据"）
        missing = sorted({(c, s) for c in cases for s in schemes if s not in mass[c]})
        self.plot_data["final_state"] = {
            "cases": list(cases),
            "schemes": list(schemes),
            "mass": {c: dict(mass[c]) for c in cases},
            "number": {c: dict(number[c]) for c in cases},
            "missing": [list(cell) for cell in missing],
        }
        plt.figure(figsize=(8, 4.5))
        for idx, scheme in enumerate(schemes):
            offset = (idx - (len(schemes) - 1) / 2) * width
            plt.bar(
                x + offset,
                [mass[c].get(scheme, 0.0) for c in cases],
                width=width,
                label=scheme,
                color=self._scheme_color(scheme),
                hatch="//" if any(cs[1] == scheme for cs in missing) else None,
            )
        plt.xticks(x, cases, rotation=20)
        plt.ylabel("Final total aerosol mass (ug/m3)")
        plt.title("Final mass comparison")
        # 09-30（用户反馈柱状图分不开两臂差异）：对数轴 + 动态量程把小百分比差异放大到可读；
        # 两臂数值完全一致时柱高依旧相同——那是配置事实，轴无法区分相同的数据。
        visible_mass = [
            mass[c].get(s, 0.0) for c in cases for s in schemes if mass[c].get(s, 0.0) > 0.0
        ]
        if visible_mass:
            plt.ylim(bottom=min(visible_mass) * 0.8, top=max(visible_mass) * 1.3)
        plt.yscale("log")
        if missing:
            plt.figtext(0.5, 0.005, f"missing data shown as 0 (hatched): {len(missing)} scheme-case cells", ha="center", fontsize=7)
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / "final_mass_comparison.png", dpi=self.figure_dpi)
        plt.close()
        plt.figure(figsize=(8, 4.5))
        for idx, scheme in enumerate(schemes):
            offset = (idx - (len(schemes) - 1) / 2) * width
            plt.bar(
                x + offset,
                [number[c].get(scheme, 0.0) for c in cases],
                width=width,
                label=scheme,
                color=self._scheme_color(scheme),
                hatch="//" if any(cs[1] == scheme for cs in missing) else None,
            )
        plt.xticks(x, cases, rotation=20)
        plt.ylabel("Final total particle number (count, dimensionless)")
        plt.title("Final number comparison")
        visible_number = [
            number[c].get(s, 0.0) for c in cases for s in schemes if number[c].get(s, 0.0) > 0.0
        ]
        if visible_number:
            plt.ylim(bottom=min(visible_number) * 0.8, top=max(visible_number) * 1.3)
        plt.yscale("log")
        if missing:
            plt.figtext(0.5, 0.005, f"missing data shown as 0 (hatched): {len(missing)} scheme-case cells", ha="center", fontsize=7)
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / "final_number_comparison.png", dpi=self.figure_dpi)
        plt.close()

    def _plot_case_timeseries(self) -> None:
        # 2026-09-30 新布局：结果根 = 案例目录（<结果根>/<案例名>/，臂目录是它的子目录）。
        # 这里保留单元素循环：下面的 continue 语义就是"该案例无数据 → 跳过"。
        for case_dir in (self.results_root,):
            if not case_dir.is_dir():
                continue
            schemes = self._scheme_names(case_dir)
            if not schemes:
                continue
            # 零数据案例（探针残留：CSV 只有表头）画出来是空白坐标轴——整案跳过。
            if all(
                not self.read_csv(case_dir / name / "csv" / "timestep_summary.csv")
                for name in schemes
            ):
                continue
            anomaly_note = self._anomaly_counts(case_dir)
            case_entry = self.plot_data.setdefault("cases", {}).setdefault(
                case_dir.name, {"schemes": list(schemes), "series": {}, "relative": {}}
            )
            case_entry["anomaly_counts"] = dict(anomaly_note)
            # 每臂只读一次；两臂逐位一致时在图上明确标注（09-30：11 个组合两臂完全相同，
            # 时序线重叠、相对差恒零，观感像"缺线/空图"，实为该配置下内外混无差异）
            data_rows = {
                name: self.read_csv(case_dir / name / "csv" / "timestep_summary.csv")
                for name in schemes
            }
            # 逐位一致判断只看数值列（time/mass/number）——scheme 等标签列两臂必然不同
            parsed = {
                name: {
                    "time": [_to_float(row["time_seconds"]) for row in data_rows[name]],
                    "mass": [_to_float(row["total_mass"]) for row in data_rows[name]],
                    "number": [_to_float(row["total_number"]) for row in data_rows[name]],
                }
                for name in schemes
            }
            mass_all_zero = True
            for name in schemes:
                times = np.array(parsed[name]["time"], dtype=float)
                masses = np.array(parsed[name]["mass"], dtype=float)
                case_entry["series"][name] = {"time": times.tolist(), "mass": masses.tolist()}
                if np.any(np.abs(masses) > 0.0):
                    mass_all_zero = False
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                plt.plot(
                    np.array(parsed[name]["time"], dtype=float),
                    np.array(parsed[name]["mass"], dtype=float),
                    label=name,
                    color=self._scheme_color(name),
                    linestyle=self._scheme_linestyle(name),
                    linewidth=2.1,
                    alpha=0.9,
                )
            plt.title(f"{case_dir.name}: total mass")
            plt.xlabel("Time (s)")
            plt.ylabel("Total aerosol mass (ug/m3)")
            if mass_all_zero:
                # P9：数据全零时图看起来“正常”，加显著水印避免误读为“结果正常”
                plt.figtext(0.5, 0.5, "NO NON-ZERO DATA", ha="center", va="center",
                            fontsize=26, color="#cccccc", rotation=18)
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_total_mass.png", dpi=self.figure_dpi)
            plt.close()
            number_all_zero = True
            for name in schemes:
                times = np.array(parsed[name]["time"], dtype=float)
                numbers = np.array(parsed[name]["number"], dtype=float)
                case_entry["series"][name]["number"] = numbers.tolist()
                if np.any(np.abs(numbers) > 0.0):
                    number_all_zero = False
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                plt.plot(
                    np.array(parsed[name]["time"], dtype=float),
                    np.array(parsed[name]["number"], dtype=float),
                    label=name,
                    color=self._scheme_color(name),
                    linestyle=self._scheme_linestyle(name),
                    linewidth=2.1,
                    alpha=0.9,
                )
            plt.title(f"{case_dir.name}: total number")
            plt.xlabel("Time (s)")
            plt.ylabel("Total particle number (count, dimensionless)")
            # 对数轴（09-30 用户批准）：排放暴发期数量比后期高 2–3 个数量级，
            # 线性轴下后期演化全部贴在横轴附近无法阅读。
            plt.yscale("log")
            if anomaly_note:
                note = ", ".join(f"{k} x{v}" for k, v in sorted(anomaly_note.items()))
                plt.figtext(
                    0.5, 0.005,
                    f"! core-flagged anomalies: {note} (see csv/anomaly_flags.csv)",
                    ha="center", fontsize=7, color="#b22222",
                )
            if number_all_zero:
                plt.figtext(0.5, 0.5, "NO NON-ZERO DATA", ha="center", va="center",
                            fontsize=26, color="#cccccc", rotation=18)
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_total_number.png", dpi=self.figure_dpi)
            plt.close()
            ref_name = self._pick_reference_scheme(schemes)
            if ref_name is None:
                continue
            # 外混状态图只需要外混臂自身的数据，与臂数无关 —— 单臂外混运行也要出
            # （09-30 补充：只有相对差图才需要两条臂）。
            case_entry["ref"] = ref_name
            if "external" in ref_name.lower():
                self._plot_external_mixing_state(case_dir, ref_name)
            # 单臂运行没有"另一臂"可比：相对差图退化为自比零线，跳过。
            if len(schemes) < 2:
                continue
            ref_label = "external" if "external" in ref_name.lower() else ref_name
            # P7（2026-09-15 绘图核查）：相对差图把参考臂线性插值到公共时间网格，
            # 两臂步数可能差很多 ⇒ 必须在图上写明步数，避免把采样伪影当物理。
            step_note = ", ".join(f"{n}={len(parsed[n]['time'])} steps" for n in schemes)
            case_entry["step_note"] = step_note
            ref_times = np.array(parsed[ref_name]["time"], dtype=float)
            ref_mass = np.array(parsed[ref_name]["mass"], dtype=float)
            ref_number = np.array(parsed[ref_name]["number"], dtype=float)
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                rows = data_rows[name]
                times = np.array([_to_float(row["time_seconds"]) for row in rows], dtype=float)
                masses = np.array([_to_float(row["total_mass"]) for row in rows], dtype=float)
                if name == ref_name:
                    plt.plot(times, np.zeros_like(times), label=f"{name} (reference, identically 0)", linestyle=":", color="#888888")
                else:
                    # 相对差的口径（2026-09-20 实测更正）：两臂**时间网格不同**（实测 78 vs 83 步），
                    # 所以逐点相减得到的曲线包含两部分：真实的物理差异 + 步长尺度的采样成分。
                    # 实测：中段振荡幅度 1.33e-2，粗化到 300 s 共同网格后降到 5.92e-3
                    # ⇒ 振荡**不是**插值 bug，约一半是真实差异；但**单点的振荡不可当物理读**，
                    # 要看趋势。这里把两臂都插值到公共网格（并集），并注明步数。
                    grid = np.union1d(times, ref_times)
                    arm_values = np.interp(grid, times, masses)
                    ref_values = np.interp(grid, ref_times, ref_mass)
                    rel = (arm_values - ref_values) / np.maximum(np.abs(ref_values), 1.0e-20)
                    case_entry["relative"].setdefault("mass", {})[name] = {"grid": grid.tolist(), "rel": rel.tolist()}
                    plt.plot(grid, rel, label=name, color=self._scheme_color(name))
            plt.title(f"{case_dir.name}: relative mass difference vs {ref_label}")
            plt.xlabel("Time (s)")
            plt.ylabel("Relative mass difference (dimensionless)")
            plt.figtext(0.5, 0.005,
                        f"common time grid (union of steps); {step_note}. "
                        f"Sawtooth = real difference + step-scale sampling; read trends, not single points.",
                        ha="center", fontsize=6.5, color="#666666")
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_relative_mass_vs_{ref_label}.png", dpi=self.figure_dpi)
            plt.close()
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                rows = data_rows[name]
                times = np.array([_to_float(row["time_seconds"]) for row in rows], dtype=float)
                number = np.array([_to_float(row["total_number"]) for row in rows], dtype=float)
                if name == ref_name:
                    plt.plot(times, np.zeros_like(times), label=f"{name} (reference, identically 0)", linestyle=":", color="#888888")
                else:
                    # 同相对质量图：两臂都插值到公共网格；振荡含采样成分，读数看趋势
                    grid = np.union1d(times, ref_times)
                    arm_values = np.interp(grid, times, number)
                    ref_values = np.interp(grid, ref_times, ref_number)
                    rel = (arm_values - ref_values) / np.maximum(np.abs(ref_values), 1.0e-20)
                    case_entry["relative"].setdefault("number", {})[name] = {"grid": grid.tolist(), "rel": rel.tolist()}
                    plt.plot(grid, rel, label=name, color=self._scheme_color(name))
            plt.title(f"{case_dir.name}: relative number difference vs {ref_label}")
            plt.xlabel("Time (s)")
            plt.ylabel("Relative number difference (dimensionless)")
            plt.figtext(0.5, 0.005,
                        f"common time grid (union of steps); {step_note}. "
                        f"Sawtooth = real difference + step-scale sampling; read trends, not single points.",
                        ha="center", fontsize=6.5, color="#666666")
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_relative_number_vs_{ref_label}.png", dpi=self.figure_dpi)
            plt.close()

    def _plot_logic_schematic(self) -> None:
        plt.figure(figsize=(8, 4))
        plt.axis("off")
        plt.text(0.18, 0.75, "INTERNAL_MIXING", ha="center", va="center", fontsize=14, bbox={"boxstyle": "round", "facecolor": "#b8d8f8"})
        plt.text(0.18, 0.45, "One average composition\nper size section", ha="center", va="center")
        plt.text(0.18, 0.18, "Faster, less composition detail", ha="center", va="center")
        plt.text(0.78, 0.75, "EXTERNAL_MIXING", ha="center", va="center", fontsize=14, bbox={"boxstyle": "round", "facecolor": "#f9d29d"})
        plt.text(0.78, 0.45, "Size + composition cells\nresolve mixing state", ha="center", va="center")
        plt.text(0.78, 0.18, "Tracks mixed and unmixed particles", ha="center", va="center")
        plt.annotate("", xy=(0.18, 0.55), xytext=(0.18, 0.67), arrowprops={"arrowstyle": "->"})
        plt.annotate("", xy=(0.18, 0.28), xytext=(0.18, 0.40), arrowprops={"arrowstyle": "->"})
        plt.annotate("", xy=(0.78, 0.55), xytext=(0.78, 0.67), arrowprops={"arrowstyle": "->"})
        plt.annotate("", xy=(0.78, 0.28), xytext=(0.78, 0.40), arrowprops={"arrowstyle": "->"})
        plt.title("Internal vs external mixing assumptions")
        plt.tight_layout()
        plt.savefig(self.figure_root / "internal_vs_external_mixing_logic.png", dpi=self.figure_dpi)
        plt.close()

    def _load_composition_grid(self, csv_dir: Path) -> dict | None:
        """读该臂存档的"档→组成"映射（fractions.txt + composition_grid.json）。

        缺任一文件返回 None（09-30 之前的老运行没有这份存档）——此时不画混合度图，
        避免退回"距 t=0 偏移"的旧口径。
        """
        spec_path = csv_dir / "composition_grid.json"
        fractions_path = csv_dir / "fractions.txt"
        if not spec_path.exists() or not fractions_path.exists():
            return None
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            return composition_grid.build_grid_map(fractions_path, int(spec["n_groups"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def _initial_composition_bins(self, mass_rows: list[dict[str, str]]) -> set[int]:
        """该次运行 t=0 有质量的组成档（"初始档"）。

        注意：这是**相对口径**的基准。只在"t=0 是纯外混"时它才等于物理意义的未混合档；
        内混放置的运行里它只是"起点档"，所以用它的曲线叫"距初始档的偏移"（composition drift），
        是诊断量、不是混合态指标（2026-09-30 用户要求：保留旧口径但换名，与新混合度图并存）。
        """
        return {
            int(_to_float(row["composition_bin"]))
            for row in mass_rows
            if int(_to_float(row["timestep"])) == 0 and _to_float(row["mass"]) > 0.0
        }

    def _composition_drift_series(
        self, rows: list[dict[str, str]], column: str, initial_bins: set[int]
    ) -> list[tuple[float, float]]:
        totals: dict[int, dict[str, float]] = defaultdict(lambda: {"time": 0.0, "total": 0.0, "outside": 0.0})
        for row in rows:
            timestep = int(_to_float(row["timestep"]))
            value = _to_float(row[column])
            totals[timestep]["time"] = _to_float(row["time_seconds"])
            totals[timestep]["total"] += value
            if int(_to_float(row["composition_bin"])) not in initial_bins:
                totals[timestep]["outside"] += value
        return [
            (totals[t]["time"], totals[t]["outside"] / totals[t]["total"])
            for t in sorted(totals)
            if totals[t]["total"] > 0.0
        ]

    def _plot_external_mixing_state(self, case_dir: Path, ref_name: str) -> None:
        # 用实际挑出来的参考臂，而不是写死目录名
        external_dir = case_dir / ref_name / "csv"
        mass_path = external_dir / "size_composition_mass.csv"
        number_path = external_dir / "size_composition_number.csv"
        if not mass_path.exists() or not number_path.exists():
            return
        mass_rows = self.read_csv(mass_path)
        number_rows = self.read_csv(number_path)
        external = self.plot_data.setdefault("cases", {}).setdefault(case_dir.name, {}).setdefault(
            "external_mixing", {"ref": ref_name}
        )

        # (1) 诊断图：距初始档的偏移（旧口径保留版，09-30 换名）——不依赖档映射，任何运行都能画
        initial_bins = self._initial_composition_bins(mass_rows)
        if initial_bins:
            drift_mass = self._composition_drift_series(mass_rows, "mass", initial_bins)
            drift_number = self._composition_drift_series(number_rows, "number", initial_bins)
            if drift_mass and drift_number:
                plt.figure(figsize=(8, 4.5))
                plt.plot([p[0] for p in drift_mass], [p[1] for p in drift_mass], label="outside initial bins (mass)")
                plt.plot([p[0] for p in drift_number], [p[1] for p in drift_number], label="outside initial bins (number)")
                plt.xlabel("Time (s)")
                plt.ylabel("Fraction outside the initial composition bins")
                plt.ylim(0.0, 1.05)
                plt.title(f"{case_dir.name}: composition drift from initial bins (diagnostic)")
                plt.figtext(0.5, 0.005,
                            "relative to this run's own t=0 composition bins; NOT a mixing state "
                            "- see the mixing-degree chart",
                            ha="center", fontsize=6.5, color="#666666")
                plt.legend()
                plt.tight_layout()
                plt.savefig(self.figure_root / f"{case_dir.name}_external_composition_drift.png", dpi=self.figure_dpi)
                plt.close()
                external["initial_bins"] = sorted(initial_bins)
                external["drift_mass"] = [list(point) for point in drift_mass]
                external["drift_number"] = [list(point) for point in drift_number]

        # (2) 混合度图（新口径）：需要内核落盘的档→组成映射；老运行没有该存档则跳过本图
        grid = self._load_composition_grid(external_dir)
        if grid is None:
            return
        mass_series = _mixing_degree_series(mass_rows, grid, "mass")
        number_series = _mixing_degree_series(number_rows, grid, "number")
        if not mass_series or not number_series:
            return
        uncertainty = max(column["uncertainty"] for column in grid["columns"])
        plt.figure(figsize=(8, 4.5))
        plt.plot([row[0] for row in mass_series], [row[1] for row in mass_series], label="mass-weighted degree")
        plt.plot([row[0] for row in number_series], [row[1] for row in number_series], label="number-weighted degree")
        plt.xlabel("Time (s)")
        plt.ylabel("Average mixing degree")
        plt.ylim(0.0, 1.05)
        plt.title(f"{case_dir.name}: external-arm average mixing degree")
        plt.figtext(0.5, 0.005,
                    "0 = single-component, 1 = evenly mixed; per-bin degree = 1 - dominant group share; "
                    f"grid uncertainty ±{uncertainty:.2f}; comparable only within the same discretization",
                    ha="center", fontsize=6.5, color="#666666")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / f"{case_dir.name}_external_mixed_fraction.png", dpi=self.figure_dpi)
        plt.close()

        # 按粒径（连续口径，09-30 用户确认）：每档一根柱 = 该档质量加权混合度，
        # 柱上标注该档质量——直接回答"哪个粒径段混合得充分、哪个还是单成分"。
        final_timestep = max(int(_to_float(row["timestep"])) for row in mass_rows)
        columns = grid["columns"]
        by_size_mass: dict[int, float] = defaultdict(float)
        by_size_weighted: dict[int, float] = defaultdict(float)
        for row in mass_rows:
            if int(_to_float(row["timestep"])) != final_timestep:
                continue
            index = int(_to_float(row["composition_bin"]))
            if index < 1 or index > len(columns):
                continue
            value = _to_float(row["mass"])
            size = int(_to_float(row["size_bin"]))
            by_size_mass[size] += value
            by_size_weighted[size] += value * columns[index - 1]["mixing_degree"]
        sizes = sorted(by_size_mass)
        degrees_by_size = {
            size: (by_size_weighted[size] / by_size_mass[size] if by_size_mass[size] > 0.0 else 0.0)
            for size in sizes
        }
        drawn = [size for size in sizes if by_size_mass[size] > 0.0]
        # 只画"有意义质量"的柱：低于总量 1e-6 的痕量档不画（否则会出现"柱高 0.56 而
        # 标注质量 0.00"的误导——那些档质量非零但小到显示不出来）。
        total_final = sum(by_size_mass.values())
        floor = total_final * 1e-6 if total_final > 0.0 else 0.0
        drawn = [size for size in drawn if by_size_mass[size] > floor]
        plt.figure(figsize=(8, 4.5))
        if drawn:
            bars = plt.bar(drawn, [degrees_by_size[size] for size in drawn], color="#4c78a8")
            for rect, size in zip(bars, drawn):
                plt.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 0.02,
                         _mass_label(by_size_mass[size]), ha="center", fontsize=7)
        plt.xlabel("Size bin index (1..N_sizebin)")
        plt.ylabel("Mass-weighted mixing degree")
        plt.xticks(sizes)  # 全部粒径档都上轴（无质量的档留空，不再因跳过画柱而缩轴）
        plt.ylim(0.0, 1.15)
        plt.title(f"{case_dir.name}: external-arm mixing degree by size bin (final state)")
        plt.figtext(0.5, 0.005,
                    "0 = single-component, 1 = evenly mixed; label = bin mass (ug/m3); "
                    f"grid uncertainty ±{uncertainty:.2f}; comparable only within the same discretization",
                    ha="center", fontsize=6.5, color="#666666")
        plt.tight_layout()
        plt.savefig(self.figure_root / f"{case_dir.name}_external_mixing_degree_by_size.png", dpi=self.figure_dpi)
        plt.close()
        external.update({
            "mixing_degree_mass": [list(point) for point in mass_series],
            "mixing_degree_number": [list(point) for point in number_series],
            "uncertainty": uncertainty,
            "by_size_degree": {str(size): degrees_by_size[size] for size in sizes},
            "by_size_mass": {str(size): by_size_mass[size] for size in sizes},
            "drawn_bins": sorted(drawn),
            "final_timestep": final_timestep,
        })

    def _ordered_schemes(self, rows: list[dict[str, str]]) -> list[str]:
        present = {row["scheme"] for row in rows}
        preferred = ["INTERNAL_MIXING", "EXTERNAL_MIXING", "LEGACY", "DETERMINISTIC_NEAREST"]
        ordered = [scheme for scheme in preferred if scheme in present]
        ordered.extend(sorted(present - set(ordered)))
        return ordered

    def _scheme_color(self, scheme: str) -> str:
        upper = scheme.upper()
        if "INTERNAL" in upper:
            return "#4c78a8"
        if "EXTERNAL" in upper:
            return "#f58518"
        if "NEAREST" in upper:
            return "#54a24b"
        return "#b279a2"

    def _scheme_linestyle(self, scheme: str) -> str:
        upper = scheme.upper()
        if "INTERNAL" in upper:
            return "--"
        if "EXTERNAL" in upper:
            return "-"
        if "NEAREST" in upper:
            return ":"
        return "-."
