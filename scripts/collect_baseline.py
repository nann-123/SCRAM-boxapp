#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""1.2 数值基线采集（台账 E3 / undobug U-12）。

目的：内核升到 SCRAM1.2（且 2026-09-29 又修了初始化三处）之后，1.1 时代的一切基线
数字作废。本脚本用当前内核对出厂 GMD 模板重采一份最小基线，落成可提交的 JSON，
作为此后"是否回归"的对照尺子。作者原文依据（UPDATE_SCRAM1.2.md）：
  "Kn公式和密度修正会改变凝结结果，不能把当前输出当成SCRAM1.1逐位复现。"

只在 Linux 侧跑（Windows 运行时仍是 1.1，采出来的不是 1.2 基线）：
  python3 scripts/collect_baseline.py                 # 4 个 GMD 模板 × 内外两臂
  python3 scripts/collect_baseline.py --hours 1       # 缩短时长冒烟（默认用模板预设 12 h）
  python3 scripts/collect_baseline.py --repeat-check  # 先对 emission_only 外混臂跑两遍验证可复现

产出：
  --out（默认 docs/baseline_scram12.json）—— 基线本体，随仓库提交；
  install_logs/baseline_<时间戳>/ —— 每次运行的 run.log / report.txt / cfg 存档（已 gitignore，
  仅为溯源保留；基线 JSON 里记了它的路径）。

指标（每个 模板×混合臂 一行）：初始总质量/粒子数（模板值）、终态质量/粒子数、步数、
三个过程计数（Mass Cond / Nub Coag / Nub Nucl，取自 report.txt）、total_water（report.txt
若含）、异常标记数（report/run.log 里 orphan/nonfinite/NaN/Infinity 行数）、wallclock。
JSON 同时记录内核 md5、runtime 清单、git 提交、主机与时间 —— 基线必须能回答"是用哪个核采的"。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 只采 4 个 GMD 模板（用户指定；teaching 基座不在基线口径内）
GMD_TEMPLATES = (
    "gmd_paris_emission_only",
    "gmd_paris_coagulation",
    "gmd_paris_condensation",
    "gmd_paris_full",
)
SCHEMES = ("INTERNAL_MIXING", "EXTERNAL_MIXING")

# 项目共享源码树（"项目核"的源码本体；Windows/Linux 同一路径，与暂存副本无关）。
# 双平台对照的"同一份源码"判据以此处指纹为准 —— 暂存运行时的 manifest 在 Linux 侧
# 不带 source 子树（历史缺口，runtime_manifest.source_sha256 会是空串）。
SOURCE_TREE = ROOT / "core" / "executables_or_wrappers" / "runtime" / "windows" / "source" / "SCRAM1.2"

# report.txt 的计数都挤在同一行（实测格式）：
#   "Nub Nucl 0.000000E+00  Nub Coag 0.000000E+00 Mass Cond 0.000000  n_emis 2.701633E+08"
# 所以必须取 token 后面**紧跟**的那个数，而不是行末最后一个数（否则全抓成 n_emis）。
_NUM = r"([-+]?\d*\.?\d+(?:[eEdD][-+]?\d+)?)"
_REPORT_TOKENS = {
    "nub_nucl": re.compile(r"Nub\s+Nucl\s+" + _NUM),
    "nub_coag": re.compile(r"Nub\s+Coag\s+" + _NUM),
    "mass_cond": re.compile(r"Mass\s+Cond\s+" + _NUM),
    "total_water": re.compile(r"total_water\s+" + _NUM),
}
_ANOMALY_RE = re.compile(r"orphan|nonfinite|nan|infinity", re.IGNORECASE)


def _to_float(text: str) -> float | None:
    try:
        return float(text.replace("d", "e").replace("D", "E"))
    except ValueError:
        return None


def parse_report_counters(text: str) -> dict[str, float | None]:
    counters: dict[str, float | None] = {key: None for key in _REPORT_TOKENS}
    for line in text.splitlines():
        for key, pattern in _REPORT_TOKENS.items():
            if counters[key] is None:
                match = pattern.search(line)
                if match:
                    counters[key] = _to_float(match.group(1))
    return counters


def count_anomalies(*texts: str) -> int:
    return sum(1 for text in texts for line in text.splitlines() if _ANOMALY_RE.search(line))


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compiler_versions() -> dict[str, str | None]:
    """记录实际编译器版本（gfortran/gcc -dumpversion；不在 PATH 时记 None）。"""
    versions: dict[str, str | None] = {}
    for name in ("gfortran", "gcc"):
        try:
            completed = subprocess.run(
                [name, "-dumpversion"], capture_output=True, text=True, check=True
            )
            versions[name] = completed.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            versions[name] = None
    return versions


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — 基线允许在无 git 环境采集
        return ""


