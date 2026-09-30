"""结果目录布局（2026-09-30 重构，唯一来源）。

一次实验（一个"案例"）落在**一个自描述的目录**里，案例名 = 实验名（载入模板时默认取模板 id）：

    <结果根>/<案例名>/
        case.json              运行清单：模式（single/compare）、每臂的配置与实测数据
        figures/               该案例的全部图（11 张两臂 / 6 张单臂）
        csv/                   案例级汇总表：final_state_summary.csv、performance_summary.csv
        external_mixing/       臂目录（存在 = 跑过这一臂）
            run_config.cfg     该臂**真正送核**的配置（归档，可复现）
            csv/               内核写的数据 + 采集件（fractions.txt / mass_init.txt / composition_grid.json）
            logs/              run.log、report.txt
        internal_mixing/       （同上）

设计约束（都是上一版布局被吐槽的点，见 2026-09-30 重构说明）：

1. **没有 `runs/<案例>/` 那一层**：臂目录直接挂在案例目录下，路径里案例名只出现一次。
2. **没有 `compare/`、`single/` 两级模式目录**：模式是"这批结果怎么跑出来的"，
   记在 `case.json` 里，不再是路径的一部分 —— 同一实验的两种跑法写同一个案例目录，
   不会出现"同一份数字在两条目录里各存一份"。
3. **臂级不再有 figures/**：内核启动时会自建 `csv/figures/logs` 三个目录（脚手架，
   它自己只往 csv/ 写），`figures/` 由本模块在采集时删掉，图一律画在案例级 `figures/`。
4. **案例目录是"最近一次运行"的快照**：同名实验重跑会先清空案例目录（与界面
   "同名实验会覆盖历史结果"的既有约定一致），避免出现"一臂新一臂旧"的混装结果。
5. **体积控制（2026-09-30）**：内核每步还写"逐格 × 逐物种"的凝并增量诊断
   `coag_delta_mass.csv` / `coag_delta_number.csv`（实测 743 步的长案例 = 348 MB / 11 MB，
   应用与脚本都不读）。跑完即删，需要排查凝并重分布时设 `SCRAM_KEEP_COAG_DELTAS=1` 保留。
"""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST_NAME = "case.json"
FIGURES_DIRNAME = "figures"
CASE_CSV_DIRNAME = "csv"
ARM_CONFIG_NAME = "run_config.cfg"
TIMESTEP_CSV = "timestep_summary.csv"

LAYOUT_VERSION = 2


def case_root(results_root: Path, case_name: str) -> Path:
    """案例目录：<结果根>/<案例名>。"""
    return Path(results_root) / str(case_name)


def manifest_path(root: Path) -> Path:
    return Path(root) / MANIFEST_NAME


def figures_dir(root: Path) -> Path:
    return Path(root) / FIGURES_DIRNAME


def case_csv_dir(root: Path) -> Path:
    """案例级汇总表目录（final_state_summary.csv / performance_summary.csv）。"""
    return Path(root) / CASE_CSV_DIRNAME


def arm_dir(root: Path, scheme: str) -> Path:
    return Path(root) / str(scheme).lower()


def arm_csv_dir(root: Path, scheme: str) -> Path:
    return arm_dir(root, scheme) / CASE_CSV_DIRNAME


def arm_logs_dir(root: Path, scheme: str) -> Path:
    return arm_dir(root, scheme) / "logs"


def arm_config_path(root: Path, scheme: str) -> Path:
    return arm_dir(root, scheme) / ARM_CONFIG_NAME


def iter_arms(root: Path) -> list[Path]:
    """列出案例目录下**真的有内核数据**的臂目录（按名字排序）。"""
    root = Path(root)
    arms = []
    if not root.is_dir():
        return arms
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if (child / CASE_CSV_DIRNAME / TIMESTEP_CSV).exists():
            arms.append(child)
    return arms


def is_case_dir(path: Path) -> bool:
    """像不像一个案例目录：有清单、有图目录、或至少有一个臂。"""
    path = Path(path)
    if not path.is_dir():
        return False
    return manifest_path(path).exists() or figures_dir(path).is_dir() or bool(iter_arms(path))


def arm_scheme_of(root: Path, arm: Path) -> str:
    """臂目录名（小写）→ 送核用的 scheme 名（大写）。"""
    name = Path(arm).name.lower()
    return name.upper()


HISTORY_DIRNAME = "history"
DEFAULT_HISTORY_KEEP = 3


def history_root(results_root: Path) -> Path:
    """旧结果快照的家：<结果根>/history/（不在案例目录里，结果页也不会把它当案例列出）。"""
    return Path(results_root) / HISTORY_DIRNAME


def snapshot_case_dir(root: Path) -> Path | None:
    """把已有结果的案例目录**整目录搬到** <结果根>/history/<案例名>_<时间戳>/ 后重建空目录。

    同名实验重跑不再直接删除旧结果（用户反馈："要用就不删了吧"）；搬运是同盘 rename，
    不复制数据、不额外占空间。没有旧结果的目录直接重建，返回 None。
    """
    import os
    import shutil
    from datetime import datetime

    root = Path(root)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return None
    if not any(root.iterdir()):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = history_root(root.parent) / f"{root.name}_{stamp}"
    index = 2
    while target.exists():
        target = history_root(root.parent) / f"{root.name}_{stamp}-{index}"
        index += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(root, target)          # 同盘 rename，原子且不复制
    except OSError:
        shutil.move(str(root), str(target))
    root.mkdir(parents=True, exist_ok=True)
    prune_history(root.parent, root.name)
    return target


def prune_history(results_root: Path, case_name: str, keep: int | None = None) -> None:
    """每个实验只保留最近 keep 份快照（默认 3，可用 SCRAM_CASE_HISTORY_KEEP 调整，0=不留）。"""
    import os
    import shutil

    if keep is None:
        try:
            keep = int(os.environ.get("SCRAM_CASE_HISTORY_KEEP", DEFAULT_HISTORY_KEEP))
        except ValueError:
            keep = DEFAULT_HISTORY_KEEP
    history = history_root(results_root)
    if not history.is_dir() or keep < 0:
        return
    snapshots = sorted(
        (p for p in history.iterdir() if p.is_dir() and p.name.startswith(f"{case_name}_")),
        key=lambda p: p.name,
    )
    for stale in snapshots[:-keep] if keep else snapshots:
        shutil.rmtree(stale, ignore_errors=True)


def write_manifest(root: Path, payload: dict) -> Path:
    path = manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_manifest(root: Path) -> dict:
    path = manifest_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_manifest_run(root: Path, scheme: str, patch: dict) -> None:
    """把某一臂的实测结果并入 case.json（不存在则新建骨架）。"""
    payload = read_manifest(root) or {"layout": LAYOUT_VERSION, "case_name": Path(root).name, "runs": []}
    runs = payload.setdefault("runs", [])
    entry = next((item for item in runs if str(item.get("scheme", "")).upper() == str(scheme).upper()), None)
    if entry is None:
        entry = {"scheme": str(scheme).upper()}
        runs.append(entry)
    entry.update(patch)
    write_manifest(root, payload)


def drop_empty_arm_figures(root: Path, scheme: str) -> None:
    """删掉内核脚手架留下的空 figures/（内核自建但从不写入）。"""
    candidate = arm_dir(root, scheme) / FIGURES_DIRNAME
    if candidate.is_dir() and not any(candidate.iterdir()):
        try:
            candidate.rmdir()
        except OSError:
            pass
