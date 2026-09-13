# 人工 Windows 审核规划

> 背景：Linux 侧的定时自动调试已停止，移植层的自动化排查（契约/模板/保真度/假设队列）已收尾，见 `review_2026-09-13.md`。
> 本规划只列**只能在 Windows 上做**或**必须人工拍板**的事。
> 边界：agent 不改 `core/executables_or_wrappers/runtime/windows/**`、不改两个打包脚本、不生成发布资产——这些一律由人工在 Windows 上执行。
> 签核基线：`docs/validation_checklist.md`。

## 1. 前置准备

1. 仓库拉到含本次提交的状态：`git pull`（被强推过历史的机器用 `git fetch && git reset --hard origin/main`）。
2. Python 3.10+ 建 venv 并装依赖：`pip install -r requirements.txt`（PySide6 / matplotlib / SCons）。
3. 确认中文字体可用：**Microsoft YaHei UI**、SimSun——截图质量直接取决于此。
4. 报告链路（可选）：见 `docs/report_dependencies_windows.md` 与 `scripts/fetch_report_dependencies_windows.ps1`；无 LaTeX 时走内置离线 PDF 回退。
5. 开工前 `git rev-parse HEAD` 存档，作为本轮审核基线。

## 2. 审核批次

### W0 冷启动冒烟（前置，必须全过）

- **目的**：确认移植产物在 Windows 上能起来、能跑完标准对照。
- **步骤**：`scripts\run_app_windows.bat`；或跑 offscreen 冒烟 `python scripts\run_standard_tests.py`。
- **判据**：GUI 正常打开；默认新建实验为 `gmd_paris_full`（非零质量初值）；标准对照（内混 vs 外混）跑通并写出两分支结果。
- **不通过**：停止后续批次，回报现场。

### W1 核心数值一致性（上游本体 vs 移植 runtime）★最重要

- **目的**：确认移植没有改变数值口径——这是"Windows 化"的核心验收项。
- **前置**：Windows 侧的上游本体可执行程序，与 `core\executables_or_wrappers\runtime\windows\ProgramSCRAM.exe`。
- **步骤**：同一份 cfg、同一份系数库（`coef_s5_f3_b7.nc`）各跑一次，比较终态表（`concentration_gas` / `total_aero_mass` / `total_mass` 求和）。
- **判据**（沿用 P4 gate）：**总质量逐位一致**；气溶胶质量相对差 ≤ 1e-5。
- **已知差异（必须先知道）**：Linux 侧实测相对差 **1.373e-5 > 1e-5 ⇒ gate 未达标**（Bug #18），差异源于 `-g` 与 `-O2 -ffp-contract=off` 的编译标志而非代码。**Windows 工具链不同，Linux 的数值不能直接搬用，必须在 Windows 上重新测定。**
- **产物**：两臂 `run.log` + 对比表，结论登记到 `docs/BUG_TRACKING.md` #18。
- **不通过处置**：先在**统一编译标志**下重测；仍超阈值才判为移植缺陷。

### W2 Bug #7 v4 补丁落盘验证（可选，非阻塞）

- **目的**：若要在 Windows 上保留 `redistribution_method=6` 的演示能力。
- **前置**：`core\...\runtime\windows\source\SCRAM1.1\SRC\rdb\euler_coupled.f90` 与 `proposals/bug7_double_add_v4.patch` 的上下文需一致（Linux 侧已核对：上游 `~/SCRAM1.1` 与仓库锁版**逐字节相同**）。
- **步骤**：套用 `proposals/bug7_double_add_v4.patch` → 用 Windows 工具链重编译 runtime → 跑 `gmd_hazy_coag_cond` + `redistribution_method=6`。
- **判据**：`failed → ok`；日志中 `non conservation du nombre total !!` 出现 **0 次**；跑满配置步数。
- **已有证据（Linux/gfortran）**：512 步 0 次触发，总质量守恒 `2.02e-18`，方法=6 由 failed 转 ok。
- **注意**：产品侧已通过把模板默认 method 6→2 规避该缺陷，**本项非阻塞**，不做也不影响发布。
- **不通过**：保留为提案，不落盘，登记结论。

### W3 Bug #10：截图重生成（发布资产）

- **目的**：消除中文方框（tofu）。
- **步骤**（必须在 Windows、字体齐备时执行）：
  1. `python scripts\capture_screenshots.py` —— 默认写入 `docs\screenshots\`，共 **9 张**：
     `main_zh` / `main_en` / `config_setup_panel` / `structure_editor` / `running_state` /
     `results_view` / `report_panel` / `settings_panel` / `help_panel`（`.png`）。
  2. 终端会打印 `[font] 使用 CJK 字体: …`，确认取到的是 **Microsoft YaHei UI**。
  3. 逐张目视核验**无方框、无缺字**。
  4. 同步到另两处资产目录（当前三处同名同数、各 9 张）：
     `docs\user_manual_zh_assets\screenshots\`、`docs\undergrad_lab_assets\`。
- **判据**：9 张全部无方框，且三处一致。
- **产物**：更新后的 PNG（+ 提交）。
- **不通过**：回报具体哪几张、哪个控件，便于定位字体回退问题。

### W4 打包与 DevKit 生成

- **步骤**：`scripts\package_app_windows.ps1`（或 `package_app_windows.bat`）→ `scripts\make_windows_devkit.ps1`。
- **判据**：安装包可双击运行、开始菜单/桌面快捷方式可用；`WINDOWS_DEVKIT_MANIFEST.txt` **由脚本生成、不得手改**，生成后核对条目完整。
- **产物**：`dist\windows\...` + 更新后的 manifest。

### W5 验收口径定案（Bug #18）

- **三选一**：(a) 统一上游/移植的编译标志后维持 1e-5；(b) 调整阈值并记录依据；(c) 总质量逐位一致作硬判据、气溶胶相对差作软信号。
- **建议 (c)**：总质量是守恒量、对编译标志不敏感；气溶胶质量受浮点结合顺序影响，作为软信号更稳。
- **判据/交付**：决定与依据写入 `docs/BUG_TRACKING.md` #18，并把 gate 定义回写 `docs/linux_debugging/runbook.md`。

## 3. 需人工决策（不依赖 Windows，可离线拍板）

| ID | 决策项 | 选项 |
|---|---|---|
| #12 | `redistribution_option` 死控件 | A 接入核心 / B 移除控件 |
| #15 | `mapping_scheme` 死配置 | A / B（与 #12 同批处理） |
| #16 | GUI「环境状态」被 `tag_init` 门控 | a 与 `tag_init` 联动（推荐）/ b 暴露 `tag_init` / c 移除下拉 |
| #17 | 普通模式排放窗口仅 44 min | a 置 0 与本体口径一致 / b 做成可配 |
| #13 | 零质量下 EXT/INT 粒子数差 4 个数量级 | 需物理判断：设计使然 or 缺陷 |
| #2 / #5 | Prototype 零质量行为不一致 | 是否需要修（需重编译核心 → 先出提案） |

## 4. 签核表

| 批次 | 负责人 | 日期 | 结论 | 备注 |
|---|---|---|---|---|
| W0 冷启动冒烟 | | | | |
| W1 数值一致性 | | | | gate 是否达标： |
| W2 #7 v4 落盘 | | | | 非阻塞 |
| W3 #10 截图 | | | | 9 张是否无方框： |
| W4 打包/DevKit | | | | manifest 是否由脚本生成： |
| W5 口径定案 | | | | 选定 a / b / c： |

> 完成后请把结论回写 `docs/BUG_TRACKING.md`，并在 `docs/validation_checklist.md` 追加对应条目。
