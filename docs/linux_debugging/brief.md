# Linux 调试 Agent 任务书 — SCRAM BoxApp

> 面向自动化调试 agent 的执行规范。**本文件不是我自己定的规矩，而是把仓库里发布者文档中
> 已有的意图提炼成可执行条目**，每条都注明依据，避免 agent 按 README 里"看起来像但现在
> 不存在"的指令行事。
>
> 关联文档：日常操作与调度见 `docs/linux_debugging/runbook.md`；发现新 Bug 的方法见 `docs/linux_debugging/probe_backlog.md`；
> 总入口见仓库 `README.md` 的 "Development and debugging" 一节。
>
> 目标环境：Linux（Debian 12 / gfortran 12.2 / netCDF-Fortran 4.5.4 已验证）。
> 仓库根目录：`/home/yifeihu/SCRAMBoxApp-WinDevKit`（`/home/yifeihu/SCRAM-boxapp` 是其符号链接）。

---

## 0. 依据文档（提炼自哪里）

| 依据 | 提供的是什么 |
|---|---|
| `README.md` | 用户可见假设（只允许 INTERNAL/EXTERNAL）、GUI 工作流、配置语义、报告行为、平台与排错说明 |
| `WINDOWS_DEVKIT_README_zh.md` §5–§15 | 环境配置、**标准测试的 8 项检查**、截图流程、打包与重新生成开发包、结果目录约定、常见问题、**发布者建议的分工** |
| `docs/validation_checklist.md` | 发布验收清单（Windows 桌面 13 项 + 科学工作流 5 项） |
| `docs/BUG_TRACKING.md` | 未决 Bug 队列（含位置/触发条件/证据/修复方向）、实测模板对照表、模板与论文差异表、论文原始代码与输出文件位置 |
| `docs/gui_workflow.md` / `docs/demo_walkthrough.md` | 发布者定义的 GUI 正向流程（9/10 步），含"曲线重叠需用线型区分"这类验收细节 |
| `docs/config_mapping_spec.md` | GUI↔cfg 映射与 **4 条校验规则** |
| `docs/shared_runtime_layout.md` | 运行时解析顺序、venv 顺序、`source/` 用途 |
| `docs/SCRAM_BoxApp_中文用户操作手册.md` | "运行结束后应看到的文件"与**六张正确结果图**的定义 |
| `docs/SCRAM_BoxApp_本科教学实验手册.md` | **A/B/C/D 场景标准参考结果（数值基线）**与"应观察到的现象" |
| `docs/checktest/` | Bug 夹具惯例：同一 Bug 保留 `*_test.cfg`（可复现）与 `*_fixed.cfg`（手工修复）两份 |
| `docs/linux_debugging/brief.md`（本文件） | 把上述内容落到 Linux 平台的可执行版 |

发布者对调试的总期望可以概括为：**任何改动之后，都能在受支持平台上重新走通
"GUI → 运行 → 结果 → 报告"全流程，并且数值/图形与既有基线一致；Bug 的修复必须带
可复现证据与回归夹具。**

## 1. 角色与目标

Linux 上的调试 agent 通常同时承担 devkit §15 中的三个方向：**GUI 方向**（`app/views/main_window.py`、`app/i18n/`、`app/services/settings_service.py`）、**模型运行方向**（`app/services/run_service.py`、`template_service.py`、`core/templates/`、`core/defaults/`）、**结果分析方向**（`app/services/plot_service.py`、`report_service.py`）。底层算法方向（`source/SCRAM1.1/`）需要额外的人工物理判断。

目标（按优先级）：

1. 保持全链路可用：标准测试五项全通过；
2. 推进 `BUG_TRACKING.md` 的未决条目，并留下可复现证据与夹具；
3. 保证数值与图形落在基线范围内（§2.2/§2.3）；
4. 让文档、截图、清单与实际行为保持一致（§2.6）；
5. 逐步满足发布闸门（§7）。

## 2. 发布者定义的"正确"（验收基线，不要自创）

### 2.1 标准测试的 8 项检查（devkit §6）