def collect_one(run_service, template_service, config_model, template_id: str, scheme: str,
                hours: float | None, archive_dir: Path) -> dict:
    data = template_service.load_template(template_id)
    if hours is not None:
        # 2026-09-30：案例预设删除后，时长就是 cfg 里的值本身，不再需要 explicit_keys 保护。
        data["scalars"]["final_time_hours"] = float(hours)
    initial_mass = sum(sum(record["bin_values"]) for record in data["species_records"])
    initial_number = sum(float(value) for value in data["init_bin_number"])

    case_name = f"baseline_{template_id}"
    prepared = run_service.prepare_run(data, case_name, scheme)
    result = run_service.run_prepared(prepared)

    archive = archive_dir / f"{template_id}_{scheme.lower()}"
    archive.mkdir(parents=True, exist_ok=True)
    for name in ("run.log", "report.txt"):
        source = Path(prepared["run_root"]) / "logs" / name
        if source.exists():
            (archive / name).write_bytes(source.read_bytes())
    (archive / "config.cfg").write_bytes(Path(prepared["config_path"]).read_bytes())

    report_path = Path(prepared["run_root"]) / "logs" / "report.txt"
    log_path = Path(prepared["run_root"]) / "logs" / "run.log"
    report_text = report_path.read_text(encoding="utf-8", errors="replace") if report_path.exists() else ""
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""

    row = {
        "template": template_id,
        "scheme": scheme,
        "hours": float(prepared["total_sim_seconds"]) / 3600.0,
        "initial_total_mass": initial_mass,
        "initial_total_number": initial_number,
        "final_mass": result.get("final_mass"),
        "final_number": result.get("final_number"),
        "total_steps": result.get("total_steps"),
        "status": result.get("status"),
        "wallclock_seconds": round(float(result.get("wallclock", 0.0)), 3),
        "anomaly_lines": count_anomalies(report_text, log_text),
    }
    row.update(parse_report_counters(report_text))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="SCRAM1.2 数值基线采集（Linux 侧）")
    parser.add_argument("--out", default=str(ROOT / "docs" / "baseline_scram12.json"),
                        help="基线 JSON 输出路径（默认 docs/baseline_scram12.json，随仓库提交；平台记在 JSON 里）")
    parser.add_argument("--hours", type=float, default=None,
                        help="覆盖模板预设时长（默认 12 h）；冒烟时可给 --hours 1")
    parser.add_argument("--templates", nargs="*", default=list(GMD_TEMPLATES))
    parser.add_argument("--repeat-check", action="store_true",
                        help="先把 gmd_paris_emission_only 外混臂跑两遍，验证同配置重复出同值")
    args = parser.parse_args()

    from app.config_binding.config_model import ConfigModel
    from app.services.run_service import RunService
    from app.services.template_service import TemplateService

    run_service = RunService(ROOT)
    if not run_service.executable_available():
        print("!! 找不到可用的 ProgramSCRAM —— 本脚本只能在装好 1.2 运行时的 Linux 侧跑", file=sys.stderr)
        print("   " + run_service.last_runtime_error(), file=sys.stderr)
        return 2
    executable = run_service.default_executable()

    template_service = TemplateService(ROOT)
    config_model = ConfigModel(ROOT)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_dir = ROOT / "install_logs" / f"baseline_{stamp}"
    archive_dir.mkdir(parents=True, exist_ok=True)

    repeat_info: dict = {"performed": False}
    if args.repeat_check:
        rows = [
            collect_one(run_service, template_service, config_model, "gmd_paris_emission_only",
                        "EXTERNAL_MIXING", args.hours, archive_dir / f"repeat{index}")
            for index in (1, 2)
        ]
        keys = ("final_mass", "final_number", "total_steps")
        identical = all(rows[0][key] == rows[1][key] for key in keys)
        repeat_info = {"performed": True, "identical": identical, "keys": list(keys),
                       "runs": [{key: row[key] for key in keys} for row in rows]}
        print(f"repeat-check：同配置两遍 {'逐位一致' if identical else '不一致（!!）'}：{repeat_info['runs']}")

    rows = []
    for template_id in args.templates:
        for scheme in SCHEMES:
            started = time.perf_counter()
            row = collect_one(run_service, template_service, config_model, template_id, scheme,
                              args.hours, archive_dir)
            rows.append(row)
            print(f"  {template_id:26s} {scheme:16s} status={row['status']:6s} "
                  f"final_mass={row['final_mass']} steps={row['total_steps']} "
                  f"({time.perf_counter() - started:.1f}s)")

    baseline = {
        "schema": "scram-baseline/1",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "git_commit": git_commit(),
        "kernel": {
            "executable": str(executable),
            "md5": file_md5(executable),
            "size": executable.stat().st_size,
        },
        "source_tree": {
            "root": SOURCE_TREE.relative_to(ROOT).as_posix(),
            "sha256": run_service._source_tree_hash(SOURCE_TREE),
            "note": "项目共享源码树指纹（与暂存副本无关）；双平台对照的'同一份源码'判据",
        },
        "compilers": compiler_versions(),
        "runtime_manifest": run_service.runtime_manifest(),
        "hours_override": args.hours,
        "templates": list(args.templates),
        "repeat_check": repeat_info,
        "archive_dir": str(archive_dir.relative_to(ROOT)),
        "rows": rows,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"基线已写入 {out_path}（{len(rows)} 行；运行存档在 {archive_dir}）")
    print("提示：把该 JSON 随仓库提交，此后任何内核/移植改动重跑本脚本 diff 即可判断回归。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
