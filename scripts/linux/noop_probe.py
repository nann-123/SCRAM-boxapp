#!/usr/bin/env python3
"""空转探测（no-op probe）：把过程开关关掉，结果**应当**改变。

反证式判据（这是本工具与"跑一遍记 clean"的本质区别——它必须能被推翻）：

    · 关掉某开关后，终态质量/数量应明显不同；若逐位相同（相对差 < 1e-9 且步数不变），
      说明该开关在本次配置下没有起作用 → **沉默失败嫌疑**（Bug #2/#5 那一类：
      开关已开却 coag_event_rate_sum=0 / mapping_calls_step=0 / active_bins=0）。
    · 若关掉后生成配置里该开关仍是 1 → 说明设置被忽略（run_service/模板层缺陷）。

用法：

    # 默认检查三个过程开关（凝并/冷凝/成核）
    .venv/bin/python scripts/linux/noop_probe.py --template gmd_paris_full

    # 只查指定开关
    .venv/bin/python scripts/linux/noop_probe.py --template tutorial_minimal --switches with_coag

产出：install_logs/auto/noop/<模板>__<开关>/{on,off}/ （含 probe.json 与生成的 cfg 路径）
退出码：0 = 被关的开关都起作用；1 = 有空转/未生效嫌疑；2 = 运行或读取失败。
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SWITCHES = ["with_coag", "with_cond", "with_nucl"]


def schema_index() -> dict[str, tuple[int, int]]:
    """从 config_schema.json 取 key -> (line_index(0 基), subindex)。"""
    out: dict[str, tuple[int, int]] = {}
    data = json.loads((ROOT / "core" / "schema" / "config_schema.json").read_text())

    def walk(node) -> None:
        if isinstance(node, dict):
            if "key" in node and "line_index" in node:
                try:  # 部分条目（分组标记）的 line_index 不是行号，跳过
                    out[str(node["key"])] = (int(node["line_index"]), int(node.get("subindex", 0)))
                except (TypeError, ValueError):
                    pass
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return out


def cfg_switch_value(cfg_path: Path, key: str, index: dict[str, tuple[int, int]]) -> str | None:
    try:
        line_i, sub = index[key]
        line = cfg_path.read_text(errors="replace").splitlines()[line_i]
        tokens = line.split("##")[0].split()
        return tokens[sub] if len(tokens) > sub else None
    except Exception:
        return None


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def run_cell(template: str, case: str | None, overrides: dict[str, object], out: Path) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / "scripts" / "linux" / "probe_cell.py"),
           "--template", template, "--out", str(out)]
    if case:
        cmd += ["--case", case]
    for key, value in overrides.items():
        cmd += ["--set", f"{key}={value}"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def summarise(out: Path) -> dict:
    states = {}
    for row in read_rows(out / "final_state_summary.csv"):
        states[row["scheme"]] = (float(row["final_total_mass"]), float(row["final_total_number"]))
    steps, cfg = {}, {}
    for row in read_rows(out / "performance_summary.csv"):
        steps[row["scheme"]] = int(float(row["total_steps"]))
        cfg[row["scheme"]] = row.get("config_path", "")
    return {"states": states, "steps": steps, "cfg": cfg}


def rel_diff(a: float, b: float) -> float:
    base = max(abs(a), abs(b), 1e-300)
    return abs(a - b) / base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--case", default=None)
    parser.add_argument("--switches", default=",".join(DEFAULT_SWITCHES),
                        help="逗号分隔的开关键名（默认 with_coag,with_cond,with_nucl）")
    parser.add_argument("--tolerance", type=float, default=1e-9,
                        help="判定为「空转」的相对差阈值（默认 1e-9，即逐位相同）")
    args = parser.parse_args()

    index = schema_index()
    root = ROOT / "install_logs" / "auto" / "noop"
    print(f"== 空转探测：{args.template}（{args.case or args.template}）==")
    print(f"   判据：关掉开关后终态应改变；相对差 < {args.tolerance:g} 且步数不变 ⇒ 空转嫌疑")
    suspects, failures = [], []

    for switch in [s.strip() for s in args.switches.split(",") if s.strip()]:
        if switch not in index:
            print(f"  [跳过] {switch}: 不在 config_schema.json 中")
            continue
        label = f"{args.template}__{switch}"
        on_dir, off_dir = root / label / "on", root / label / "off"
        on_dir.mkdir(parents=True, exist_ok=True)
        off_dir.mkdir(parents=True, exist_ok=True)

        code_on, log_on = run_cell(args.template, args.case, {}, on_dir)
        if code_on == 2:
            failures.append(f"{switch}: 基准运行失败（退出码 2）")
            print(f"  [失败] {switch}: 基准运行失败\n{log_on[-400:]}")
            continue
        base = summarise(on_dir)

        # 基准里该开关若不是 1，说明这个模板默认就关着 → 无需反证，直接跳过
        base_val = None
        for scheme, cfg_path in base["cfg"].items():
            if cfg_path and Path(cfg_path).exists():
                base_val = cfg_switch_value(Path(cfg_path), switch, index)
                break
        if base_val not in (None, "1"):
            print(f"  [跳过] {switch}: 该模板基准值已是 {base_val}（默认关闭，无需反证）")
            continue

        code_off, log_off = run_cell(args.template, args.case, {switch: 0}, off_dir)
        if code_off == 2:
            failures.append(f"{switch}: 关闭后运行失败（退出码 2）")
            print(f"  [失败] {switch}: 关闭后运行失败（可能是关闭该过程本身不可行）\n{log_off[-300:]}")
            continue
        off = summarise(off_dir)

        off_val = None
        for scheme, cfg_path in off["cfg"].items():
            if cfg_path and Path(cfg_path).exists():
                off_val = cfg_switch_value(Path(cfg_path), switch, index)
                break
        if off_val == "1":
            suspects.append(f"{switch}: 覆写未生效（关闭后 cfg 里仍为 1）")
            print(f"  ⚠ {switch:10s} 覆写未生效：关闭后生成的 cfg 里该开关仍为 1 → 设置被忽略")
            continue

        worst_mass = worst_number = 0.0
        step_changed = False
        for scheme, (mass_on, num_on) in base["states"].items():
            pair = off["states"].get(scheme)
            if not pair:
                continue
            worst_mass = max(worst_mass, rel_diff(mass_on, pair[0]))
            worst_number = max(worst_number, rel_diff(num_on, pair[1]))
            if base["steps"].get(scheme) != off["steps"].get(scheme):
                step_changed = True

        if worst_mass < args.tolerance and worst_number < args.tolerance and not step_changed:
            suspects.append(f"{switch}: 关闭后终态与步数均未变（mass Δ={worst_mass:.2e}, "
                            f"number Δ={worst_number:.2e}）→ 该开关未起作用")
            verdict = "空转嫌疑 ⚠"
        else:
            verdict = "有效"
        print(f"  {switch:10s} 基准={base_val} 关掉后={off_val}  "
              f"Δmass={worst_mass:.3e} Δnumber={worst_number:.3e} "
              f"{'步数变化' if step_changed else '步数不变'}  → {verdict}")

    if suspects:
        print("\n== 结论：发现空转/未生效嫌疑 ==")
        for item in suspects:
            print(f"  · {item}")
        print("  下一步：按 probe_backlog §4 取证（保存 cfg + 两侧 CSV），并登记台账 hypotheses")
        return 2 if failures else 1
    if failures:
        for item in failures:
            print(f"  [失败] {item}")
        return 2
    print("\n== 结论：被检查的开关都真实起作用（无反证）==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
