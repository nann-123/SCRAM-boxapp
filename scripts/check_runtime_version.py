#!/usr/bin/env python3
"""内核版本自检：确认「运行时真正会被执行的那个 ProgramSCRAM」是 SCRAM1.2 构建。

## 为什么需要这个脚本（2026-09-23 立）

SCRAM1.1 → 1.2 升级时，源码树是用 `git mv` 改的名（`source/SCRAM1.1` → `source/SCRAM1.2`），
但 Windows 侧被跟踪的发行 exe 一直是 **2026-05-15 的 1.1 构建**，而且被复制成了三份
（源码树残留 / 共享运行时 / 已打包发行版），md5 完全相同：

    aeaf4a5e74abc031e9477401db634eca

也就是说「**源码已经是 1.2、跑起来的却还是 1.1**」这种情况可以长期静默存在。
本脚本把它变成一条可机检的判据，避免重编译之后又拿错版本。

## 判据

下列字符串常量是 1.2 新增的，在 1.1 二进制里 **0 命中**（2026-09-23 实测）：

    SCRAM_REDISTRIBUTION_MODE        1.2 新增的环境变量开关
    MOVING_CENTER_DUALPIVOT          1.2 新增的 moving-center dual-pivot 重分布
    orphan mass                      1.2 新增的守恒不变量报错文本

三个全命中 ⇒ 1.2；任一缺失 ⇒ 旧核，需要用 `source/SCRAM1.2` 重新编译后覆盖运行时。

## 退出码（沿用本仓库检查脚本的通用约定）

    0 = 判定为 1.2
    3 = 判定为旧核（已知项：Windows 侧待重编译）
    1 = 连二进制都找不到（配置/打包出错）

用法：
    python scripts/check_runtime_version.py
    python scripts/check_runtime_version.py --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 1.2 独有的字符串标记（1.1 里 0 命中）
MARKERS: tuple[bytes, ...] = (
    b"SCRAM_REDISTRIBUTION_MODE",
    b"MOVING_CENTER_DUALPIVOT",
    b"orphan mass",
)


def executable_name() -> str:
    from app.services import deployment_paths

    return "ProgramSCRAM.exe" if deployment_paths.platform_name() == "windows" else "ProgramSCRAM"


def targets() -> list[tuple[str, Path]]:
    """返回 (角色说明, 路径)，按「实际会不会被跑到」排序。"""
    from app.services import deployment_paths

    name = executable_name()
    platform = deployment_paths.platform_name()
    shared = deployment_paths.shared_runtime_platform_dir(ROOT)
    return [
        ("staged (app 实际执行)", deployment_paths.runtime_platform_dir() / name),
        ("shared (仓库共享运行时)", shared / name),
        ("built-from-source (SCRAM1.2 本地构建产物)", shared / "source" / "SCRAM1.2" / name),
    ]


def probe(path: Path) -> dict:
    """读取二进制并统计 1.2 独有标记的命中次数。"""
    if not path.exists():
        return {"exists": False, "version": "missing", "hits": {}, "size": 0, "md5": ""}
    blob = path.read_bytes()
    hits = {marker.decode(): blob.count(marker) for marker in MARKERS}
    return {
        "exists": True,
        "version": "1.2" if all(count > 0 for count in hits.values()) else "1.1-or-older",
        "hits": hits,
        "size": len(blob),
        "md5": hashlib.md5(blob).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that the runtime ProgramSCRAM is a SCRAM1.2 build.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON only")
    args = parser.parse_args()

    # 中文 Windows 上 stdout 的编码可能是 GBK（尤其是被管道/重定向时），
    # 无法编码的字符（如 ⇒）会让整个检查脚本以 UnicodeEncodeError 崩掉 ——
    # 检查脚本因“打印”而失败是最没意义的失败，所以这里降级为替换符。
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

    results = [(role, path, probe(path)) for role, path in targets()]

    # 判定只看"会不会真被跑到"的前两个：staged（优先）→ shared
    running = next((r for role, _p, r in results if role.startswith("staged") and r["exists"]), None)
    if running is None:
        running = next((r for role, _p, r in results if role.startswith("shared") and r["exists"]), None)

    if args.json:
        print(json.dumps(
            {
                "verdict": running["version"] if running else "missing",
                "probes": [{"role": role, "path": str(path), **result} for role, path, result in results],
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0 if running and running["version"] == "1.2" else (3 if running else 1)

    print("== 内核版本自检（判据：SCRAM1.2 独有字符串标记）==")
    for role, path, result in results:
        if not result["exists"]:
            print(f"  [ -- ] {role}\n         {path}\n         不存在（未构建 / 未暂存，属正常）")
            continue
        flag = "OK " if result["version"] == "1.2" else "!! "
        print(f"  [{flag}] {role}\n         {path}")
        print(f"         version={result['version']}  md5={result['md5']}  size={result['size']}")
        print("         标记命中：" + "  ".join(f"{k}={v}" for k, v in result["hits"].items()))

    if running is None:
        print("\n  => 找不到任何会被执行的 ProgramSCRAM（staged / shared 都没有），退出码 1")
        print("     检查 core/executables_or_wrappers/runtime/<platform>/ 是否完整。")
        return 1

    if running["version"] == "1.2":
        print("\n  => 判定 1.2，与源码树一致，退出码 0")
        return 0

    print("\n  => 判定为【旧核】（1.1 或更早），与 source/SCRAM1.2 不一致，退出码 3")
    print("     重编译（需要 Fortran/C 工具链 + NetCDF Fortran，见 docs/windows_devkit_readme_zh.md §9）：")
    print("       在 core/executables_or_wrappers/runtime/windows/source/SCRAM1.2 下运行 SCons，")
    print("       把产出的 ProgramSCRAM(.exe) 覆盖到 core/executables_or_wrappers/runtime/<platform>/。")
    print("     Linux 侧一条命令：bash scripts/linux/build_runtime.sh")
    print("     覆盖后重跑本脚本；GUI 检测到共享运行时变化会自动重新暂存，" "强制刷新可删 %LOCALAPPDATA%\\scram_boxapp_mixing\\runtime。")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
