from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties

from app.services import deployment_paths


class ReportService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.results_root = deployment_paths.user_results_root()
        self.report_root = deployment_paths.user_report_root()
        self.report_root.mkdir(parents=True, exist_ok=True)
        self.last_backend_message = ""

    def set_results_root(self, results_root: Path) -> None:
        self.results_root = results_root

    def available(self) -> bool:
        return True

    def generate(self, selected_figures: list[str] | None = None, prefer_latex: bool = True) -> tuple[Path, Path]:
        figures_dir = self.report_root / "figures"
        tables_dir = self.report_root / "tables"
        figures_dir.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(parents=True, exist_ok=True)

        allowed = set(selected_figures or [])
        source_figures = sorted((self.results_root / "figures").glob("*.png"))
        if allowed:
            source_figures = [src for src in source_figures if src.name in allowed]
        for src in source_figures:
            shutil.copy2(src, figures_dir / src.name)

        for src in sorted((self.root / "docs" / "screenshots").glob("*.png")):
            shutil.copy2(src, figures_dir / src.name)

        for name in ["performance_summary.csv", "final_state_summary.csv"]:
            src = self.results_root / name
            if src.exists():
                shutil.copy2(src, tables_dir / name)

        tex_path = self.report_root / "internal_external_mixing_report.tex"
        tex_path.write_text(self._build_tex([src.name for src in source_figures]), encoding="utf-8")
        pdf_path = tex_path.with_suffix(".pdf")
        self.last_backend_message = ""
        if prefer_latex and (shutil.which("xelatex") or shutil.which("tectonic")):
            try:
                self._compile(tex_path)
                self.last_backend_message = "PDF generated with LaTeX backend."
            except Exception as exc:
                self._compile_builtin_pdf(pdf_path, [src.name for src in source_figures])
                self.last_backend_message = (
                    "LaTeX backend failed; generated the PDF with the built-in offline backend instead.\n"
                    f"Original LaTeX error: {exc}\n\n{self.dependency_help_text()}"
                )
        else:
            self._compile_builtin_pdf(pdf_path, [src.name for src in source_figures])
            self.last_backend_message = (
                "No LaTeX backend was found; generated the PDF with the built-in offline backend.\n"
                "For editable .tex compilation, install the optional LaTeX dependency pack.\n\n"
                f"{self.dependency_help_text()}"
            )
        return tex_path, tex_path.with_suffix(".pdf")

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))

    def _build_tex(self, selected_figures: list[str]) -> str:
        rows = self._read_csv(self.results_root / "final_state_summary.csv")
        perf_rows = self._read_csv(self.results_root / "performance_summary.csv")

        table_rows = "\n".join(self._final_state_rows(rows)) or (
            r"\multicolumn{6}{c}{尚未生成 final_state_summary.csv。}\\"
        )
        runtime_rows = "\n".join(self._runtime_rows(perf_rows)) or (
            r"\multicolumn{4}{c}{尚未生成 performance_summary.csv。}\\"
        )
        figure_blocks = "\n".join(self._figure_blocks(selected_figures))
        screenshot_blocks = "\n".join(self._screenshot_blocks())

        return rf"""\documentclass[11pt]{{ctexart}}
\usepackage[a4paper,margin=2.2cm]{{geometry}}
\usepackage{{amsmath,amssymb,booktabs,graphicx,float,hyperref}}
\hypersetup{{colorlinks=true,linkcolor=blue,urlcolor=blue}}
\title{{SCRAM internal / external mixing 对比报告}}
\author{{SCRAM BoxApp}}
\date{{\today}}

\begin{{document}}
\maketitle

\section{{报告目的}}
SCRAM 的核心用途是模拟按粒径和组成解析的气溶胶混合状态，尤其是 externally mixed particles 的演化。本报告围绕论文中的 internal mixing 与 external mixing 假设对比：internal mixing 把同一粒径内的颗粒视为具有平均组成，external mixing 则继续区分不同组成类别，因此能够输出混合颗粒比例和不同粒径中的组成差异。

\section{{实验设置}}
当前 GUI 的“混合假设”字段会生成两组可复现实验：\texttt{{INTERNAL\_MIXING}} 使用单一组成区间，\texttt{{EXTERNAL\_MIXING}} 使用组成区间网格来跟踪混合状态。Greater Paris 参考案例遵循 Zhu et al. (2015) 的场景设计：A 为排放，B 增加碰并，C 增加冷凝/蒸发，D 同时包含排放、碰并、冷凝/蒸发和成核。

\section{{终态对比}}
\begin{{table}}[H]
\centering
\begin{{tabular}}{{llrrrr}}
\toprule
案例 & 混合假设 & 终态质量 & 终态数量 & 相对 external 质量差 & 相对 external 数量差 \\
\midrule
{table_rows}
\bottomrule
\end{{tabular}}
\caption{{internal 与 external mixing 终态结果对比}}
\end{{table}}

\section{{运行性能}}
\begin{{table}}[H]
\centering
\begin{{tabular}}{{llrr}}
\toprule
案例 & 混合假设 & wallclock (s) & 步数 \\
\midrule
{runtime_rows}
\bottomrule
\end{{tabular}}
\caption{{真实运行时间与积分步数}}
\end{{table}}

\section{{结果图}}
{figure_blocks}

\section{{GUI 截图}}
{screenshot_blocks}

\section{{结果解读}}
如果 internal 与 external 的总质量、总数量接近，说明总体守恒和宏观演化一致；如果 external 的混合颗粒比例、各粒径 mixed/unmixed 质量分布发生明显变化，则说明混合状态假设会影响组成层面的解释。external mixing 通常需要更多状态变量和更多计算时间，这与论文中关于运行成本的讨论一致。

\end{{document}}
"""

    def _final_state_rows(self, rows: list[dict[str, str]]) -> list[str]:
        output: list[str] = []
        for row in rows:
            case_label = self._case_label(row.get("case_name", "case")).replace("_", r"\_")
            scheme_label = self._scheme_label(row.get("scheme", "")).replace("_", r"\_")
            mass_diff = self._float_from_any(
                row,
                "relative_difference_vs_external_mass",
                "relative_difference_vs_nearest_mass",
                default=0.0,
            )
            number_diff = self._float_from_any(
                row,
                "relative_difference_vs_external_number",
                "relative_difference_vs_nearest_number",
                default=0.0,
            )
            output.append(
                f"{case_label} & {scheme_label} & {self._float(row.get('final_total_mass')):.4f} & "
                f"{self._float(row.get('final_total_number')):.4e} & {100.0 * mass_diff:.2f}\\% & "
                f"{100.0 * number_diff:.2f}\\% \\\\"
            )
        return output

    def _runtime_rows(self, rows: list[dict[str, str]]) -> list[str]:
        output: list[str] = []
        for row in rows:
            case_label = self._case_label(row.get("case_name", "case")).replace("_", r"\_")
            scheme_label = self._scheme_label(row.get("scheme", "")).replace("_", r"\_")
            output.append(
                f"{case_label} & {scheme_label} & {self._float(row.get('wallclock')):.2f} & "
                f"{int(self._float(row.get('total_steps')))} \\\\"
            )
        return output

    def _figure_blocks(self, selected_figures: list[str]) -> list[str]:
        captions = {
            "final_mass_comparison.png": "终态总质量对比",
            "final_number_comparison.png": "终态总数量对比",
            "internal_vs_external_mixing_logic.png": "internal 与 external mixing 假设示意",
        }
        blocks: list[str] = []
        for name in selected_figures:
            caption = captions.get(name, name.replace("_", " ").replace(".png", ""))
            caption = caption.replace("_", r"\_")
            blocks.append(
                rf"\begin{{figure}}[H]\centering\includegraphics[width=0.88\linewidth]{{figures/{name}}}\caption{{{caption}}}\end{{figure}}"
            )
        return blocks

    def _screenshot_blocks(self) -> list[str]:
        screenshots = [
            ("main_zh.png", "GUI 中文主窗口"),
            ("main_en.png", "GUI English 主窗口"),
            ("config_setup_panel.png", "实验设置与结构编辑"),
            ("running_state.png", "运行监控面板"),
            ("results_view.png", "结果分析面板"),
            ("report_panel.png", "报告中心"),
        ]
        blocks: list[str] = []
        for name, caption in screenshots:
            if (self.root / "docs" / "screenshots" / name).exists():
                blocks.append(
                    rf"\begin{{figure}}[H]\centering\includegraphics[width=0.88\linewidth]{{figures/{name}}}\caption{{{caption}}}\end{{figure}}"
                )
        return blocks

    def _case_label(self, case_name: str) -> str:
        labels = {
            "coag_only": "碰并教学案例",
            "coag_cond": "碰并 + 冷凝教学案例",
            "coag_cond_nucl": "碰并 + 冷凝 + 成核教学案例",
            "baseline12h": "12 小时基准案例",
            "gmd_hazy_condensation": "GMD hazy 冷凝验证",
            "gmd_hazy_coag_cond": "GMD hazy 碰并 + 冷凝验证",
            "gmd_paris_emission_only": "Greater Paris 场景 A",
            "gmd_paris_coagulation": "Greater Paris 场景 B",
            "gmd_paris_condensation": "Greater Paris 场景 C",
            "gmd_paris_full": "Greater Paris 场景 D",
        }
        return labels.get(case_name, case_name)

    def _scheme_label(self, scheme: str) -> str:
        labels = {
            "INTERNAL_MIXING": "internal mixing",
            "EXTERNAL_MIXING": "external mixing",
            "DETERMINISTIC_NEAREST": "deterministic nearest",
            "LEGACY": "legacy",
        }
        return labels.get(scheme, scheme.lower())

    def _float_from_any(self, row: dict[str, str], *keys: str, default: float) -> float:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return self._float(value)
        return default

    def _float(self, value: str | None) -> float:
        try:
            return float(value or 0.0)
        except ValueError:
            return 0.0

    def _compile(self, tex_path: Path) -> None:
        if shutil.which("xelatex"):
            for idx in (1, 2):
                log_path = self.report_root / f"xelatex_pass_{idx}.log"
                with log_path.open("w", encoding="utf-8", errors="replace") as handle:
                    result = subprocess.run(
                        ["xelatex", "-interaction=nonstopmode", tex_path.name],
                        cwd=self.report_root,
                        check=False,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                    )
                if result.returncode != 0:
                    raise RuntimeError(f"xelatex failed on pass {idx}. {self._log_tail(log_path)}")
        elif shutil.which("tectonic"):
            log_path = self.report_root / "tectonic.log"
            with log_path.open("w", encoding="utf-8", errors="replace") as handle:
                result = subprocess.run(
                    ["tectonic", tex_path.name],
                    cwd=self.report_root,
                    check=False,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                )
            if result.returncode != 0:
                raise RuntimeError(f"tectonic failed. {self._log_tail(log_path)}")
        else:
            raise RuntimeError("No TeX compiler found. Install xelatex or tectonic to generate PDF reports.")
        if not tex_path.with_suffix(".pdf").exists():
            raise RuntimeError(f"Report compiler finished but did not create {tex_path.with_suffix('.pdf')}.")

    def _log_tail(self, path: Path, lines: int = 30) -> str:
        if not path.exists():
            return f"Log file was not written: {path}"
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(content[-lines:])
        return f"See {path}\n{tail}"

    def dependency_help_text(self) -> str:
        dependency_candidates = [
            Path(sys.executable).resolve().parent / "report_dependencies",
            self.root.parent / "report_dependencies",
            self.root / "report_dependencies",
            self.root / "dist" / "windows" / "dependencies",
        ]
        dependencies_dir = next((path for path in dependency_candidates if path.exists()), dependency_candidates[-1])
        return (
            "LaTeX repair steps:\n"
            f"1. Open the dependency folder if it exists: {dependencies_dir}\n"
            "2. Run basic-miktex-*.exe or MiKTeX installer as administrator, choose a full or default installation, "
            "and allow missing packages to be installed automatically.\n"
            "3. Restart SCRAM BoxApp, run the experiment again if needed, then click Generate Report.\n"
            "4. If you only need a PDF, no LaTeX repair is required because the built-in offline PDF backend is available."
        )

    def _compile_builtin_pdf(self, pdf_path: Path, selected_figures: list[str]) -> None:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        font = self._report_font()
        final_rows = self._read_csv(self.results_root / "final_state_summary.csv")
        perf_rows = self._read_csv(self.results_root / "performance_summary.csv")
        with PdfPages(pdf_path) as pdf:
            self._pdf_text_page(
                pdf,
                "SCRAM internal / external mixing 对比报告",
                [
                    "本报告由 SCRAM BoxApp 内置离线 PDF 后端生成，不依赖 LaTeX。",
                    "核心目的：对比 internal mixing 与 external mixing 两种气溶胶混合假设。",
                    "internal mixing 将同一粒径段内颗粒视为平均组成；external mixing 保留粒径和组成网格，可分析 mixed / unmixed 颗粒比例。",
                ],
                font,
            )
            self._pdf_table_page(pdf, "终态结果对比", final_rows, ["case_name", "scheme", "final_total_mass", "final_total_number"], font)
            self._pdf_table_page(pdf, "运行性能", perf_rows, ["case_name", "scheme", "wallclock", "total_steps"], font)
            for figure_name in selected_figures:
                figure_path = self.results_root / "figures" / figure_name
                if figure_path.exists():
                    self._pdf_image_page(pdf, figure_path, figure_name, font)
            for screenshot in sorted((self.root / "docs" / "screenshots").glob("*.png")):
                self._pdf_image_page(pdf, screenshot, f"GUI screenshot: {screenshot.name}", font)
        if not pdf_path.exists():
            raise RuntimeError(f"Built-in PDF backend did not create {pdf_path}.\n\n{self.dependency_help_text()}")

    def _pdf_text_page(self, pdf: PdfPages, title: str, paragraphs: list[str], font: FontProperties | None) -> None:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor("white")
        fig.text(0.08, 0.92, title, fontsize=20, fontproperties=font, weight="bold")
        y = 0.82
        for paragraph in paragraphs:
            for line in textwrap.wrap(paragraph, width=52):
                fig.text(0.08, y, line, fontsize=12, fontproperties=font)
                y -= 0.035
            y -= 0.025
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _pdf_table_page(
        self,
        pdf: PdfPages,
        title: str,
        rows: list[dict[str, str]],
        columns: list[str],
        font: FontProperties | None,
    ) -> None:
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.set_title(title, fontsize=18, fontproperties=font, pad=18)
        if rows:
            table_rows = [[row.get(column, "") for column in columns] for row in rows[:12]]
        else:
            table_rows = [["No data"] + [""] * (len(columns) - 1)]
        table = ax.table(cellText=table_rows, colLabels=columns, cellLoc="center", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.6)
        for cell in table.get_celld().values():
            if font is not None:
                cell.get_text().set_fontproperties(font)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _pdf_image_page(self, pdf: PdfPages, image_path: Path, title: str, font: FontProperties | None) -> None:
        image = plt.imread(image_path)
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        fig.patch.set_facecolor("white")
        ax.imshow(image)
        ax.axis("off")
        ax.set_title(title, fontsize=14, fontproperties=font, pad=10)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _report_font(self) -> FontProperties | None:
        candidates = [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simsun.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        ]
        for path in candidates:
            if path.exists():
                return FontProperties(fname=str(path))
        return None
