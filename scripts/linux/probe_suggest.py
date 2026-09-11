"""自我发现建议器：从「未覆盖格子 + 源码线索」生成下一批候选探测。

用法：

    python scripts/linux/probe_suggest.py                 # 打印优先级最高的候选探测
    python scripts/linux/probe_suggest.py --limit 5       # 只要前 5 条
    python scripts/linux/probe_suggest.py --matrix        # 只打印覆盖矩阵状态
    python scripts/linux/probe_suggest.py --mark <id> --status done|bug|clean --note "结论…"

台账是机器可读的 docs/linux_debugging/probe_ledger.json（已做过的不再重复建议）：
  cells        已执行的参数格子
  hypotheses   已执行的假设及其结论

设计意图：让 agent 每轮自己产生新假设（读源码 → 提假设 → 设计实验 → 记录结论），
而不是把固定矩阵跑完就无事可做。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 2026-09-11 统一：此前误写 docs/probe_ledger.json，与 brief/runbook/probe_backlog 指向的
# docs/linux_debugging/probe_ledger.json 分叉（人工复盘会看错文件、Windows 口径守卫也会误报）
LEDGER = ROOT / "docs" / "linux_debugging" / "probe_ledger.json"
SRC = ROOT / "core" / "executables_or_wrappers" / "runtime" / "windows" / "source" / "SCRAM1.1" / "SRC"
APP = ROOT / "app"

TEMPLATES = ["tutorial_minimal", "gmd_hazy_condensation", "gmd_hazy_coag_cond",
             "gmd_paris_emission_only", "gmd_paris_coagulation", "gmd_paris_condensation",
             "gmd_paris_full"]
OPTIONS = ["legacy", "core_conserv", "core_nogrow", "core_smallgrow"]

# 源码线索：模式 → (探测类, 假设模板, 实验设计, 预期信号)
CODE_SOURCES = [
    ("STOP 语句", r"\bSTOP\b",
     "P4 退出码/日志交叉",
     "{file} 里有 {n} 处 STOP（内部崩溃点）：构造能走到它的输入，验证 run_service 是否报 failed 且日志含崩溃关键字",
     "用对应模板/开关复现该分支，观察 status 与 run.log 关键字",
     "status=failed 且日志出现 STOP/关键字；若 status=ok 即为 Bug #8 复发"),
    ("成核模型分支", r"nucl_model",
     "P8 配置最小化差分",
     "{file} 有 {n} 处 nucl_model 分支：逐值扫描（含硬编码的 5），验证配置解析与运行",
     "对 nucl_model 取 1..6 各值跑同一模板（nucl_mode=5 用 docs/checktest/nucl_model5_test.cfg）",
     "解析失败/列错位/崩溃即命中（Bug #9 的同类）；记录哪些值被支持"),
    ("零质量阈值", r"TINYM|TINY\b|1\.d-30|1\.e-30",
     "P2 沉默失败",
     "{file} 有 {n} 处极小阈值比较：构造 mass=0/number≠0 或极端不均匀分布，检查是否静默跳过计算",
     "用零质量骨架模板跑凝并/重分配（见 Bug #2/#5 触发条件）",
     "conag_event_rate_sum/active_bins/mapping_calls_step 为 0 而开关已开 → 沉默失败"),
    ("无保护除法", r"/\s*[a-zA-Z_][a-zA-Z_0-9]*\s*\(",
     "P1 守恒与有限性",
     "{file} 有 {n} 处除法嫌疑：分母可能为 0（NaN/Inf 来源），构造边界输入",
     "挑该文件对应过程的极端配置（零值/单物种/单 bin）跑一遍",
     "has_nan/has_inf 置位或 final_* 非有限值"),
]

RULE = [
    "# 选择 probe_cell.py 的实验参数：",
    "python scripts/linux/probe_cell.py --template <模板> --case <预设> [--set 字段=值]",
    "",
]


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"cells": {}, "hypotheses": {}}


def save_ledger(data: dict) -> None:
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def scan_code() -> list[dict]:
    candidates = []
    for label, pattern, probe_class, hypothesis, design, expect in CODE_SOURCES:
        regex = re.compile(pattern)
        for path in sorted(list(SRC.rglob("*.f90")) + list(SRC.rglob("*.f"))):
            hits = [f"{path.name}:{i + 1}" for i, line in enumerate(
                path.read_text(errors="replace").splitlines()) if regex.search(line)]
            if len(hits) < 2:
                continue
            key = f"code:{label}:{path.name}"
            candidates.append({
                "id": key, "class": probe_class, "weight": len(hits),
                "hypothesis": hypothesis.format(file=path.name, n=len(hits)),
                "design": design, "expect": expect,
                "evidence": ", ".join(hits[:6]) + ("…" if len(hits) > 6 else ""),
            })
    app_hits = []
    for path in sorted(APP.rglob("*.py")):
        text = path.read_text(errors="replace")
        if re.search(r"except[^\n]*:\s*\n\s*(pass|return\s+None)", text):
            app_hits.append(path.name)
    if app_hits:
        candidates.append({
            "id": "code:静默异常:app", "class": "P2 沉默失败", "weight": len(app_hits),
            "hypothesis": f"app/ 下有 {len(app_hits)} 个文件存在静默异常分支（except 后 pass/return None）："
                          "失败被吞掉，用户看到空结果而不是报错（Bug #6 的同类）",
            "design": "逐个检查这些分支，构造触发条件并观察 GUI/日志是否提示",
            "expect": "触发后界面无提示且产物缺失 → 静默失败", "evidence": ", ".join(app_hits[:6]),
        })
    return sorted(candidates, key=lambda c: -c["weight"])


def matrix_candidates(ledger: dict) -> list[dict]:
    priority = {  # 与已知 Bug 相邻的格子优先
        ("gmd_hazy_coag_cond", "core_conserv"): 0,
        ("gmd_paris_full", "legacy"): 1,
        ("gmd_paris_full", "core_nogrow"): 2,
        ("gmd_paris_condensation", "core_nogrow"): 3,
        ("gmd_hazy_coag_cond", "core_smallgrow"): 4,
    }
    cells = []
    for template in TEMPLATES:
        for option in OPTIONS:
            key = f"{template}|{option}"
            if key in ledger.get("cells", {}):
                continue
            cells.append({
                "id": f"cell:{key}", "class": "P1/P5 覆盖矩阵",
                "weight": 100 - priority.get((template, option), 50),
                "hypothesis": f"{template} 在 {option} 核心模式下未验证（矩阵空格子）",
                "design": f"python scripts/linux/probe_cell.py --template {template} "
                          f"--case {template} --set redistribution_option={option}",
                "expect": "status=ok、守恒残差 ≤1e-6、无 NaN；异常即候选发现",
                "evidence": "docs/linux_debugging/probe_backlog.md §3 覆盖矩阵",
            })
    return sorted(cells, key=lambda c: -c["weight"])


def print_matrix(ledger: dict) -> None:
    print("模板 \\ 核心模式      " + "".join(f"{opt:>18s}" for opt in OPTIONS))
    for template in TEMPLATES:
        row = []
        for option in OPTIONS:
            mark = "✅已探" if f"{template}|{option}" in ledger.get("cells", {}) else "☐未探"
            row.append(f"{mark:>18s}")
        print(f"{template:20s}" + "".join(row))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--mark")
    parser.add_argument("--status", choices=["done", "bug", "clean"])
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    ledger = load_ledger()

    if args.matrix:
        print_matrix(ledger)
        return 0

    if args.mark:
        if not args.status:
            print("--mark 需要 --status", file=sys.stderr)
            return 2
        record = {"status": args.status, "note": args.note, "date": date.today().isoformat()}
        if args.mark.startswith("cell:"):
            ledger.setdefault("cells", {})[args.mark[5:]] = record
        else:
            ledger.setdefault("hypotheses", {})[args.mark] = record
        save_ledger(ledger)
        print(f"已登记 {args.mark} → {args.status}")
        return 0

    candidates = matrix_candidates(ledger) + scan_code()
    print(f"== 候选探测（共 {len(candidates)} 条，已排除台账里做过的）==")
    for item in candidates[:args.limit]:
        print(f"\n[{item['class']}] {item['id']}")
        print(f"  假设：{item['hypothesis']}")
        print(f"  依据：{item['evidence']}")
        print(f"  实验：{item['design']}")
        print(f"  预期/判定：{item['expect']}")
    print()
    print("\n".join(RULE))
    print("执行后用 --mark 登记，例如：")
    print("  python scripts/linux/probe_suggest.py --mark 'cell:gmd_paris_full|legacy' --status clean --note '数值一致'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
