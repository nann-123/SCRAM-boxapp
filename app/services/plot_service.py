from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.services import deployment_paths

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


class PlotService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.set_results_root(deployment_paths.user_results_root())

    def set_results_root(self, results_root: Path) -> None:
        self.results_root = results_root
        self.figure_root = self.results_root / "figures"
        self.figure_root.mkdir(parents=True, exist_ok=True)

    def read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return list(csv.DictReader(handle))

    def generate_all(self, results_root: Path | None = None) -> None:
        if results_root is not None:
            self.set_results_root(results_root)
        self._plot_runtime()
        self._plot_final_state()
        self._plot_case_timeseries()
        self._plot_logic_schematic()

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
        if not (self.results_root / "performance_summary.csv").exists():
            return
        rows = self.read_csv(self.results_root / "performance_summary.csv")
        labels = [f"{row['case_name']}\n{row['scheme']}" for row in rows]
        values = [_to_float(row["wallclock"]) for row in rows]
        colors = [self._scheme_color(row["scheme"]) for row in rows]
        plt.figure(figsize=(10, 5))
        plt.bar(range(len(values)), values, color=colors)
        plt.xticks(range(len(values)), labels, rotation=90, fontsize=7)
        # 单位是秒，且这是机器墙钟时间（含负载噪声），不是模型算力的度量
        plt.ylabel("Wallclock (s)")
        plt.title("Internal vs external mixing runtime comparison (wallclock, machine-dependent)")
        plt.tight_layout()
        plt.savefig(self.figure_root / "runtime_comparison.png", dpi=160)
        plt.close()

    def _plot_final_state(self) -> None:
        if not (self.results_root / "final_state_summary.csv").exists():
            return
        rows = self.read_csv(self.results_root / "final_state_summary.csv")
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
        if missing:
            plt.figtext(0.5, 0.005, f"missing data shown as 0 (hatched): {len(missing)} scheme-case cells", ha="center", fontsize=7)
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / "final_mass_comparison.png", dpi=160)
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
        if missing:
            plt.figtext(0.5, 0.005, f"missing data shown as 0 (hatched): {len(missing)} scheme-case cells", ha="center", fontsize=7)
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / "final_number_comparison.png", dpi=160)
        plt.close()

    def _plot_case_timeseries(self) -> None:
        runs_root = self.results_root / "runs"
        if not runs_root.exists():
            return
        for case_dir in sorted(runs_root.glob("*")):
            if not case_dir.is_dir():
                continue
            schemes = self._scheme_names(case_dir)
            if not schemes:
                continue
            anomaly_note = self._anomaly_counts(case_dir)
            mass_all_zero = True
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                rows = self.read_csv(case_dir / name / "csv" / "timestep_summary.csv")
                times = np.array([_to_float(row["time_seconds"]) for row in rows], dtype=float)
                masses = np.array([_to_float(row["total_mass"]) for row in rows], dtype=float)
                if np.any(np.abs(masses) > 0.0):
                    mass_all_zero = False
                plt.plot(
                    times,
                    masses,
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
            plt.savefig(self.figure_root / f"{case_dir.name}_total_mass.png", dpi=160)
            plt.close()
            number_all_zero = True
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                rows = self.read_csv(case_dir / name / "csv" / "timestep_summary.csv")
                times = np.array([_to_float(row["time_seconds"]) for row in rows], dtype=float)
                numbers = np.array([_to_float(row["total_number"]) for row in rows], dtype=float)
                if np.any(np.abs(numbers) > 0.0):
                    number_all_zero = False
                plt.plot(
                    times,
                    numbers,
                    label=name,
                    color=self._scheme_color(name),
                    linestyle=self._scheme_linestyle(name),
                    linewidth=2.1,
                    alpha=0.9,
                )
            plt.title(f"{case_dir.name}: total number")
            plt.xlabel("Time (s)")
            plt.ylabel("Total particle number (count, dimensionless)")
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
            plt.savefig(self.figure_root / f"{case_dir.name}_total_number.png", dpi=160)
            plt.close()
            ref_name = self._pick_reference_scheme(schemes)
            if ref_name is None:
                continue
            ref_label = "external" if "external" in ref_name.lower() else ref_name
            ref_rows = self.read_csv(case_dir / ref_name / "csv" / "timestep_summary.csv")
            # P7（2026-09-15 绘图核查）：相对差图把参考臂**线性插值**到各臂自己的时间网格上。
            # 两臂步数本来就可能差很多（实测 78 vs 83、79 vs 635），插值会在粗步长一侧留下
            # 折线伪影 ⇒ 必须在图上写明步数，否则读数时容易把伪影当物理。
            step_note = ", ".join(
                f"{n}={len(self.read_csv(case_dir / n / 'csv' / 'timestep_summary.csv'))} steps"
                for n in schemes
            )
            ref_times = np.array([_to_float(row["time_seconds"]) for row in ref_rows], dtype=float)
            ref_mass = np.array([_to_float(row["total_mass"]) for row in ref_rows], dtype=float)
            ref_number = np.array([_to_float(row["total_number"]) for row in ref_rows], dtype=float)
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                rows = self.read_csv(case_dir / name / "csv" / "timestep_summary.csv")
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
            plt.savefig(self.figure_root / f"{case_dir.name}_relative_mass_vs_{ref_label}.png", dpi=160)
            plt.close()
            plt.figure(figsize=(8, 4.5))
            for name in schemes:
                rows = self.read_csv(case_dir / name / "csv" / "timestep_summary.csv")
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
            plt.savefig(self.figure_root / f"{case_dir.name}_relative_number_vs_{ref_label}.png", dpi=160)
            plt.close()
            self._plot_external_mixing_state(case_dir, ref_name)

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
        plt.savefig(self.figure_root / "internal_vs_external_mixing_logic.png", dpi=160)
        plt.close()

    def _plot_external_mixing_state(self, case_dir: Path, ref_name: str) -> None:
        # 用实际挑出来的参考臂，而不是写死目录名
        external_dir = case_dir / ref_name / "csv"
        mass_path = external_dir / "size_composition_mass.csv"
        number_path = external_dir / "size_composition_number.csv"
        if not mass_path.exists() or not number_path.exists():
            return
        mass_rows = self.read_csv(mass_path)
        number_rows = self.read_csv(number_path)
        # 未混合档必须由**该臂自己的数据**推出，不能用写死的编号：
        # 档号跟着 N_frac 变（实测 gmd_paris_full 是 20 个组成档、初始有质量的是 1/12/14/15，
        # 而写死的 {1,3,6,11,20} 只命中 1 个），写死会让"混合粒子分数"在纯外混初值上误报 0.94。
        unmixed_bins = self._derive_unmixed_bins(mass_rows)
        if not unmixed_bins:
            return
        mass_series = self._mixed_fraction_series(mass_rows, "mass", unmixed_bins)
        number_series = self._mixed_fraction_series(number_rows, "number", unmixed_bins)
        if not mass_series or not number_series:
            return
        plt.figure(figsize=(8, 4.5))
        plt.plot([row[0] for row in mass_series], [row[1] for row in mass_series], label="mixed mass fraction")
        plt.plot([row[0] for row in number_series], [row[1] for row in number_series], label="mixed number fraction")
        plt.xlabel("Time (s)")
        plt.ylabel("Mixed-particle fraction (dimensionless)")
        plt.ylim(0.0, 1.05)
        plt.title(f"{case_dir.name}: mixed particle fraction in external representation")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / f"{case_dir.name}_external_mixed_fraction.png", dpi=160)
        plt.close()

        final_timestep = max(int(_to_float(row["timestep"])) for row in mass_rows)
        by_size = defaultdict(lambda: {"mixed": 0.0, "unmixed": 0.0})
        for row in mass_rows:
            if int(_to_float(row["timestep"])) != final_timestep:
                continue
            state = "unmixed" if int(_to_float(row["composition_bin"])) in unmixed_bins else "mixed"
            by_size[int(_to_float(row["size_bin"]))][state] += _to_float(row["mass"])
        sizes = sorted(by_size)
        mixed = np.array([by_size[size]["mixed"] for size in sizes], dtype=float)
        unmixed = np.array([by_size[size]["unmixed"] for size in sizes], dtype=float)
        plt.figure(figsize=(8, 4.5))
        plt.bar(sizes, unmixed, label="unmixed", color="#f58518")
        plt.bar(sizes, mixed, bottom=unmixed, label="mixed", color="#4c78a8")
        plt.xlabel("Size bin index (1..N_sizebin)")
        plt.ylabel("Aerosol mass (ug/m3)")
        plt.title(f"{case_dir.name}: final external mixing-state mass by size bin")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / f"{case_dir.name}_external_mixing_mass_by_size.png", dpi=160)
        plt.close()

    def _derive_unmixed_bins(self, mass_rows: list[dict[str, str]]) -> set[int]:
        """推出"哪些组成档是未混合的（每个分组内只有一个物种）"。

        口径：**t=0 有质量的组成档即未混合档**。依据是物理不变量——纯外混初值
        （tag_external=1，配方为单组分纯粒子）在 t=0 不该有任何混合态粒子，
        所以 t=0 出现的那些档按定义就是"未混合"档。

        已知边界：该推导只在"t=0 是纯外混"时成立。若某臂 t=0 本身就含混合粒子
        （内混臂，或初始已是混合组成），这里会低估未混合集合——使用时可用「纯外混
        初值的混合分数必须为 0」这一判据交叉确认（原先由已移除的
        `scripts/linux/audit_plots.py` 自动核对）。
        """
        at_zero = [
            int(_to_float(row["composition_bin"]))
            for row in mass_rows
            if int(_to_float(row["timestep"])) == 0 and _to_float(row["mass"]) > 0.0
        ]
        return set(at_zero)

    def _mixed_fraction_series(
        self, rows: list[dict[str, str]], column: str, unmixed_bins: set[int]
    ) -> list[tuple[float, float]]:
        totals: dict[int, dict[str, float]] = defaultdict(lambda: {"time": 0.0, "total": 0.0, "mixed": 0.0})
        for row in rows:
            timestep = int(_to_float(row["timestep"]))
            value = _to_float(row[column])
            totals[timestep]["time"] = _to_float(row["time_seconds"])
            totals[timestep]["total"] += value
            if int(_to_float(row["composition_bin"])) not in unmixed_bins:
                totals[timestep]["mixed"] += value
        series = []
        for timestep in sorted(totals):
            total = totals[timestep]["total"]
            if total <= 0.0:
                continue
            series.append((totals[timestep]["time"], totals[timestep]["mixed"] / total))
        return series

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