每次修改代码后至少运行一次；检查项为：

1. Python 包能否导入；
2. GUI 能否在离屏模式下创建窗口并载入模板；
3. 当前平台的核心可执行文件存在且能被调用（Linux 上是
   `runtime/linux/ProgramSCRAM`，**不是** `.exe`）；
4. internal 与 external 两套假设是否都能完成运行；
5. 是否生成 `performance_summary.csv`；
6. 是否生成 `final_state_summary.csv`；
7. 是否生成关键 PNG 结果图；
8. PDF 报告是否能生成（无 LaTeX 时走内置离线后端）。

命令与成功标志见 §4 Phase 2。

### 2.2 数值基线（教学手册"标准参考结果" + BUG_TRACKING 对照表）

| 场景 | 过程 | 混合假设 | 终态质量 | 终态数量 | 相对 external 质量差 | 相对 external 数量差 |
|---|---|---:|---:|---:|---:|---:|
| A | 排放 only | INTERNAL / EXTERNAL | 24.4820 | 3.4465e10 | 0.00% | 0.00% |
| B | 排放 + 凝并 | INTERNAL | 24.4820 | 9.5575e9 | 0.00% | +1.32% |
| B | 排放 + 凝并 | EXTERNAL | 24.4820 | 9.4329e9 | 0.00% | 0.00% |
| C | 排放 + 冷凝/蒸发 | INTERNAL | 32.6126 | 3.4465e10 | −1.41% | 0.00% |
| C | 排放 + 冷凝/蒸发 | EXTERNAL | 33.0803 | 3.4465e10 | 0.00% | 0.00% |
| D | 全过程 | INTERNAL | 32.7327 | 1.0240e10 | −3.36% | −10.46% |
| D | 全过程 | EXTERNAL | 33.8691 | 1.1436e10 | 0.00% | 0.00% |

另：`tutorial_minimal` 基准终态质量 0.00148、`nucl_model=5` 实测（12h、30 物种）总质量 226.07 µg/m³、运行耗时 24.03 s（BUG_TRACKING 底部）。

判据分两层：

- **与上一轮基线比较 ≤ 1%**（同机器、同配置，紧——这才是回归判据）；
- **与上表比较 ≤ 2.5%**（跨环境量级校验，宽）。实测 EXTERNAL 终态数量与手册相差 1.774%、
  质量相差 0.349%，属正常环境差异，**不得据此判失败**。

运行时间只作趋势参考（教学手册明确"不同电脑运行时间会略有变化，终态数值通常应接近"）；
本机基线：internal ≈ 0.77 s / 88 步，external ≈ 17.2 s / 540 步（external 明显更慢，
与教学手册"external mixing 通常比 internal mixing 慢"一致）。

### 2.3 图形基线（用户手册"正确结果图"）

必须能生成并且形态正确：

- 总质量、总数量（`gmd_paris_full_total_mass.png` / `_total_number.png`）
- 相对 external 的质量差、数量差（`*_relative_mass_vs_external.png` / `*_relative_number_vs_external.png`）
- external mixed fraction（`*_external_mixed_fraction.png`）
- 不同粒径段的 mixed/unmixed 质量（`*_external_mixing_mass_by_size.png`）
- 对比图（`final_mass_comparison.png`、`final_number_comparison.png`、`runtime_comparison.png`）

用户手册同时规定"运行结束后应看到的文件"清单；教学手册规定"external mixing 通常比
internal mixing 慢"、"两者总质量同数量级但不完全相同"等可观察现象。

### 2.4 配置语义约束（config_mapping_spec.md "Validation Rules" + README "Config matching"）

- `n_species` 必须等于 species 表行数；
- `n_sizebin` 必须同时等于 size-bin 表、emission 表宽度、initial mass 表宽度；
- 粒径边界必须严格递增且长度为 `n_sizebin + 1`；
- fraction 边界必须严格递增、起于 `0`、止于 `1`、长度为 `n_frac + 1`；
- 混合假设只能是 `INTERNAL_MIXING` 或 `EXTERNAL_MIXING`；
- 载入 cfg 后必须先把解析值回填进 GUI 表格，再做任何由表格派生的收集。

