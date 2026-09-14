#!/usr/bin/env python3
"""字段登记表对账脚本（Phase 0，只读不改）。

对照五方，把「不一致」从"要读代码才发现"变成"跑一条命令就列出来"：
  1) core/schema/config_schema.json  —— 配置字段声明
  2) core/schema/gui_fields.json      —— GUI/契约登记表（本脚本的输入）
  3) SRC/*.f90                        —— 核心到底读不读、用不用
  4) app/i18n/{zh_CN,en_US}.json       —— 标签是否两个语言都齐
  5) app/views/main_window.py         —— 界面上到底有没有这个控件

退出码（沿用 scripts/linux/check_assets.py 的约定）：
  0 = 干净        3 = 只有已登记的已知项        1 = 出现未登记的新问题

用法：python scripts/check_field_registry.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "core" / "schema" / "gui_fields.json"
SCHEMA = ROOT / "core" / "schema" / "config_schema.json"
FORTRAN_SRC = ROOT / "core" / "executables_or_wrappers" / "runtime" / "windows" / "source" / "SCRAM1.1"
MAIN_WINDOW = ROOT / "app" / "views" / "main_window.py"

known: list[str] = []      # 已在登记表里标了 known_defect 的
new: list[str] = []        # 未登记的新问题


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fortran_texts() -> dict[str, str]:
    out: dict[str, str] = {}
    for sub in ("SRC", "INC"):
        for path in (FORTRAN_SRC / sub).rglob("*"):
            if path.is_file() and path.suffix.lower() in {".f90", ".f", ".inc"}:
                out[str(path.relative_to(FORTRAN_SRC))] = path.read_text(
                    encoding="utf-8", errors="ignore")
    return out


def real_uses(name: str, text: str) -> list[tuple[int, str]]:
    """返回「真正的使用」位置 —— 排除读取语句、类型声明与注释。

    只有出现在 read(10,*) 之外、且既不是声明也不是注释的引用，才算真被使用。
    （教训一：tag_thrm 的 2 处命中里，1 处是 ModuleInitialization.f90 的
    `integer :: tag_thrm` 声明，1 处是读取行 —— 两处都不是使用。
    教训二：早期的版本漏了排除读取行，把读进来的那一行误当成"使用"。）
    """
    decl = re.compile(
        r"^\s*(integer|real|double\s+precision|logical|character)\b[^!]*::",
        re.IGNORECASE)
    read_stmt = re.compile(r"^\s*read\s*\(", re.IGNORECASE)
    pat = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not pat.search(line):
            continue
        code = line.split("!", 1)[0]
        if not pat.search(code):
            continue                      # 命中只出现在注释里
        if read_stmt.match(line):
            continue                      # 配置文件读取语句（就是"读它"本身）
        if decl.match(line) and pat.search(line.split("::", 1)[-1]):
            continue                      # 类型声明行
        hits.append((lineno, line.strip()))
    return hits


def main() -> int:
    print("== 字段登记表对账 ==")
    if not REGISTRY.exists():
        print(f"  找不到登记表：{REGISTRY}")
        return 1
    reg = load_json(REGISTRY)
    schema = load_json(SCHEMA)
    fields = reg["fields"]
    app_only = reg.get("app_only_fields", [])
    transforms = reg.get("transforms", [])
    ftext = fortran_texts()
    all_fortran = "\n".join(ftext.values())

    # 核心的 read(10,*) 清单
    read_block = ""
    disc = ftext.get("SRC\\ModuleDiscretization.f90") or ftext.get("SRC/ModuleDiscretization.f90") or ""
    for line in disc.splitlines():
        if re.search(r"read\s*\(\s*10\s*,", line):
            read_block += line + "\n"

    # ---------- 1) 键集合一致性 ----------
    schema_keys = [f["key"] for f in schema["scalar_fields"]]
    reg_keys = [f["key"] for f in fields]
    only_schema = [k for k in schema_keys if k not in reg_keys]
    only_reg = [k for k in reg_keys if k not in schema_keys]
    print(f"\n[1] 键集合：schema {len(schema_keys)} 个 / 登记表 {len(reg_keys)} 个")
    if only_schema:
        new.append(f"schema 有、登记表没有的字段：{only_schema}")
    if only_reg:
        new.append(f"登记表有、schema 没有的字段：{only_reg}")
    if not only_schema and not only_reg:
        print("    ✅ 两边一致")

    # ---------- 2) 核心是否真读 / 真用 ----------
    print("\n[2] 核心读取与使用情况")
    for f in fields:
        name = f.get("fortran_name")
        key = f["key"]
        if not name:
            if f.get("core_reads"):
                new.append(f"{key}: 声明 core_reads=true 但没有 fortran_name，无法核对")
            continue
        pat = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        in_read = bool(pat.search(read_block))
        uses = real_uses(name, all_fortran)
        used_elsewhere = bool(uses)
        declared_read = bool(f.get("core_reads"))
        declared_use = bool(f.get("core_uses"))
        tag = f" [{f['known_defect']}]" if f.get("known_defect") else ""
        if declared_read != in_read:
            msg = (f"{key}: 登记表说 core_reads={declared_read}，"
                   f"但核心 read(10,*) 里{'有' if in_read else '没有'}它")
            (known if f.get("known_defect") else new).append(msg)
            print(f"    ⚠ {msg}{tag}")
        if declared_use != used_elsewhere:
            where = "、".join(f"{h[0]}" for h in uses[:4]) or "无"
            msg = (f"{key}: 登记表说 core_uses={declared_use}，但核心源码里"
                   f"{'确实还有真实使用' if used_elsewhere else '除读取外再无使用（声明/注释不算）'}"
                   f"（真实使用行：{where}）")
            (known if f.get("known_defect") else new).append(msg)
            print(f"    ⚠ {msg}{tag}")
    dead = [f["key"] for f in fields if f.get("core_uses") is False]
    print(f"    死标签（核心读了不用）：{dead or '无'}")
    dead_controls = [f["key"] for f in fields + app_only
                     if f.get("core_reads") is False and f.get("widget") not in (None, "none")]
    print(f"    死控件（有界面但核心不读）：{dead_controls or '无'}")

    # ---------- 3) i18n 标签 ----------
    print("\n[3] i18n 标签覆盖")
    zh = load_json(ROOT / "app" / "i18n" / "zh_CN.json")
    en = load_json(ROOT / "app" / "i18n" / "en_US.json")
    label_keys = {f["label_key"] for f in fields + app_only if f.get("label_key")}
    miss_zh = sorted(k for k in label_keys if k not in zh)
    miss_en = sorted(k for k in label_keys if k not in en)
    for k in miss_zh:
        new.append(f"标签键 {k} 在 zh_CN.json 里不存在（界面会显示键名本身）")
    for k in miss_en:
        new.append(f"标签键 {k} 在 en_US.json 里不存在")
    print(f"    登记表引用 {len(label_keys)} 个标签键；缺 zh {len(miss_zh)} 个 / 缺 en {len(miss_en)} 个")
    if miss_zh or miss_en:
        print(f"    ⚠ 缺 zh：{miss_zh}\n    ⚠ 缺 en：{miss_en}")
    else:
        print("    ✅ 两个语言文件都齐")

    # ---------- 4) 界面控件 ----------
    print("\n[4] 界面控件有无")
    mw = MAIN_WINDOW.read_text(encoding="utf-8")
    no_widget_but_core = []
    for f in fields:
        key = f["key"]
        declared = f.get("widget")
        present = bool(re.search(r"\b" + re.escape(key) + r"\b", mw))
        if declared is None:
            if present:
                new.append(f"{key}: 登记表说没有控件，但 main_window.py 里出现了这个字段名")
            if f.get("core_reads"):
                no_widget_but_core.append(key)
        elif not present:
            new.append(f"{key}: 登记表说有控件（{declared}），但 main_window.py 里找不到")
    print(f"    有配置项、核心会读、但界面上改不了：{no_widget_but_core or '无'}")

    # ---------- 5) 运行时变换的闭合性 ----------
    print("\n[5] 运行时变换闭合性（谁改我 ⇄ 我被谁改）")
    declared_rw: dict[str, set[str]] = {f["key"]: set(f.get("rewritten_by") or []) for f in fields}
    for t in transforms:
        for key in t.get("rewrites", []):
            if key not in declared_rw:
                continue  # 表/非标量字段，跳过
            if t["name"] not in declared_rw[key]:
                msg = (f"{key} 被变换 `{t['name']}`（{t['where']}）改写，"
                       f"但该字段的 rewritten_by 里没登记")
                new.append(msg)
                print(f"    ⚠ {msg}")
        for key in t.get("drops", []):
            msg = f"变换 `{t['name']}` 会丢弃 {key}（{t['where']}）"
            (known if any(a["key"] == key and a.get("known_defect") for a in app_only) else new).append(msg)
            print(f"    ⚠ {msg}")
    for key, names in declared_rw.items():
        for n in names:
            t = next((x for x in transforms if x["name"] == n), None)
            if t is None:
                new.append(f"{key} 声明被不存在的变换 `{n}` 改写")
            elif key not in t.get("rewrites", []):
                msg = f"{key} 声明被 `{n}` 改写，但该变换的 rewrites 列表里没有它"
                new.append(msg)
                print(f"    ⚠ {msg}")
    print("    已登记的变换：")
    for t in transforms:
        print(f"      · {t['name']:<18} 改写 {len(t.get('rewrites', []))} 个字段"
              + (f"，丢弃 {t['drops']}" if t.get("drops") else ""))

    # ---------- 6) 归档一致性 ----------
    arc = reg.get("archive", {})
    print("\n[6] 归档配置 vs 实际执行配置")
    if arc.get("consistent") is False:
        msg = ("归档的 experiment_config.cfg 与实际执行的 cfg 不是同一份"
               f"（{arc.get('note', '')}）")
        (known if arc.get("known_defect") else new).append(msg)
        print(f"    ⚠ {msg}  [{arc.get('known_defect')}]")
    else:
        print("    ✅ 一致")

    # ---------- 汇总 ----------
    print("\n== 汇总 ==")
    print(f"   已知项（登记表里已标 known_defect）：{len(known)}")
    for m in known:
        print(f"     · {m}")
    print(f"   新问题（未登记，需要决定如何处理）：{len(new)}")
    for m in new:
        print(f"     ⚠ {m}")
    if new:
        print("\n   => 有新问题，退出码 1")
        return 1
    if known:
        print("\n   => 只有已登记项，退出码 3")
        return 3
    print("\n   => 干净，退出码 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
