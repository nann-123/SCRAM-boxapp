#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""手册 Markdown → PDF（2026-09-30）。

背景：`docs/SCRAM_BoxApp_*手册.pdf` 是 2026-05 用外部工具导出的，仓库里没有生成脚本，
正文更新后 PDF 无法同步（会以旧口径随发布包发给学生）。本脚本用**应用已有的依赖**
（matplotlib 的 PdfPages + 微软雅黑，与 `report_service` 的内置离线 PDF 后端同一条路）
把手册从 Markdown 重新渲染成 PDF，不需要 pandoc / LaTeX / wkhtmltopdf。

用法：
  python scripts/build_manual_pdf.py                      # 两本手册都渲染
  python scripts/build_manual_pdf.py docs/xxx.md          # 指定文件

支持：标题（#/##/###）、正文段落（自动折行）、表格（等宽对齐块）、代码块、引用、
有序/无序列表，以及 `![alt](path)` 图片（按页嵌入）。不追求排版精美，
目的是**内容正确、中文不出方框、可随包分发**。
"""
from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

PAGE = (8.27, 11.69)          # A4 纵向（英寸）
MARGIN = 0.08                 # 页边距（比例）
WRAP = 52                     # 每行字符数（中文按 2 计宽，见 _display_width）
FONT_SIZE = 9.0
LINE_H = 0.018                # 行高（页面高度比例）
IMG_RE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)\s*$")


def find_cjk_font() -> FontProperties | None:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"),
                 Path("C:/Windows/Fonts/simsun.ttc"),
                 Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                 Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")):
        if path.exists():
            return FontProperties(fname=str(path))
    return None


def _display_width(text: str) -> int:
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _wrap(text: str, width: int = WRAP) -> list[str]:
    """按显示宽度折行（中文按 2 列），保留英文单词不被切断。"""
    lines, current, current_w = [], "", 0
    for token in re.findall(r"\s+|\S+", text):
        token_w = _display_width(token)
        if current and current_w + token_w > width:
            lines.append(current.rstrip())
            current, current_w = token.lstrip(), _display_width(token.lstrip())
        else:
            current += token
            current_w += token_w
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def _strip_inline(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    return text


class PageWriter:
    """把"文本块"逐页写到 PDF：每页一个 figure，写满自动翻页。"""

    def __init__(self, pdf: PdfPages, font: FontProperties | None) -> None:
        self.pdf = pdf
        self.font = font
        self.fig = None
        self.y = 1.0 - MARGIN
        self._new_page()

    def _new_page(self) -> None:
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
        self.fig = plt.figure(figsize=PAGE)
        self.fig.patch.set_facecolor("white")
        self.fig.text(MARGIN, 0.035, f"{self.pdf.get_pagecount() + 1}", fontsize=7, color="#888888")
        self.y = 1.0 - MARGIN

    def _write_line(self, text: str, size: float = FONT_SIZE, indent: float = 0.0,
                    color: str = "black", weight: str = "normal") -> None:
        if self.y < MARGIN + LINE_H:
            self._new_page()
        self.fig.text(MARGIN + indent, self.y, text, fontsize=size, fontproperties=self.font,
                      va="top", color=color, fontweight=weight)
        self.y -= LINE_H * (size / FONT_SIZE)

    def para(self, text: str, size: float = FONT_SIZE, indent: float = 0.0,
             color: str = "black", weight: str = "normal", width: int = WRAP) -> None:
        for line in _wrap(text, width):
            self._write_line(line, size=size, indent=indent, color=color, weight=weight)

    def blank(self, factor: float = 0.5) -> None:
        self.y -= LINE_H * factor

    def image(self, path: Path, alt: str) -> None:
        if not path.exists():
            self.para(f"[缺图：{path.name}]", color="#aa0000")
            return
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
        image = plt.imread(path)
        fig, ax = plt.subplots(figsize=PAGE)
        fig.patch.set_facecolor("white")
        ax.imshow(image)
        ax.axis("off")
        if alt:
            ax.set_title(alt, fontsize=10, fontproperties=self.font, pad=8)
        self.pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        self.fig = None
        self._new_page()

    def close(self) -> None:
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
            self.fig = None


def render(md_path: Path, pdf_path: Path) -> None:
    font = find_cjk_font()
    lines = md_path.read_text(encoding="utf-8").splitlines()
    base = md_path.parent
    with PdfPages(pdf_path) as pdf:
        writer = PageWriter(pdf, font)
        in_code = False
        for raw in lines:
            line = raw.rstrip()
            image = IMG_RE.match(line.strip())
            if image:
                writer.image((base / image.group("path")).resolve(), image.group("alt"))
                continue
            if line.strip().startswith("```"):
                in_code = not in_code
                writer.blank(0.3)
                continue
            if in_code:
                writer.para(line or " ", size=FONT_SIZE - 1, indent=0.02, color="#333333", width=WRAP + 6)
                continue
            if not line.strip():
                writer.blank(0.45)
                continue
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = _strip_inline(line.lstrip("#").strip())
                writer.blank(0.4 if level > 1 else 0.6)
                writer.para(title, size=FONT_SIZE + (6 - level * 1.5), weight="bold",
                            width=int(WRAP * (1.25 if level == 1 else 1.1)))
                writer.blank(0.2)
                continue
            if line.lstrip().startswith(("|", ">")):
                writer.para(_strip_inline(line), size=FONT_SIZE - 1, indent=0.02,
                            color="#444444" if line.lstrip().startswith(">") else "black",
                            width=WRAP + 10)
                continue
            writer.para(_strip_inline(line))
        writer.close()
    size_kb = pdf_path.stat().st_size // 1024
    print(f"  {md_path.name} → {pdf_path.name}（{size_kb} KB）")


def main() -> int:
    targets = [Path(arg) for arg in sys.argv[1:]] or sorted(
        ROOT.joinpath("docs").glob("SCRAM_BoxApp_*手册.md"))
    if not targets:
        print("找不到手册 md（docs/SCRAM_BoxApp_*手册.md）", file=sys.stderr)
        return 1
    print(f"渲染 {len(targets)} 本手册（matplotlib 后端，无需 pandoc/LaTeX）")
    for md_path in targets:
        render(md_path, md_path.with_suffix(".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
