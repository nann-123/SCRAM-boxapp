from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.services import deployment_paths


class PlotService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.set_results_root(deployment_paths.user_results_root())

    def set_results_root(self, results_root: Path) -> None:
        self.results_root = results_root
        self.figure_root = self.results_root / "figures"
        self.figure_root.mkdir(parents=True, exist_ok=True)

    def read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open() as handle:
            return list(csv.DictReader(handle))

    def generate_all(self, results_root: Path | None = None) -> None:
        if results_root is not None:
            self.set_results_root(results_root)
        self._plot_runtime()
        self._plot_final_state()
        self._plot_case_timeseries()
        self._plot_logic_schematic()

    def _plot_runtime(self) -> None:
        if not (self.results_root / "performance_summary.csv").exists():
            return
        rows = self.read_csv(self.results_root / "performance_summary.csv")
        labels = [f"{row['case_name']}\n{row['scheme']}" for row in rows]
        values = [float(row["wallclock"]) for row in rows]
        colors = [self._scheme_color(row["scheme"]) for row in rows]
        plt.figure(figsize=(10, 5))
        plt.bar(range(len(values)), values, color=colors)
        plt.xticks(range(len(values)), labels, rotation=90, fontsize=7)
        plt.ylabel("Wallclock (s)")
        plt.title("Internal vs external mixing runtime comparison")
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
            mass[row["case_name"]][row["scheme"]] = float(row["final_total_mass"])
            number[row["case_name"]][row["scheme"]] = float(row["final_total_number"])
        x = np.arange(len(cases))
        width = min(0.8 / max(len(schemes), 1), 0.35)
        plt.figure(figsize=(8, 4.5))
        for idx, scheme in enumerate(schemes):
            offset = (idx - (len(schemes) - 1) / 2) * width
            plt.bar(x + offset, [mass[c].get(scheme, np.nan) for c in cases], width=width, label=scheme, color=self._scheme_color(scheme))
        plt.xticks(x, cases, rotation=20)
        plt.ylabel("Final mass")
        plt.title("Final mass comparison")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / "final_mass_comparison.png", dpi=160)
        plt.close()
        plt.figure(figsize=(8, 4.5))
        for idx, scheme in enumerate(schemes):
            offset = (idx - (len(schemes) - 1) / 2) * width
            plt.bar(x + offset, [number[c].get(scheme, np.nan) for c in cases], width=width, label=scheme, color=self._scheme_color(scheme))
        plt.xticks(x, cases, rotation=20)
        plt.ylabel("Final number")
        plt.title("Final number comparison")
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
            plt.figure(figsize=(8, 4.5))
            for scheme_dir in sorted(case_dir.glob("*")):
                if not (scheme_dir / "csv" / "timestep_summary.csv").exists():
                    continue
                rows = self.read_csv(scheme_dir / "csv" / "timestep_summary.csv")
                times = np.array([float(row["time_seconds"]) for row in rows], dtype=float)
                masses = np.array([float(row["total_mass"]) for row in rows], dtype=float)
                plt.plot(
                    times,
                    masses,
                    label=scheme_dir.name,
                    color=self._scheme_color(scheme_dir.name),
                    linestyle=self._scheme_linestyle(scheme_dir.name),
                    linewidth=2.1,
                    alpha=0.9,
                )
            plt.title(f"{case_dir.name}: total mass")
            plt.xlabel("Time (s)")
            plt.ylabel("Total mass")
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_total_mass.png", dpi=160)
            plt.close()
            plt.figure(figsize=(8, 4.5))
            for scheme_dir in sorted(case_dir.glob("*")):
                if not (scheme_dir / "csv" / "timestep_summary.csv").exists():
                    continue
                rows = self.read_csv(scheme_dir / "csv" / "timestep_summary.csv")
                times = np.array([float(row["time_seconds"]) for row in rows], dtype=float)
                numbers = np.array([float(row["total_number"]) for row in rows], dtype=float)
                plt.plot(
                    times,
                    numbers,
                    label=scheme_dir.name,
                    color=self._scheme_color(scheme_dir.name),
                    linestyle=self._scheme_linestyle(scheme_dir.name),
                    linewidth=2.1,
                    alpha=0.9,
                )
            plt.title(f"{case_dir.name}: total number")
            plt.xlabel("Time (s)")
            plt.ylabel("Total number")
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_total_number.png", dpi=160)
            plt.close()
            ref_dir = case_dir / "external_mixing"
            ref_label = "external"
            if not (ref_dir / "csv" / "timestep_summary.csv").exists():
                ref_dir = case_dir / "deterministic_nearest"
                ref_label = "nearest"
            if not (ref_dir / "csv" / "timestep_summary.csv").exists():
                continue
            plt.figure(figsize=(8, 4.5))
            ref_rows = self.read_csv(ref_dir / "csv" / "timestep_summary.csv")
            ref_times = np.array([float(row["time_seconds"]) for row in ref_rows], dtype=float)
            ref_mass = np.array([float(row["total_mass"]) for row in ref_rows], dtype=float)
            ref_number = np.array([float(row["total_number"]) for row in ref_rows], dtype=float)
            for scheme_dir in sorted(case_dir.glob("*")):
                rows = self.read_csv(scheme_dir / "csv" / "timestep_summary.csv")
                times = np.array([float(row["time_seconds"]) for row in rows], dtype=float)
                masses = np.array([float(row["total_mass"]) for row in rows], dtype=float)
                number = np.array([float(row["total_number"]) for row in rows], dtype=float)
                if scheme_dir.name == ref_dir.name:
                    plt.plot(times, np.zeros_like(times), label=scheme_dir.name)
                else:
                    interp = np.interp(times, ref_times, ref_mass)
                    rel = (masses - interp) / np.maximum(np.abs(interp), 1.0e-20)
                    plt.plot(times, rel, label=scheme_dir.name)
            plt.title(f"{case_dir.name}: relative mass difference vs {ref_label}")
            plt.xlabel("Time (s)")
            plt.ylabel("Relative difference")
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_relative_mass_vs_{ref_label}.png", dpi=160)
            plt.close()
            plt.figure(figsize=(8, 4.5))
            for scheme_dir in sorted(case_dir.glob("*")):
                rows = self.read_csv(scheme_dir / "csv" / "timestep_summary.csv")
                times = np.array([float(row["time_seconds"]) for row in rows], dtype=float)
                number = np.array([float(row["total_number"]) for row in rows], dtype=float)
                if scheme_dir.name == ref_dir.name:
                    plt.plot(times, np.zeros_like(times), label=scheme_dir.name)
                else:
                    interp = np.interp(times, ref_times, ref_number)
                    rel = (number - interp) / np.maximum(np.abs(interp), 1.0e-20)
                    plt.plot(times, rel, label=scheme_dir.name)
            plt.title(f"{case_dir.name}: relative number difference vs {ref_label}")
            plt.xlabel("Time (s)")
            plt.ylabel("Relative difference")
            plt.legend()
            plt.tight_layout()
            plt.savefig(self.figure_root / f"{case_dir.name}_relative_number_vs_{ref_label}.png", dpi=160)
            plt.close()
            self._plot_external_mixing_state(case_dir)

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

    def _plot_external_mixing_state(self, case_dir: Path) -> None:
        external_dir = case_dir / "external_mixing" / "csv"
        mass_path = external_dir / "size_composition_mass.csv"
        number_path = external_dir / "size_composition_number.csv"
        if not mass_path.exists() or not number_path.exists():
            return
        mass_rows = self.read_csv(mass_path)
        number_rows = self.read_csv(number_path)
        mass_series = self._mixed_fraction_series(mass_rows, "mass")
        number_series = self._mixed_fraction_series(number_rows, "number")
        if not mass_series or not number_series:
            return
        plt.figure(figsize=(8, 4.5))
        plt.plot([row[0] for row in mass_series], [row[1] for row in mass_series], label="mixed mass fraction")
        plt.plot([row[0] for row in number_series], [row[1] for row in number_series], label="mixed number fraction")
        plt.xlabel("Time (s)")
        plt.ylabel("Fraction")
        plt.ylim(0.0, 1.05)
        plt.title(f"{case_dir.name}: mixed particle fraction in external representation")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / f"{case_dir.name}_external_mixed_fraction.png", dpi=160)
        plt.close()

        final_timestep = max(int(float(row["timestep"])) for row in mass_rows)
        by_size = defaultdict(lambda: {"mixed": 0.0, "unmixed": 0.0})
        for row in mass_rows:
            if int(float(row["timestep"])) != final_timestep:
                continue
            state = "unmixed" if int(float(row["composition_bin"])) in {1, 3, 6, 11, 20} else "mixed"
            by_size[int(float(row["size_bin"]))][state] += float(row["mass"])
        sizes = sorted(by_size)
        mixed = np.array([by_size[size]["mixed"] for size in sizes], dtype=float)
        unmixed = np.array([by_size[size]["unmixed"] for size in sizes], dtype=float)
        plt.figure(figsize=(8, 4.5))
        plt.bar(sizes, unmixed, label="unmixed", color="#f58518")
        plt.bar(sizes, mixed, bottom=unmixed, label="mixed", color="#4c78a8")
        plt.xlabel("Size bin")
        plt.ylabel("Mass")
        plt.title(f"{case_dir.name}: final external mixing-state mass by size bin")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.figure_root / f"{case_dir.name}_external_mixing_mass_by_size.png", dpi=160)
        plt.close()

    def _mixed_fraction_series(self, rows: list[dict[str, str]], column: str) -> list[tuple[float, float]]:
        unmixed_bins = {1, 3, 6, 11, 20}
        totals: dict[int, dict[str, float]] = defaultdict(lambda: {"time": 0.0, "total": 0.0, "mixed": 0.0})
        for row in rows:
            timestep = int(float(row["timestep"]))
            value = float(row[column])
            totals[timestep]["time"] = float(row["time_seconds"])
            totals[timestep]["total"] += value
            if int(float(row["composition_bin"])) not in unmixed_bins:
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