### 2.5 产品边界（README "Supported user-facing assumptions"）

- 用户界面只暴露 INTERNAL/EXTERNAL 两种假设；
- `legacy`、`core_conserv`、`core_nogrow`、`core_smallgrow` 等 RDB 实现细节**不得**上升为用户选项；
- **Weighted / LCP 研究路径刻意排除在用户应用之外**——调试时不得把它们暴露给用户界面；
- 面向用户的比较目标始终是 internal vs external。

### 2.6 文档、截图与手册一致性（devkit §7）

**只要改动了 GUI 布局、按钮、文字或结果页，就必须重新生成截图**并更新手册资产：

```bash
# Windows（发布用）：写回 docs/screenshots/
.venv/bin/python scripts/capture_screenshots.py

# Linux（仅检查用）：必须用 --out 写到别处，不得覆盖发布资产
.venv/bin/python scripts/capture_screenshots.py --out install_logs/auto/<时间戳>/screenshots
```

脚本自带 `QT_QPA_PLATFORM=offscreen`，在 Linux 无显示器环境下**可以运行**；但它同时硬编码了
Windows 字体 `Microsoft YaHei UI`（第 36 行），Linux 上的字形与度量与发布资产不同，因此
**Linux 生成的截图只能用于比对检查，不能作为发布资产**（详见 §8）。

手册资产位置：`docs/user_manual_zh_assets/`、`docs/undergrad_lab_assets/`。
涉及手册文字改动时，同步更新 `docs/SCRAM_BoxApp_中文用户操作手册.md` 与
`docs/SCRAM_BoxApp_本科教学实验手册.md`。

## 3. Linux 环境事实与限制（不许当成 Bug）

- 平台：Linux。`app/services/deployment_paths.py` 的 `platform_name()` 返回 `linux`，
  运行时按 `docs/shared_runtime_layout.md` 的顺序解析：
  `SCRAM_PROGRAMSCRAM` → `runtime/<platform>/ProgramSCRAM` → 用户状态目录下的暂存副本
  （`~/.local/state/scram_boxapp_mixing/runtime/linux/`）。
- 本仓库自带 Linux 原生核心 `core/executables_or_wrappers/runtime/linux/ProgramSCRAM`；
  由 `scripts/linux/build_runtime.sh` 从 `source/SCRAM1.1` 编译安装（Debug 模式加 `debug`）。
- Windows 相关操作在 Linux 上**不可执行也不应尝试**：`scripts/package_app_windows.bat`、
  `package_app_windows.ps1`、`make_windows_devkit.ps1`（devkit §8/§13 的打包步骤必须在
  Windows 机器上完成）。
- **README.md 中被提到但本仓库不存在的文件**，不要执行、也不要据此判断环境损坏：
  `scripts/run_app_linux.sh`、`scripts/run_app_macos.sh`、`scripts/make_linux_release.sh`、
  `scripts/install_linux_fresh.sh`、`scripts/check_rdb_core_invariants.py`、
  `scripts/run_comparison_pipeline.sh`、`docs/linux_fresh_install.md`、
  `docs/linux_shared_install.md`、`dist/windows/dependencies/`。
- 手动运行核心前要在工作目录建 `RESULT/`（GUI 会自动创建）。
- 结果目录约定（devkit §11）：GUI 写入 `{输出目录}/single/{实验名称}_{案例预设}/` 与
  `{输出目录}/compare/...`，每次运行自动保存 `experiment_config.cfg` 便于追溯；
  标准测试强制写入 `install_logs/`（`--output-root` 指定），避免误删用户数据。

## 4. 每轮执行流程

### Phase 0 · 准备

```bash
cd /home/yifeihu/SCRAMBoxApp-WinDevKit
git fetch
git status --short          # 必须为空；不干净则报告并停止本轮
```

### Phase 1 · 构建（改过 Fortran 必须重跑，同时验证可构建性）

