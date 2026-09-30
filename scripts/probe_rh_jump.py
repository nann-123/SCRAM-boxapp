#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RH 跳变取证（台账 Q-06 / undobug U-16）。

背景：2026-09-12 在 1.1 核上扫 RH（0.99→0.999）发现 **RH=0.995 处约 2.5% 的终态质量跳变**
（外混质量 35.1567→36.0418，粒子数恒 3.44653e10）。当时归因"isorropia regime 切换"被人工
复核推翻 —— isorropia 的 DRH 常数是 0.7997/0.69/0.6183，源码里没有 0.995 这个阈值，
台账总则因此规定该条"不得以 clean 结案"。

本脚本重建最小取证：同一配置只改相对湿度，在 0.995 两侧细扫，逐点记录终态质量/粒子数/
步数，自动定位相邻点间最大的相对跳变。**只采行为证据**（跳变是否存在、位置与宽度、
在 1.2 上是否复现）—— 归因仍需在内核里 dump isorropia 的 flag/regime，那是下一步。

在 Linux 侧跑（Windows 运行时是 1.1，历史跳变也是 1.1 观测；1.2 是否复现本身就是要回答的问题）：
  python3 scripts/probe_rh_jump.py                    # 默认 gmd_paris_condensation，1 h，0.995 两侧细扫
  python3 scripts/probe_rh_jump.py --hours 12         # 与历史口径一致跑 12 h
  python3 scripts/probe_rh_jump.py --template gmd_paris_full

产出：install_logs/rh_jump_<时间戳>/result.json + 每个测点的 run.log/report.txt/cfg 存档。
判读：若最大相邻跳变 ≥ 1% ⇒ 跳变在当前核仍存在，把 result.json 交给人工归因；
      若全程平滑（< 1%）⇒ 1.1 上的跳变未在 1.2 复现，可作为"重新定性"的证据（但归因仍待补）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 历史：0.995 处跳变（1.1 核，2026-09-12）；两侧细扫 + 粗点锚定
DEFAULT_RH_LIST = (
    0.99, 0.994, 0.9945,
    0.9949, 0.99495, 0.99497, 0.99499,
    0.995, 0.99501, 0.99503, 0.99505, 0.9951,
    0.996, 0.999,
)
JUMP_THRESHOLD = 0.01  # 相邻测点终态质量相对差 ≥1% 记为跳变


def main() -> int:
    parser = argparse.ArgumentParser(description="RH 跳变取证扫描（Q-06）")
    parser.add_argument("--template", default="gmd_paris_condensation",
                        help="基线模板（历史跳变在冷凝工况观测；默认 gmd_paris_condensation）")
    parser.add_argument("--scheme", default="EXTERNAL_MIXING",
                        choices=("INTERNAL_MIXING", "EXTERNAL_MIXING"))
    parser.add_argument("--hours", type=float, default=1.0,
                        help="每个测点的模拟时长（默认 1 h 冒烟；对齐历史用 12）")
    parser.add_argument("--rh-list", nargs="*", type=float, default=list(DEFAULT_RH_LIST))
    parser.add_argument("--out", default=None, help="结果目录（默认 install_logs/rh_jump_<时间戳>）")
    args = parser.parse_args()

    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    run_service = RunService(ROOT)
    if not run_service.executable_available():
        print("!! 找不到可用的 ProgramSCRAM —— 本脚本在装好运行时的 Linux 侧跑", file=sys.stderr)
        print("   " + run_service.last_runtime_error(), file=sys.stderr)
        return 2
    template_service = TemplateService(ROOT)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else ROOT / "install_logs" / f"rh_jump_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    base = template_service.load_template(args.template)
    # 2026-09-30：案例预设删除后，时长就是 cfg 里的值本身（原 explicit_keys 保护不再需要）。
    base["scalars"]["final_time_hours"] = float(args.hours)

    rows = []
    for rh in args.rh_list:
        data = json.loads(json.dumps(base))
        data["scalars"]["humidity"] = float(rh)
        case_name = f"rh_{rh:.5f}"
        prepared = run_service.prepare_run(data, case_name, args.scheme)
        started = time.perf_counter()
        result = run_service.run_prepared(prepared)
        elapsed = time.perf_counter() - started

        run_root = Path(prepared["run_root"])
        archive = out_dir / case_name
        archive.mkdir(parents=True, exist_ok=True)
        for name in ("run.log", "report.txt"):
            source = run_root / "logs" / name
            if source.exists():
                shutil.copy2(source, archive / name)
        shutil.copy2(Path(prepared["config_path"]), archive / "config.cfg")

        rows.append({
            "rh": float(rh),
            "status": result.get("status"),
            "final_mass": result.get("final_mass"),
            "final_number": result.get("final_number"),
            "total_steps": result.get("total_steps"),
            "wallclock_seconds": round(elapsed, 3),
        })
        print(f"  RH={rh:<9.5f} status={result.get('status'):6s} "
              f"final_mass={result.get('final_mass')} steps={result.get('total_steps')} ({elapsed:.1f}s)")

    # 相邻测点差分，定位最大跳变
    jumps = []
    for prev, curr in zip(rows, rows[1:]):
        mass_a, mass_b = prev["final_mass"], curr["final_mass"]
        if mass_a and mass_b and abs(mass_a) > 0:
            jumps.append({
                "rh_low": prev["rh"], "rh_high": curr["rh"],
                "mass_low": mass_a, "mass_high": mass_b,
                "relative_delta": abs(mass_b - mass_a) / abs(mass_a),
            })
    max_jump = max(jumps, key=lambda item: item["relative_delta"], default=None)
    verdict = "no-jump-found" if not max_jump or max_jump["relative_delta"] < JUMP_THRESHOLD else "jump-persists"

    summary = {
        "schema": "scram-rh-jump/1",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "template": args.template,
        "scheme": args.scheme,
        "hours": args.hours,
        "rh_list": list(args.rh_list),
        "threshold_relative_delta": JUMP_THRESHOLD,
        "history": "Q-06：2026-09-12 于 1.1 核 gmd_paris_condensation 观测 RH=0.995 处 ~2.5% 质量跳变；"
                   "归因 isorropia 阈值已被复核推翻（源码无 0.995 常数），不得以 clean 结案",
        "max_jump": max_jump,
        "verdict": verdict,
        "rows": rows,
    }
    (out_dir / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("")
    if verdict == "jump-persists":
        print(f"判定：jump-persists —— 最大相邻跳变 {max_jump['relative_delta']:.4%} "
              f"位于 RH {max_jump['rh_low']} → {max_jump['rh_high']}（≥ {JUMP_THRESHOLD:.0%}）。")
        print("      跳变在当前核仍存在 ⇒ 保持'未解释'定性，下一步在内核里 dump isorropia flag/regime 归因。")
    else:
        print(f"判定：no-jump-found —— 全程相邻差 < {JUMP_THRESHOLD:.0%}，1.1 的跳变未在当前核复现。")
        print("      可作为重新定性的证据提交台账，但归因说明仍需补（历史跳变只在 1.1 观测过）。")
    print(f"明细已写入 {out_dir / 'result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
