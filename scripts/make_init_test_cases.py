#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成"初始态 × 组成档"测试配置矩阵，供 Linux 重编译后验证内核修改。

覆盖的三处内核修改（改动说明见 docs/0929check.md，操作清单见 docs/0929linux.md）：
  1. ModuleDiscretization.f90 块④ 守卫补 nucl_model/=5 与 Tag_init=1；
  2. nl=5 外混臂的黑碳判据由"第 1 族下限=0"改为"第 4 族上限=1"；
  3. init_bin_mass / init_bin_number 显式清零。

机制：直接复用应用侧 ConfigModel（写法与 GUI 完全一致，含 nl=5 的 53 行精简格式），
因此不用手工维护 cfg 行数契约。Tag_init=0 的物种行按内核 read 语义改写成
"ID 族号 init_gas 排放 总质量" 五列形式（内核该模式下只取前 5 列）。

用法：
  python scripts/make_init_test_cases.py
  python scripts/make_init_test_cases.py --out /tmp/cases --n-frac 5 --hours 12
"""
from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config_binding.config_model import ConfigModel  # noqa: E402

BASE_CFG = ROOT / "core" / "templates" / "baseline12h.cfg"

# 组成档边界：n_frac=3 用出厂手写边界（与 GUI 比较臂一致），其余等分
BOUNDS = {
    1: [0.0, 1.0],
    3: [0.0, 0.2, 0.8, 1.0],
    5: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
}

# 官方雾霾预设（app/services/template_service.py 的 gmd_hazy_condensation）：
# nl=5 的三个臂按它取参数，测试才与产品路径一致。
HAZY = {
    "with_coag": 0, "with_cond": 1, "with_nucl": 0,
    "temperature": 298.0, "pressure": 101325.0, "humidity": 0.7,
}

# case 名 → (nucl_model, tag_external, n_frac, tag_init, 说明)
CASES = [
    ("T1_nl5_nf1",          5, 0, 1, 1, "nl=5 内混基准臂（单列）"),
    ("T2_nl5_ext_tagext0",  5, 0, 3, 1, "nl=5 外混 + 内混初值：修前 orphan 停机"),
    ("T3_nl5_ext_tagext1",  5, 1, 3, 1, "nl=5 外混 + 外混初值：修前初值虚高 6 倍"),
    ("T4_nl1_ext_tagext1",  1, 1, 3, 1, "回归：块③的 tag_external=1 路径必须逐位不变"),
    ("T5_nl1_ext_tagext0_ti0", 1, 0, 3, 0, "隐患路 B：Tag_init=0 时块④ 读到未初始化质量"),
    ("T6_nl1_ext_tagext0_ti1", 1, 0, 3, 1, "块④ 的正常用途：必须仍然执行（回归）"),
    ("T7_nl1_nf1_ti0",      1, 0, 1, 0, "T5 的内混对照臂（Tag_init=0 单列）"),
]

# 可选：零质量输入的复验配置（--zero-mass 时才生成）。逐档质量全 0、逐档粒子数非 0，
# 用来把"新核下零质量输入是否仍静默空转"变成有记录的事实（见 docs/0929linux.md §5）。
ZERO_MASS_CASES = [
    ("T8_zero_mass_int", 1, 0, 1, 1, "零质量 + 内混单列（复验用）"),
    ("T9_zero_mass_ext", 1, 0, 3, 1, "零质量 + 外混多列（复验用）"),
]


def _sum_species_line(line: str) -> str:
    """把逐档质量行改写成 5 列形式：ID 族号 init_gas 排放 总质量。"""
    head, sep, comment = line.partition("##")
    tokens = head.split()
    if len(tokens) <= 5:
        return line
    total = sum(float(value) for value in tokens[4:])
    rebuilt = "%-3s %-3s %-14s %-14s %.10g" % (tokens[0], tokens[1], tokens[2], tokens[3], total)
    return rebuilt + ("  " + sep.strip() if sep else "")


def build_case(base: dict, case, hours: float, out_dir: Path, model: ConfigModel,
               zero_mass: bool = False) -> dict:
    name, nucl_model, tag_external, n_frac, tag_init, note = case
    data = deepcopy(base)
    scalars = data["scalars"]
    n_frac = int(n_frac)
    scalars.update(
        nucl_model=int(nucl_model),
        tag_external=int(tag_external),
        n_frac=n_frac,
        tag_init=int(tag_init),
        kind_composition=0,
        final_time_hours=float(hours),
    )
    if int(nucl_model) == 5:
        scalars.update(HAZY)  # 与官方雾霾预设一致
    if zero_mass:
        # 逐档质量全 0、逐档粒子数保持非 0（内核 Tag_init=1 时两者分别来自不同行）。
        # tagrho=0：tagrho=1 时全零质量会在"平均密度"计算里除零得到 NaN，属另一个问题。
        scalars["tagrho"] = 0
        for record in data["species_records"]:
            record["bin_values"] = [0.0] * len(record["bin_values"])
    data["fraction_bounds"] = list(BOUNDS[n_frac])
    data["mixing_assumption"] = "INTERNAL_MIXING" if n_frac == 1 else "EXTERNAL_MIXING"

    target = out_dir / ("%s.cfg" % name)
    model.serialize(data, target)

    if int(tag_init) == 0:
        # 内核 Tag_init=0 时物种行只读 5 列（第 5 列 = 该物种总质量），
        # 因此把逐档质量列压成一列；其余行（init_bin_number/排放）保持标准格式。
        text = target.read_text(encoding="utf-8").splitlines()
        n_species = int(scalars["n_species"])
        start = 19  # 前 19 行是标量行，其后是物种行
        for i in range(start, start + n_species):
            text[i] = _sum_species_line(text[i])
        target.write_text("\n".join(text) + "\n", encoding="utf-8")

    return {"case": name, "path": target, "note": note,
            "nucl_model": nucl_model, "tag_external": tag_external,
            "n_frac": n_frac, "tag_init": tag_init}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成初始态测试配置矩阵")
    parser.add_argument("--out", default=str(ROOT / "install_logs" / "20260929_init_cases"),
                        help="输出目录（默认 install_logs/20260929_init_cases，已被 gitignore）")
    parser.add_argument("--n-frac", type=int, default=3, help="外混臂的组成档段数（3 或 5）")
    parser.add_argument("--hours", type=float, default=12.0,
                        help="模拟时长（小时，默认 12.0 = 出厂雾霾案例；冒烟用 1.0）")
    parser.add_argument("--zero-mass", action="store_true",
                        help="额外生成零质量输入复验配置（T8/T9；逐档质量全 0、粒子数非 0、tagrho=0）")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = ConfigModel(ROOT)
    base = model.parse(BASE_CFG)

    cases = []
    for case in CASES:
        name, nucl_model, tag_external, n_frac, tag_init, note = case
        if n_frac > 1 and n_frac != args.n_frac:
            case = (name, nucl_model, tag_external, args.n_frac, tag_init, note)
        cases.append(build_case(base, case, args.hours, out_dir, model))
    if args.zero_mass:
        for case in ZERO_MASS_CASES:
            zero_case = (case[0], case[1], case[2],
                         args.n_frac if case[3] > 1 else case[3], case[4], case[5])
            cases.append(build_case(base, zero_case, args.hours, out_dir, model, zero_mass=True))

    print("输出目录：%s" % out_dir)
    print("")
    print("%-26s %-4s %-4s %-4s %-4s %s" % ("case", "nl", "text", "nfra", "init", "说明"))
    for row in cases:
        print("%-26s %-4s %-4s %-4s %-4s %s" % (
            row["case"], row["nucl_model"], row["tag_external"],
            row["n_frac"], row["tag_init"], row["note"]))
    print("")
    print("回归自查（nl≠5 且 Tag_init=1 的配置应能往返解析）：")
    for row in cases:
        if row["nucl_model"] != 5 and row["tag_init"] == 1:
            back = model.parse(row["path"])
            ok = (int(back["scalars"]["n_frac"]) == row["n_frac"]
                  and int(back["scalars"]["tag_external"]) == row["tag_external"])
            print("  %-26s %s" % (row["case"], "ok" if ok else "往返不一致，请检查"))
    print("")
    print("Tag_init=0 的配置（内核只取物种行前 5 列，已改写为 5 列形式）：")
    for row in cases:
        if row["tag_init"] == 0:
            first = row["path"].read_text(encoding="utf-8").splitlines()[19]
            print("  %-26s 物种行 1：%s" % (row["case"], first.split("##")[0].strip()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