```bash
bash scripts/linux/build_runtime.sh              # 常规
bash scripts/linux/build_runtime.sh debug        # 核心排错：-O0 -g -fcheck=bounds -fbacktrace
```

重建后核对二进制 md5 是否与 `runtime/linux/ProgramSCRAM` 一致；不一致说明源码或工具链
发生变化，必须写入报告。

### Phase 2 · 标准测试（devkit §6 原文命令）

```bash
# 完整版
.venv/bin/python scripts/run_standard_tests.py \
    --template gmd_paris_full --case gmd_paris_full \
    --output-root install_logs/auto/<时间戳>/standard_tests

# 快速版（只测模型运行与绘图，不测报告）
.venv/bin/python scripts/run_standard_tests.py \
    --template gmd_paris_coagulation --case coag_only \
    --output-root install_logs/auto/<时间戳>/quick_test --skip-report
```

通过标志（实测输出形状）：

```
import_smoke: ok
gui_smoke: ok
report_smoke: ok
runtime_smoke: ok (gmd_paris_full / gmd_paris_full)
standard_tests: ok
```

（快速版带 `--skip-report` 时没有 `report_smoke` 行，其余四项相同；两条命令均已在 Linux 实测通过。）

### Phase 3 · 端到端流程复现（`docs/gui_workflow.md` 九步）

按文档顺序在离屏模式下复现：默认模板 `gmd_paris_full` → 选择案例预设与混合假设 →
检查/修改结构表格 → `比较 internal / external` → 运行监控 → 结果分析 → 报告导出。
等价的一条命令路径：`.venv/bin/python scripts/run_pipeline.py`（运行对比 + 绘图 + 报告）。

### 三条触发规则（按 devkit §6/§7/§8，不要混淆）

| 事项 | 条款 | 触发条件 | Linux 侧怎么做 |
|---|---|---|---|
| 标准测试 | §6 | **每次改代码后都要做** | 每轮跑（`run_standard_tests.py`，含快速版） |
| 截图 / 手册资产 | §7 | **只在改了 GUI（布局/按钮/文字/结果页）时才做** | `auto_round.sh` 用 git 时间戳复现该判据（`app/` 是否晚于 `docs/screenshots/`）；触发时生成**检查用**副本到轮次目录，发布资产仍需 Windows 生成。强制生成用 `--shots` |
| 打包 / 开发包 | §8、§13 | **只在发布时做** | 不在 Linux 做 |

### Phase 2.5 · 截图（§7 触发时才跑）

触发判据 = `git log -1 -- app/` 晚于 `git log -1 -- docs/screenshots/`。未触发则跳过并记录，不产出无意义的图。

### Phase 3.5 · 资产完整性（P9，每轮自动）

`auto_round.sh` 调用 `python scripts/linux/check_assets.py`，检查：资产是否晚于 GUI 改动（即 §7 是否触发）、
本环境能否渲染中文、文档引用的资产是否存在、影像密度是否异常、以及（`--render` 时）与新鲜渲染的对比。
任一告警都要写进 `summary.md`；`docs/BUG_TRACKING.md` 的未修条目（如 #10）会让本轮 WARN——刻意的，直到修掉为止。

### Phase 4 · 数值与图形比对

按 §2.2 / §2.3 对比，并额外采集：

| 信号 | 位置 | 判据 |
|---|---|---|
| `conservation_audit.csv` | `results/*/*/csv/`、`install_logs/**/runs/*/**/csv/` | 相对残差 ≤ 1e-6（本机实测 7.99e-16）；`has_nan`、`has_inf` 必须为 0 |
| `anomaly_flags.csv` | 同上 | **条目数不得超过上一轮基线**（首轮记录基线）。⚠️ 不要用"必须为 0"：本机基线为 external 1232 条 / internal 578 条，类型 `composition_collapse`、`single_bin_number_dominance`、`number_jump`，属既有现象而非回归 |
| `performance_summary.csv` | 同上 | `status` 必须为 `ok`；wallclock ≤ 1.5× 上一轮（本机基线 internal 0.77 s / external 17.2 s） |
| `final_state_summary.csv` | 同上 | 与上一轮偏差 ≤ 1%，与手册参考偏差 ≤ 2.5%（§2.2） |
| `timestep_summary.csv` | 同上 | 步数/最小步长无突变 |
| `run.log` | 运行目录 | 不含 `non conservation`、`STOP`、`NaN`（Bug #8 的判据） |

