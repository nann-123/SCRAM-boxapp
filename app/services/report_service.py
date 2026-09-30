from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import re
import unicodedata

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties

from app.services import deployment_paths, results_layout


SCHEME_LABELS = {
    "INTERNAL_MIXING": "internal mixing",
    "EXTERNAL_MIXING": "external mixing",
    "DETERMINISTIC_NEAREST": "deterministic nearest",
    "LEGACY": "legacy",
}


def _scheme_text(value: str) -> str:
    return SCHEME_LABELS.get(str(value).upper(), str(value).lower())


def _display_width(text: str) -> int:
    """中文/全角按 2、其余按 1 计的显示宽度（折行与列宽都用它）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in str(text))


def _wrap_display(text: str, limit: int) -> list[str]:
    """按显示宽度折行；英文按空格优先断行，中文逐字断行。"""
    lines: list[str] = []
    current = ""
    current_width = 0
    for token in re.findall(r"[A-Za-z0-9_./%µ³+\-]+|\s+|.", str(text)):
        token_width = _display_width(token)
        if token.strip() and current_width + token_width > limit and current.strip():
            lines.append(current.rstrip())
            current, current_width = "", 0
        if token.isspace() and not current:
            continue
        current += token
        current_width += token_width
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


class ReportService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.results_root = deployment_paths.user_results_root()
        # 报告落在"案例目录"里（<案例>/report/）；这里的默认值只是 set_results_root 之前的占位。
        self.report_root = deployment_paths.user_report_root()  # 占位；set_results_root 会改到 <案例>/report
        self.last_backend_message = ""

    def set_results_root(self, results_root: Path) -> None:
        """结果根 = 一个案例目录 ⇒ 报告写进该案例目录的 report/ 子目录。

        2026-09-30：原先报告固定写到全局 report/ 下的固定文件名，任何实验都覆盖同一份
        （用户反馈"不管跑什么都生成一样的 pdf"）。现在每个实验有自己的报告。
        """
        self.results_root = Path(results_root)
        self.report_root = self.results_root / "report"

    def report_stem(self) -> str:
        """报告文件名主体：<案例名>_report（案例目录名就是案例名）。"""
        name = Path(self.results_root).name or "report"
        return f"{name}_report"

    def tex_path(self) -> Path:
        return self.report_root / f"{self.report_stem()}.tex"

    def pdf_path(self) -> Path:
        return self.report_root / f"{self.report_stem()}.pdf"

    def available(self) -> bool:
        return True

    def generate(self, selected_figures: list[str] | None = None, prefer_latex: bool = True) -> tuple[Path, Path]:
        # 报告目录只放 .tex / .pdf（外加 LaTeX 后端自己的辅助文件），不建空的 figures/、tables/。
        self.report_root.mkdir(parents=True, exist_ok=True)

        allowed = set(selected_figures or [])
        source_figures = sorted(results_layout.figures_dir(self.results_root).glob("*.png"))
        if allowed:
            source_figures = [src for src in source_figures if src.name in allowed]
        # 2026-09-30（用户反馈"每个文件夹里大量 fig/csv 重复"）：报告目录**不再复制**
        # 案例里的图与表 —— 只产出 .tex 与 .pdf。
        #   · 内置 PDF 后端：需要高清图时把图**以 300 dpi 重绘到临时目录**，嵌完即删；
        #   · .tex：直接引用案例目录的图（相对路径 ../figures/…），就地编译即可；
        #   · 表格数据在 .tex 里是内联的，内置 PDF 直接读 <案例>/csv/，都不需要副本。
        tex_path = self.tex_path()
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
        return tex_path, self.pdf_path()

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))

    def _build_tex(self, selected_figures: list[str]) -> str:
        rows = self._read_csv(results_layout.case_csv_dir(self.results_root) / "final_state_summary.csv")
        perf_rows = self._read_csv(results_layout.case_csv_dir(self.results_root) / "performance_summary.csv")

        table_rows = "\n".join(self._final_state_rows(rows)) or (
            r"\multicolumn{6}{c}{尚未生成 final_state_summary.csv。}\\"
        )
        runtime_rows = "\n".join(self._runtime_rows(perf_rows)) or (
            r"\multicolumn{4}{c}{尚未生成 performance_summary.csv。}\\"
        )
        figure_blocks = "\n".join(self._figure_blocks(selected_figures))
        # 截图不再进 .tex：它们位于仓库 docs/screenshots，为它们复制一份到报告目录正是
        # "文件夹里一堆重复图片"的来源；内置 PDF 后端仍直接读仓库截图作附录。
        screenshot_blocks = ""

        return rf"""\documentclass[11pt]{{ctexart}}
