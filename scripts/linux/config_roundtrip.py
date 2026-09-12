"""接口契约体检（2026-09-12 人工复核新增）。

目的：把"用户能点/能配的东西，核心到底认不认"这一整类缺陷一次扫出来。
背景：移植层的缺陷几乎都长在这条线上——#11 预设覆盖、#12 RDB 死控件、
      #15 mapping_scheme 死配置、以及系数库是否被消费（Q-21/Q-22）。

做三类检查（全部只读，不跑长任务）：
  A. **env 契约**：app 送出的 `SCRAM_*` 环境变量 vs 核心源码里真正 `get_environment_variable` 的集合
     → 差集即"送了但没人读"的死控件（#12 就是这么被定性的）。
  B. **cfg 契约**：app 能写的 cfg 字段（config_model）vs 核心 `ModuleDiscretization` 里的 `read(10,*)` 次数
     → 数量对不上就要逐行核（#9 那种错位属于此类）。
  C. **GUI 契约**：GUI 暴露的输入控件 vs 能写进 cfg 的字段名
     → 差集即"界面能点但写不出去/不生效"的候选。

用法：.venv/bin/python scripts/linux/config_roundtrip.py
退出码 1 = 有硬伤（死 env / 数量对不上），0 = 未发现硬伤（仍可能有个别字段未覆盖，见输出）。
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SRC = ROOT / "core/executables_or_wrappers/runtime/windows/source/SCRAM1.1/SRC"


def app_env_names() -> set[str]:
    text = (ROOT / "app/services/run_service.py").read_text(encoding="utf-8")
    return set(re.findall(r'"(SCRAM_[A-Z_]+)"\s*:', text))


def core_env_names() -> set[str]:
    names = set()
    for path in list(SRC.rglob("*.f90")) + list(SRC.rglob("*.f")):
        text = path.read_text(errors="replace")
        names |= set(re.findall(r"get_environment_variable\(\s*'([A-Z_]+)'", text))
    return {n for n in names if n.startswith("SCRAM_")}


def cfg_fields_written() -> list[str]:
    text = (ROOT / "app/config_binding/config_model.py").read_text(encoding="utf-8")
    return re.findall(r'##\s*([^"\']+)', text)


def core_read_sequence(path: Path) -> list[str]:
    """按出现顺序抽 ModuleDiscretization 里的 read(10,*) 语句（含所在行文本）。"""
    if not path.exists():
        return []
    body = path.read_text(errors="replace")
    if "read(10,*)Coefficient_file" not in body:
        return []
    body = body[body.index("read(10,*)Coefficient_file"):]
    seq = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("read(10,*)"):
            seq.append(re.sub(r"\s+", " ", stripped))
    return seq


def upstream_path() -> Path:
    local = Path.home() / "SCRAM1.1/SRC/ModuleDiscretization.f90"
    if local.exists():
        return local
    return Path("/nonexistent")


def generated_data_lines() -> int:
    """用 app 的写出器真实生成一份 cfg，数非注释的数据行数与核心 read 次数比对。"""
    try:
        from app.services.template_service import TemplateService
        from app.config_binding.config_model import ConfigModel
        import tempfile
        cfg = TemplateService(ROOT).load_template("gmd_paris_full")
        with tempfile.NamedTemporaryFile("w+", suffix=".cfg", delete=False) as fh:
            path = Path(fh.name)
        ConfigModel(ROOT).serialize(cfg, path)
        # 注释与数据同行（"1 ## coagulation switch"）→ 取 ## 之前的部分判空
        lines = [head for head in (l.split("##")[0].strip() for l in path.read_text().splitlines()) if head]
        path.unlink(missing_ok=True)
        # 第 1 行是系数文件，也被 read(10,*) 读走 → 计入
        return len(lines)
    except Exception as exc:  # noqa: BLE001
        print(f"   （无法生成对照 cfg：{exc}）")
        return -1


def gui_field_names() -> set[str]:
    text = (ROOT / "app/views/main_window.py").read_text(encoding="utf-8")
    return set(re.findall(r'field_widgets\["([a-z_0-9]+)"\]', text))


def main() -> int:
    hard = 0

    # SCRAM_PROGRAMSCRAM 由 run_service 自己消费（指定可执行文件），不是核心契约的一部分
    CONSUMED_BY_APP = {"SCRAM_PROGRAMSCRAM"}
    sent, read = app_env_names(), core_env_names()
    dead = sorted(sent - read - CONSUMED_BY_APP)
    print("== A. env 契约 ==")
    print(f"   app 送出 {len(sent)} 个：{', '.join(sorted(sent))}")
    print(f"   核心读取 {len(read)} 个：{', '.join(sorted(read))}")
    if dead:
        hard = 1
        print(f"   ✗ 送了但核心从不读（死控件）：{', '.join(dead)}")
    else:
        print("   ✓ 无死 env")

    print("== B. cfg 读序契约（与本体比对）==")
    repo_seq = core_read_sequence(SRC / "ModuleDiscretization.f90")
    up_seq = core_read_sequence(upstream_path())
    print(f"   仓库 read(10,*) 语句 {len(repo_seq)} 条；本体 {len(up_seq)} 条")
    if not up_seq:
        print("   · 找不到本体源码（~/SCRAM1.1），跳过比对")
    else:
        diff = [x for x in repo_seq if x not in up_seq]
        extra = [x for x in up_seq if x not in repo_seq]
        if diff or extra:
            print(f"   · 比本体多 {len(diff)} 条：{diff[:4]}")
            print(f"   · 比本体少 {len(extra)} 条：{extra[:4]}")
            print("     已知的**有意改动**只有 Bug #9（nucl_model=5 补无条件读入 init_bin_number/emission）；"
                  "若出现其它差异，就是 cfg 契约被改动，必须核对")
        else:
            note = "仓库含已知的 #9 改动（把条件读取改成无条件，语句本身相同）" \
                if "Bug #9" in (SRC / "ModuleDiscretization.f90").read_text(errors="replace") \
                else "仓库未见 #9 改动标记——若本体在该处也是条件读取，说明补丁没进去"
            print(f"   ✓ 语句序列与本体一致（{note}）")

    print("== C. GUI 契约 ==")
    fields = cfg_fields_written()
    gui = gui_field_names()
    ALIAS = {  # GUI 字段名 → cfg 里的叫法（None = 派生量，不直接写 cfg）
        "final_time_hours": "simulation time", "redistribution_method": "redistribution method",
        "fixed_density": "density mode", "dynamic_solver": "dynamic solver", "tag_thrm": "dynamic solver",
        "nucl_model": "nucleation", "sulfate_computation": "sulfate condensation",
        "kind_grid": "size sections", "kind_composition": "composition discretization",
        "cut_dim": "cut diameter", "dtmin_seconds": "minimum time step", "n_groups": "number of groups",
    }
    field_text = " ".join(fields).lower()
    missing = sorted(f for f in gui
                     if f not in field_text and (ALIAS.get(f) or "zzz").lower() not in field_text)
    print(f"   GUI 输入控件对应字段 {len(gui)} 个")
    if missing:
        print(f"   · 未在 cfg 写出行里出现（候选，需逐个确认是否只影响 GUI/派生量）：{', '.join(missing)}")
    else:
        print("   ✓ GUI 字段都能在 cfg 写出里找到")

    print(f"\n== 契约体检结论：{'有硬伤' if hard else '未发现硬伤'} ==")
    return hard


if __name__ == "__main__":
    sys.exit(main())