### Phase 5 · 未决 Bug 复现（依据 BUG_TRACKING 的条目格式）

对 `docs/BUG_TRACKING.md` 状态表中 ❌ 的条目（当前 #1、#9 未修复；#2、#5、#7 为 P2 待定）：

1. 找夹具：`docs/checktest/` 下按既有惯例命名的 cfg（如 Bug #9 的
   `nucl_model5_test.cfg` 可复现 / `nucl_model5_fixed.cfg` 手工修复对照）；
2. 无夹具则**新建最小复现配置**，按同惯例命名（`*_test.cfg` + 修复后的 `*_fixed.cfg`），
   放进 `docs/checktest/` 并 `git add`；
3. 跑夹具并判定"仍复现 / 已消失"，证据要素与 BUG_TRACKING 既有条目一致：
   **位置、触发条件、表现、影响面、证据（日志行号/CSV 数值）、修复方向、测试配置**；
4. 若是核心算法 Bug（#2/#5/#7），只产出 patch 提案放入 `proposals/`，不直接改核心。

### Phase 6 · GUI 有改动时重生成截图（§2.6）

```bash
.venv/bin/python scripts/capture_screenshots.py
```

并按需更新两份手册及 `docs/*_assets/` 中的图像。

### Phase 7 · 报告与暂存

写本轮报告（§6），把需要入库的内容 `git add`，**不 commit**。

## 5. 调试优先级与判据

**发现义务（不得跳过）**：每轮除回归验证外，必须按 `docs/linux_debugging/probe_backlog.md` 从覆盖矩阵里取
**1–3 条探测**（来源见 `next_probes.md`／`scripts/linux/probe_suggest.py`，含源码线索自动挖掘；
执行用 `scripts/linux/probe_cell.py`），并把结论按 BUG_TRACKING 的字段登记到台账（`docs/linux_debugging/probe_ledger.json`）。**复测通过 ≠ 没有 Bug**：标准测试只覆盖 28 格中的 2 格，阈值内的一切（包括基线里既有
的 1810 条 anomaly 标记）都是盲区。

1. **P0/P1 未决**：#1（tutorial_minimal 初始质量为零，证据 `performance_summary.csv` 的
   `final_mass=0.0`）、#9（nucl_model=5 文件读取错位，证据是 "Bad real number in item 8 of
   list input" 崩溃）。
2. **P2 待定（需重编译核心）**：#2/#5（Prototype 零质量 cell 被拒 / 双轨不一致，证据
   `coag_event_rate_sum=0`、`mapping_calls_step=0`、`active_bins=0`）、#7（euler_coupled
   非守恒，证据 `non conservation du nombre total !!` + IEEE 异常）。这三条要求 patch 提案 +
   人工审核，不得直接提交核心改动。
3. **数值不变量**（§4 Phase 4 表）。
4. **模板与论文/说明书差异**（BUG_TRACKING "模板与论文/说明书差异"表，例如
   `tutorial_minimal` 声称 2 物种 4 bin、实际继承 default 的 30 物种 7 bin）——属于文档或
   模板缺陷，产出修正提案。
5. **与论文原始输出对比验证**（进阶，条件允许时）：BUG_TRACKING 记录了 Zhu et al. (2015)
   的原始代码与**模型输出文件**位置（`http://cerea.enpc.fr/polyphemus/src/scram-1.0.tar.gz`）。
   网络可达时可用于交叉验证；不可达时在报告中记录为"未执行"，不要伪造结论。

## 6. 每轮生成什么