\usepackage[a4paper,margin=2.2cm]{{geometry}}
\usepackage{{amsmath,amssymb,booktabs,graphicx,float,hyperref}}
\hypersetup{{colorlinks=true,linkcolor=blue,urlcolor=blue}}
\title{{SCRAM 实验报告：{self._case_label(Path(self.results_root).name)}}}
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
        # 2026-09-30：.tex 用相对路径引用案例目录的图（../figures/x.png），报告目录不放副本。
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
                rf"\begin{{figure}}[H]\centering\includegraphics[width=0.88\linewidth]{{../figures/{name}}}\caption{{{caption}}}\end{{figure}}"
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
            # 2026-09-30：案例预设已删除 ⇒ 案例名改为「模板 id / 用户实验名」，标签表以模板 id
            # 为主；旧的预设名保留在后半段，便于重开历史结果时仍能翻译。
            "tutorial_minimal": "最简单教学案例（BC + 硫酸盐）",
            "tutorial_aging": "教学案例：黑碳–硫酸盐老化",
            "gmd_hazy_condensation": "GMD hazy 冷凝验证",
            "gmd_hazy_coag_cond": "GMD hazy 碰并 + 冷凝验证",
            "gmd_paris_emission_only": "Greater Paris 场景 A",
            "gmd_paris_coagulation": "Greater Paris 场景 B",
            "gmd_paris_condensation": "Greater Paris 场景 C",
            "gmd_paris_full": "Greater Paris 场景 D",
            "coag_only": "碰并教学案例",
            "coag_cond": "碰并 + 冷凝教学案例",
            "coag_cond_nucl": "碰并 + 冷凝 + 成核教学案例",
            "baseline12h": "12 小时基准案例",
        }
        return labels.get(case_name, case_name)

    def _scheme_label(self, scheme: str) -> str:
        return _scheme_text(scheme)

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

    # ------------------------------------------------------------------
    # 内置离线 PDF 后端：A4 纵向、固定页边距、页码页脚、中文按显示宽度折行。
    # 2026-09-30 重写（用户反馈"pdf 生成好丑"）：原实现每段/每表/每图各起一页、
    # 混排横竖版、bbox_inches="tight" 让页面几何每次都不一样、表头还是英文列名。
    # ------------------------------------------------------------------
    PAGE_SIZE = (8.27, 11.69)     # A4 纵向（英寸）
    MARGIN_X = 0.085              # 左右页边距（页宽比例）
    TOP_Y = 0.90                  # 正文起始 y（页高比例）
    BOTTOM_Y = 0.075              # 页脚线
    BODY_SIZE = 10.5
    LINE_STEP = 0.0265
    TITLE_SIZE = 17.0
    HEADING_SIZE = 12.5

    FINAL_STATE_COLUMNS = (
        ("案例", "case_name", "text"),
        ("混合假设", "scheme", "scheme"),
        ("终态质量 (µg/m³)", "final_total_mass", "mass"),
        ("终态粒子数 (#)", "final_total_number", "mass"),
        ("相对外混质量差", "relative_difference_vs_external_mass", "percent"),
        ("相对外混数量差", "relative_difference_vs_external_number", "percent"),
    )
    PERFORMANCE_COLUMNS = (
        ("案例", "case_name", "text"),
        ("混合假设", "scheme", "scheme"),
        ("状态", "status", "text"),
        ("耗时 (s)", "wallclock", "seconds"),
        ("步数", "total_steps", "steps"),
        ("终态质量 (µg/m³)", "final_mass", "mass"),
        ("终态粒子数 (#)", "final_number", "mass"),
    )
    FIGURE_CAPTIONS = {
        "internal_vs_external_mixing_logic.png": "internal 与 external mixing 假设示意",
        "final_mass_comparison.png": "各案例终态总质量对比",
        "final_number_comparison.png": "各案例终态总粒子数对比",
        "runtime_comparison.png": "两臂运行耗时对比（机器墙钟时间）",
    }
    FIGURE_SUFFIX_CAPTIONS = (
        ("_total_mass.png", "总质量随时间的演化"),
        ("_total_number.png", "总粒子数随时间的演化"),
        ("_relative_mass_vs_external.png", "相对 external 臂的质量差"),
        ("_relative_number_vs_external.png", "相对 external 臂的粒子数差"),
        ("_external_mixed_fraction.png", "external 臂平均混合度随时间的演化"),
        ("_external_composition_drift.png", "距初始组成档的偏移（诊断量）"),
        ("_external_mixing_degree_by_size.png", "终态各粒径档的质量加权混合度"),
    )

    def _compile_builtin_pdf(self, pdf_path: Path, selected_figures: list[str]) -> None:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        font = self._report_font()
        # 高清图（300 dpi）重绘到临时目录：报告目录里不留任何图片副本
        rendered_dir = None
        try:
            import tempfile

            from app.services.plot_service import PlotService

            rendered_dir = Path(tempfile.mkdtemp(prefix=".render_", dir=str(pdf_path.parent)))
            PlotService(self.root).generate_all(self.results_root, figure_root=rendered_dir, dpi=300)
        except Exception as exc:  # 绘图数据缺失等：不让报告生成失败，回退案例目录的 160 dpi 图
            self.last_backend_message = f"High-resolution figure re-render skipped: {exc}"
            if rendered_dir is not None:
                shutil.rmtree(rendered_dir, ignore_errors=True)
            rendered_dir = None
        self._figure_override_dir = rendered_dir
        case_dir = Path(self.results_root)
        case_name = case_dir.name or "experiment"
        manifest = results_layout.read_manifest(case_dir)
        final_rows = self._read_csv(results_layout.case_csv_dir(case_dir) / "final_state_summary.csv")
        perf_rows = self._read_csv(results_layout.case_csv_dir(case_dir) / "performance_summary.csv")

        with PdfPages(pdf_path) as pdf:
            page = self._ReportPage(pdf, font)
            page.title(f"SCRAM 实验报告：{self._case_label(case_name)}")
            detail = [
                f"实验（案例）目录：{case_dir}",
                f"运行模式：{manifest.get('mode', 'unknown')}"
                + (f"；生成时间：{manifest.get('generated_at', '')}" if manifest.get("generated_at") else ""),
                "本报告由 SCRAM BoxApp 生成；图与表均取自该实验目录，可直接用于实验记录。",
            ]
            for line in detail:
                page.paragraph(line, size=9.5, color="#555555")
            page.spacer()

            page.heading("报告说明")
            for paragraph in (
                "SCRAM 模拟按粒径和组成解析的气溶胶，用于比较两种混合假设：internal mixing 把同一粒径段内的颗粒视为具有平均组成；"
                "external mixing 在粒径之外再区分组成，因此可以给出混合颗粒比例与各粒径段的组成差异。",
                "本报告对应上面列出的那一次实验。不同实验各自生成一份报告，互不覆盖。",
            ):
                page.paragraph(paragraph)

            page.heading("终态结果对比")
            if final_rows:
                page.table(self.FINAL_STATE_COLUMNS, final_rows)
            else:
                page.paragraph("该实验只运行了一个混合假设（没有两臂对比），因此没有终态对比表。", color="#555555")
            page.heading("运行性能")
            if perf_rows:
                page.table(self.PERFORMANCE_COLUMNS, perf_rows)
            else:
                page.paragraph("没有运行记录表。", color="#555555")

            if selected_figures:
                page.heading("结果图")
                for figure_name in selected_figures:
                    figure_path = self._figure_source(figure_name)
                    if figure_path.exists():
                        page.figure(figure_path, self._figure_caption(figure_name))

            screenshots = sorted((self.root / "docs" / "screenshots").glob("*.png"))
            if screenshots:
                page.heading("附录：界面截图")
                for screenshot in screenshots[:2]:
                    page.figure(screenshot, f"界面截图：{screenshot.name}")
            page.finish()

        self._figure_override_dir = None
        if rendered_dir is not None:
            shutil.rmtree(rendered_dir, ignore_errors=True)
        if not pdf_path.exists():
            raise RuntimeError(f"Built-in PDF backend did not create {pdf_path}.\n\n{self.dependency_help_text()}")

    def _figure_source(self, file_name: str) -> Path:
        """报告嵌入用的图：优先用本次 300 dpi 重绘版（临时目录），缺失才回退案例目录原图。"""
        rendered_dir = getattr(self, "_figure_override_dir", None)
        if rendered_dir is not None:
            candidate = Path(rendered_dir) / file_name
            if candidate.exists():
                return candidate
        return results_layout.figures_dir(self.results_root) / file_name

    def _figure_caption(self, file_name: str) -> str:
        if file_name in self.FIGURE_CAPTIONS:
            return self.FIGURE_CAPTIONS[file_name]
        for suffix, caption in self.FIGURE_SUFFIX_CAPTIONS:
            if file_name.endswith(suffix):
                return f"{Path(self.results_root).name}：{caption}"
        return file_name.replace("_", " ").replace(".png", "")

    class _ReportPage:
        """一页 A4 纵向的简易排版器：标题 / 小节 / 段落 / 表格 / 图 + 页码页脚。"""

        def __init__(self, pdf: PdfPages, font: FontProperties | None) -> None:
            self.pdf = pdf
            self.font = font
            self.index = 1
            self._fig = None
            self._y = 0.0
            # 本页栅格化分辨率：默认给矢量页一个够用的值，插图页会按"原图 1:1"重设。
            self._page_dpi = 150.0
            self._new_page()

        # --- 基础 -------------------------------------------------------
        def _new_page(self) -> None:
            if self._fig is not None:
                self._flush()
            self._fig = plt.figure(figsize=ReportService.PAGE_SIZE)
            self._fig.patch.set_facecolor("white")
            self._y = ReportService.TOP_Y
            self._page_dpi = 150.0

        def _flush(self) -> None:
            assert self._fig is not None
            self._fig.text(
                0.5, 0.04, f"SCRAM BoxApp · 第 {self.index} 页",
                ha="center", fontsize=8, color="#999999", fontproperties=self.font,
            )
            # dpi 只影响页内位图（图/截图）的栅格化分辨率：文字与线条始终是矢量。
            # 插图页会被设成"原图像素 ÷ 版面英寸"，等于把原图 1:1 嵌进 PDF（放大不糊）。
            self.pdf.savefig(self._fig, dpi=self._page_dpi)
            plt.close(self._fig)
            self._fig = None
            self.index += 1

        def _ensure(self, needed: float) -> None:
            if self._y - needed < ReportService.BOTTOM_Y:
                self._new_page()

        # --- 内容 -------------------------------------------------------
        def title(self, text: str) -> None:
            self._fig.text(ReportService.MARGIN_X, self._y, text,
                           fontsize=ReportService.TITLE_SIZE, fontproperties=self.font, weight="bold", va="top")
            self._y -= 0.055

        def heading(self, text: str) -> None:
            """只登记标题，真正落笔推迟到下一个内容块（这样标题不会孤零零留在页尾）。"""
            self._pending_heading = text

        def _flush_heading(self, block_height: float) -> None:
            text = getattr(self, "_pending_heading", None)
            # 先保证"标题（若有）+ 该内容块"整体放得下；放不下就换页，标题落在新页顶部。
            # 注意：没有待写标题时也必须做这次空间检查，否则长图/长表会溢出到页脚下面。
            self._ensure((0.10 if text else 0.0) + block_height)
            if not text:
                return
            self._pending_heading = None
            self._y -= 0.015
            self._fig.text(ReportService.MARGIN_X, self._y, text,
                           fontsize=ReportService.HEADING_SIZE, fontproperties=self.font, weight="bold", va="top")
            self._y -= 0.022
            line = plt.Line2D([ReportService.MARGIN_X, 1 - ReportService.MARGIN_X], [self._y, self._y],
                              color="#cccccc", linewidth=0.8)
            self._fig.add_artist(line)
            self._y -= 0.020

        def paragraph(self, text: str, size: float | None = None, color: str = "#111111") -> None:
            self._flush_heading(ReportService.LINE_STEP)
            for line in _wrap_display(text, 46 if size is None else 52):
                self._ensure(ReportService.LINE_STEP)
                self._fig.text(ReportService.MARGIN_X, self._y, line,
                               fontsize=size or ReportService.BODY_SIZE, fontproperties=self.font,
                               va="top", color=color)
                self._y -= ReportService.LINE_STEP
            self._y -= 0.008

        def spacer(self) -> None:
            self._y -= 0.012

        def table(self, columns, rows) -> None:
            labels = [label for label, _, _ in columns]
            body = [[ReportService._format_cell(row.get(key, ""), kind) for _, key, kind in columns] for row in rows]
            height = 0.030 * (len(body) + 1) + 0.03
            self._flush_heading(height)
            ax = self._fig.add_axes([ReportService.MARGIN_X, self._y - height, 1 - 2 * ReportService.MARGIN_X, height])
            ax.axis("off")
            widths = ReportService._column_widths(labels, body)
            table = ax.table(cellText=body, colLabels=labels, cellLoc="center", loc="upper center",
                             colWidths=widths)
            table.auto_set_font_size(False)
            table.set_fontsize(8.5)
            table.scale(1, 1.45)
            for (row_index, _col), cell in table.get_celld().items():
                cell.set_edgecolor("#dddddd")
                if row_index == 0:
                    cell.set_facecolor("#f0f4f8")
                    cell.set_text_props(weight="bold")
                elif row_index % 2 == 0:
                    cell.set_facecolor("#fafafa")
                if self.font is not None:
                    cell.get_text().set_fontproperties(self.font)
            self._y -= height + 0.02

        def figure(self, image_path: Path, caption: str) -> None:
            try:
                image = plt.imread(image_path)
            except (OSError, ValueError):
                return
            height_px, width_px = image.shape[0], image.shape[1]
            aspect = width_px / max(height_px, 1)
            box_w = 1 - 2 * ReportService.MARGIN_X
            # 一页只放一张图 ⇒ 尽量占满版面（原来只给 0.28 页高，图明显偏小）
            box_h = ReportService.BOTTOM_Y + 0.62
            draw_h = min(box_h, box_w / max(aspect, 1e-6))
            draw_w = draw_h * aspect
            # 让嵌入分辨率等于原图像素（上限 600 dpi，避免超大截图把文件撑爆）
            page_width_inch = ReportService.PAGE_SIZE[0]
            self._page_dpi = max(self._page_dpi, min(600.0, width_px / max(draw_w * page_width_inch, 1e-6)))
            self._flush_heading(draw_h + 0.03)
            # 高度没用满时把图在版心里垂直居中（一页一图，视觉上更稳）
            slack = max(0.0, (self._y - ReportService.BOTTOM_Y) - draw_h)
            self._y -= slack / 2
            left = 0.5 - draw_w / 2
            ax = self._fig.add_axes([left, self._y - draw_h, draw_w, draw_h])
            ax.imshow(image)
            ax.axis("off")
            self._y -= draw_h + 0.012
            for line in _wrap_display(caption, 60):
                self._fig.text(0.5, self._y, line, ha="center", va="top",
                               fontsize=8.5, color="#555555", fontproperties=self.font)
                self._y -= 0.020
            self._y -= 0.010

        def finish(self) -> None:
            if self._fig is not None:
                self._flush()

    @staticmethod
    def _column_widths(labels, body) -> list[float]:
        widths = []
        for index, label in enumerate(labels):
            longest = _display_width(label)
            for row in body:
                if index < len(row):
                    longest = max(longest, _display_width(str(row[index])))
            widths.append(max(longest, 6))
        total = sum(widths) or 1.0
        return [width / total for width in widths]

    @staticmethod
    def _format_cell(value: str, kind: str) -> str:
        text = str(value)
        if kind == "scheme":                      # 语义列先处理：不能先试着转数字
            return _scheme_text(text)
        if kind == "text":
            return text
        try:
            number = float(text)
        except (TypeError, ValueError):
            return text
        if kind == "percent":
            return f"{100.0 * number:+.2f}%"
        if kind == "seconds":
            return f"{number:.2f}"
        if kind == "steps":
            return str(int(number))
        if kind == "mass":
            if number == 0.0:
                return "0"
            if 0.01 <= abs(number) < 1000.0:
                return f"{number:.3f}"
            return f"{number:.3e}"
        return text

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
