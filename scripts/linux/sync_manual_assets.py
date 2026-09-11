#!/usr/bin/env python3
"""T4: 手册资产生成/同步脚本（安全默认 dry-run）。

docs/screenshots/ 是 GUI 截图的权威来源（Windows 上生成）。
docs/user_manual_zh_assets/ 与 docs/undergrad_lab_assets/ 是手册发布资产，
其中截图应与 docs/screenshots/ 保持一致。

本脚本默认只做「漂移检查」（dry-run）：列出各手册资产目录中缺失或与
docs/screenshots/ 不一致（按 SHA-256）的截图，不修改任何发布资产。
只有在显式 --apply 时才把 docs/screenshots/ 的截图复制进手册资产目录
（仍只覆盖截图，不碰 figures/ 与 CSV）。

用法：
  python scripts/linux/sync_manual_assets.py            # dry-run，仅报告
  python scripts/linux/sync_manual_assets.py --apply    # 实际同步截图
"""
import argparse, hashlib, os, shutil, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "docs", "screenshots")
TARGETS = [
    os.path.join(ROOT, "docs", "user_manual_zh_assets", "screenshots"),
    os.path.join(ROOT, "docs", "undergrad_lab_assets"),
]

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际复制（默认 dry-run）")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        print(f"错误：源目录不存在 {SRC}")
        return 2
    src_pngs = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".png"))
    if not src_pngs:
        print(f"错误：{SRC} 中没有 PNG")
        return 2

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== 手册资产同步（{mode}）==  源: docs/screenshots/ ({len(src_pngs)} 张)")
    total_missing = total_diff = 0
    for tgt in TARGETS:
        rel = os.path.relpath(tgt, ROOT)
        if not os.path.isdir(tgt):
            print(f"  [缺失目录] {rel}（--apply 时将创建）")
            total_missing += len(src_pngs)
            continue
        print(f"  -- {rel}")
        for name in src_pngs:
            sp = os.path.join(SRC, name)
            tp = os.path.join(tgt, name)
            if not os.path.exists(tp):
                print(f"     缺失   {name}")
                total_missing += 1
                if args.apply:
                    shutil.copy2(sp, tp)
                    print(f"     已复制 {name}")
                continue
            if sha256(sp) != sha256(tp):
                print(f"     不一致 {name}（SHA-256 不同）")
                total_diff += 1
                if args.apply:
                    shutil.copy2(sp, tp)
                    print(f"     已覆盖 {name}")
    print(f"== 汇总：缺失 {total_missing}，不一致 {total_diff} ==")
    if not args.apply and (total_missing or total_diff):
        print("提示：dry-run 未修改任何文件；确认无误后加 --apply 同步。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