```
install_logs/auto/<YYYYmmdd-HHMM>/
  standard_tests/     Phase 2 全部输出
  quick_test/         快速版输出（如运行）
  pipeline/           Phase 3 产物
  screenshots/        Phase 6 新截图（如 GUI 有改动）
  baseline.json       本轮关键数值，供下一轮对比
  summary.md          人读报告
  summary.json        机读报告
  proposals/          需人工拍板的 patch（核心算法、模板、文档修正）
```

`summary.md` 必填字段：

- 轮次元信息：commit hash、构建模式、开始/结束时间、本轮改动文件清单；
- 标准测试 8 项逐项结果（§2.1）+ 原始输出片段；
- 数值表（§2.2 对照）+ 与基线/上一轮的差值；
- 图形生成清单（§2.3 六类是否齐全）；
- 不变量数值（§4 Phase 4 表）；
- 未决 Bug 复现结论（§4 Phase 5，逐条：编号 / 仍复现或已消失 / 证据 / 建议）；
- 结论：`pass` / `warn` / `fail`，以及**待人工确认项清单**（必须显式列出，不得留空）。

**允许**：写 `install_logs/auto/**`；`git add` 新增的 `docs/checktest/*.cfg`、
更新后的 `docs/BUG_TRACKING.md`、新截图与手册资产、本报告。
**禁止**：`git commit`、`git push`、`git reset --hard`；直接修改 `source/SCRAM1.1/SRC/*.f90`
（只能出 patch 提案）。

## 7. 单轮结论与发布闸门

| 结论 | 条件 |
|---|---|
| `pass` | 标准测试 8 项全过 + 不变量在阈值内 + 图形齐全 + 无新增未决项 |
| `warn` | 有不变量超阈值或图形缺失，但核心流程可用 |
| `fail` | 任一项 smoke 失败、数值偏离基线 > 1%、出现 `non conservation`/`NaN` |

**发布候选（release gate）** 需同时满足：

- 连续 7 轮 `pass`；
- `docs/validation_checklist.md` 中可在 Linux 验证的条目全部 `[x]`（Windows 专有项标注
  "需 Windows 验证"，不得勾选）；
- `docs/BUG_TRACKING.md` 中 P0/P1 无 ❌；
- `pyproject.toml` 版本号与 CHANGELOG 更新（以提案形式给出）；
- 截图与手册资产与当前 GUI 一致（§2.6）；
- Windows 安装包与开发包在 Windows 上由 `scripts/package_app_windows.ps1` /
  `scripts/make_windows_devkit.ps1` 生成（devkit §8/§13），Linux 侧只提供结论与清单。

## 8. Windows 发布口径守卫（每轮必做）

调试在 Linux、打包发布在 Windows，两条线**必须保持同一口径**：Linux 侧的工作不得改变
Windows 的发布行为。四类真实风险与对应约束：

| 风险 | 具体表现 | 约束 |
|---|---|---|
| 源码分支被写坏 | `coeff_make_dir` 的 Windows 分支（`cmd /c if not exist ...`）被删掉或改成无条件 POSIX 命令 → Windows 端无法创建输出目录 | `SRC/*.f90` 的任何改动都必须保留 Windows 分支，平台判断不得移除 |
| Linux 文件混入发布包 | `runtime/linux/**`、`build_runtime.sh` 被加进 Windows 打包白名单或运行时目录 | 不得改动 `scripts/package_app_windows.ps1`、`scripts/make_windows_devkit.ps1` 的取件范围 |
| 发布元数据被单方面推进 | 依据 Linux 结果勾选 `validation_checklist.md` 的 Windows 专有项、或直接提升 `pyproject.toml` 版本号 | 版本号与清单勾选只能出**提案**；Windows 项必须由 Windows 侧验证后勾选 |
| 文档资产漂移 | Linux 生成 `docs/screenshots/*` 覆盖 Windows 渲染的资产（脚本硬编码 `Microsoft YaHei UI`） | Linux 上必须用 `--out` 写到 `install_logs/` 作检查，**不得覆盖** `docs/screenshots/`；发布用截图在 Windows 重生成 |

每轮结束运行守卫脚本：

```bash
bash scripts/linux/check_windows_parity.sh
```

- **硬失败（exit 1）**：本轮判 `fail`，必须回退对应改动后再继续；
- **仅警告（exit 0）**：把警告项原样列入 `summary.md` 的"待人工确认项"。

守卫覆盖的硬检查：Windows 运行时目录未被改动、`SRC` 里的 Windows 分支仍在、Windows 打包脚本
未引用任何 Linux 专有文件或 `runtime/linux`。警告检查：改动落在 Linux 侧允许集合之外、
`pyproject.toml` / `validation_checklist.md` / `docs/screenshots` 被改动。

**Windows 侧的验证与打包只在 Windows 上做**：Linux 侧的报告只写"Windows 待验证 / 待打包"，
不得据此宣布发布。

## 9. 绝对不要做

- 不执行 Windows 指令：`cmd /c ...`、PowerShell、`.bat`、`.exe`。
- 不修改 `core/executables_or_wrappers/runtime/windows/` 下的 Windows 产物。
- 不为了让测试通过而放宽阈值、跳过 smoke 项或删改基线数值。
- 不把 Weighted/LCP 研究路径或 RDB 实现细节（legacy/core_*）暴露到用户界面（§2.5）。
- 不删除 `install_logs/` 之外的历史结果；不动 `~/.local/state/scram_boxapp_mixing/`
  下的用户数据（除非按 §9 强制刷新运行时）。
- 不依据 §3 列出的"README 提到但仓库不存在"的文件判断环境损坏。

## 10. 已知坑（实测 + devkit §14）

| 现象 | 处理 |
|---|---|
| `Cannot open file 'RESULT/report.txt'` | 手动运行核心的工作目录缺 `RESULT/`；`mkdir -p RESULT` 后重跑 |
| 改了 Fortran 但 GUI 仍用旧核心 | 运行时按清单暂存；`rm -rf ~/.local/state/scram_boxapp_mixing/runtime/linux` 强制重新暂存 |
| Qt 报 `could not connect to display` | 无桌面会话；`QT_QPA_PLATFORM=offscreen`（截图脚本已内置） |
| `Fatal Error: Cannot open module file '*.mod'` | 不要单文件直调 gfortran，用 `build_runtime.sh`（SCons 管依赖顺序） |
| scons 报找不到 `gfortran-15` | 本机是 gfortran 12；脚本已传 `FC=gfortran`，不要裸跑 `scons` |
| GUI 闪退（devkit §14） | 不要双击 `.py`；用 `scripts/launch_app.py` 看终端报错 |
| 结果图没生成（devkit §14） | 先确认标准测试是否通过，再看 `install_logs/.../stdout.log`、`stderr.log` 或 GUI 运行监视器 |
| `git add` 漏文件 | 注意 `.gitignore` 的 `*~` 与子目录内自忽略的 `.gitignore`；必要时 `git add -f` 并核对 `git status` |

## 11. 快速索引

| 想知道 | 看 |
|---|---|
| **Windows 发布口径会不会被改坏** | 跑 `bash scripts/linux/check_windows_parity.sh`；约束见 §8 |
| 标准测试命令与检查项 | `WINDOWS_DEVKIT_README_zh.md` §6 |
| GUI 改动后要做什么 | 同上 §7；`scripts/capture_screenshots.py` |
| 怎么打包、怎么重新生成开发包 | 同上 §8、§13 |
| 结果写到哪、怎么追溯参数 | 同上 §11 |
| 新增本科实验题目 | 同上 §10（6 步流程） |
| 每个开发方向该看哪些文件 | 同上 §15 |
| 发布验收项 | `docs/validation_checklist.md` |
| 未决 Bug 与证据 | `docs/BUG_TRACKING.md` |
| 数值/图形基线 | `docs/SCRAM_BoxApp_本科教学实验手册.md`（标准参考结果）、`docs/SCRAM_BoxApp_中文用户操作手册.md`（正确结果图） |
| 配置校验规则 | `docs/config_mapping_spec.md` |
| 运行时解析与暂存 | `docs/shared_runtime_layout.md` |
