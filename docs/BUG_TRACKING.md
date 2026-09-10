# SCRAM BoxApp Bug 追踪表

> 创建日期: 2026-07-23 | 最后更新: 2026-09-10 | 新增 #10 截图文字全为方框（文档资产不可用）

## 修复状态

| # | 严重性 | 类别 | 状态 | 验证结果 |
|---|--------|------|------|---------|
| 1 | 🔴 P0 | 初始化 | ❌ 未修复 | `tag_init=0` 方案不可行（cfg 解析时 bin_values 已定型），需改 `default_config.cfg` 或模板系统支持 per-species mass |
| 2 | 🔴 P2 | 凝并 | ❌ P2 待定 | 需重编译 Fortran |
| 3 | 🟡 P0 | 运行 | ✅ 已修复 | `Simulation Time 1800s`（原 43200s） |
| 4 | 🟡 P1 | 初始化 | ✅ 已修复 | `Fixed Density 1.8E-6`（原 NaN） |
| 5 | 🟢 P2 | 凝并 | ❌ P2 待定 | 与 #2 合并修复 |
| 6 | 🟡 P1 | 绘图 | ✅ 已修复 | `generate_all()` 不再传错参 |
| 7 | 🔴 P2 | 重分配 | ❌ P2 待定 | 需重编译 Fortran；非零质量也会触发，见 #7.1 |
| 8 | 🟡 P1 | 运行 | ✅ 已修复 | gmd_hazy 正确检测为 `failed`（原误报 `ok`） |
| 9 | 🔴 P1 | 初始化 | ❌ 未修复 | nucl_model=5 跳过行后文件位置错位，需补 dummy read |
| 10 | 🟡 P1 | 文档资产 | ❌ 未修复 | **界面截图类资产共 24 张的密度异常**：`docs/screenshots/`（9）、`docs/user_manual_zh_assets/screenshots/`（8）、`docs/undergrad_lab_assets/`（8）文字全渲染为方框（中英文皆然）；被根 `README.md`、用户手册与教学手册引用。需在有字体的 Windows 上按 §7 重生成，并给生成脚本加字体可用性检查 |

## Bug 总览

| # | 严重性 | 类别 | 简要描述 | 触发条件 | 修改文件 | Git 提交备注 |
|---|--------|------|---------|---------|---------|------------|
| 1 | 🔴 P0 | 初始化 | tutorial_minimal 初始质量为零，数量不为零 | `base="default"` + `Tag_init=1` + 全零 `bin_values` | `app/services/template_service.py` | `fix: tutorial_minimal 模板 tag_init=0，让 Hazy 分布自动生成质量` |
| 2 | 🔴 P2 | 凝并 | Prototype 模式 `coeff_build_pair_mapping` 拒绝零质量 cell | `mass=0` + `number≠0` + `with_coag=1` | `SRC/ModuleCoeffRepartitionBoxmodel.f90` | `fix: Prototype 模式零质量 cell 静默跳过保护` |
| 3 | 🟡 P0 | 运行 | Case Preset 时长未写入生成的 cfg | 所有 GUI 运行 | `app/services/run_service.py` | `fix: prepare_run 调用 _with_case_preset 确保时长写入 cfg` |
| 4 | 🟡 P1 | 初始化 | `fixed_density = NaN`（全零质量 + `tagrho=1` 除零） | `mass=0` + `tagrho=1` | `app/services/template_service.py` | `fix: 零质量模板默认 tagrho=0 避免除零 NaN` |
| 5 | 🟢 P2 | 凝并 | Legacy/Prototype 双轨制对零质量行为不一致 | `mass=0` + `with_coag=1` + 切换模式 | `SRC/ModuleCoagulation.f90` | `fix: Legacy/Prototype 零质量输入行为统一` |
| 6 | 🟡 P1 | 绘图 | GUI 单次运行不生成图片（传错参数） | GUI "运行"按钮 | `app/views/main_window.py` | `fix: _on_run_completed 传正确 results_root 给 generate_all` |
| 7 | 🔴 P2 | 重分配 | `euler_coupled` redistribution 零质量/非零不均匀质量均触发非守恒 | `mass=0` 或 `mass≠0` 分布不均 + `with_cond=1` + `redistribution_method=6` | `SRC/rdb/euler_coupled.f90` | `fix: euler_coupled 质量/数量非守恒保护` |
| 8 | 🟡 P1 | 运行 | Fortran 内部 STOP 返回 exit code 0，Python 误报成功 | Fortran 内部任何 STOP | `app/services/run_service.py` | `fix: 检测 run.log 异常关键字，标记 failed` |
| 9 | 🔴 P1 | 初始化 | nucl_model=5 跳过 init_bin_number/emission 读取后文件位置错位 | nucl_model=5 + 配置含 init_bin_number/emission 行 | `SRC/ModuleDiscretization.f90:129-134` | `fix: nucl_model=5 else 分支补 dummy read 跳过行` |

### 实测模板对照表（base="teaching"，非零初始质量，2026-07-27）

| 模板 | Case Preset | 过程 | redist. method | final_mass | final_number | 状态 | 结论 |
|------|------------|------|---------------|------------|-------------|------|------|
| tutorial_minimal | coag_only | 仅凝并, 0.25h | 2 | 0.00148 | 4.11B (−10.99M) | ✅ | 凝并正常，质量守恒 |
| gmd_hazy_condensation | gmd_hazy_condensation | 仅冷凝, 12h | 2 | 0.000174 | 3.42B 不变 | ⚠️ | 无挥发性物种，冷凝空转 |
| gmd_hazy_coag_cond | coag_cond | 凝并+冷凝, 12h | **6** | — | — | ❌ | euler_coupled 崩溃（Bug #7） |

> 注：上表为 2026-07-27 切换 base="teaching" 后的实测数据，非零初始质量。旧表（零质量骨架）见下方。

### 模板与论文/说明书差异

| 模板 | 说明书声称 | 实际 cfg | 论文 Section 3 要求 |
|------|-----------|---------|-------------------|
| tutorial_minimal | BC+硫酸盐, **2** 物种, **4** bin | 继承 default: **30** 物种, **7** bin | N/A（教学案例） |
| gmd_hazy_condensation | hazy 冷凝验证 | 30 物种, 无冷凝源 | **2** 物种, 恒定硫酸蒸气源 5.5 µm³/cm³/12h |
| gmd_hazy_coag_cond | hazy 凝并+冷凝验证 | 30 物种, 无冷凝源 | **2** 物种, 恒定硫酸蒸气源 |

### 论文原始代码位置

Zhu et al. (2015) 第 17 页 "Code availability":
> http://cerea.enpc.fr/polyphemus/src/scram-1.0.tar.gz
> 包含源码、配置文件、Read Me、**模型输出文件**（可用于对比验证）

## 详细信息

### Bug #1: tutorial_minimal 初始质量为零

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/template_service.py:12-25` + `core/defaults/default_config.cfg:19-49` + `SRC/ModuleDiscretization.f90:654-663,672-684` |
| **触发条件** | 模板 `base="default"`，`Tag_init=1`，所有物种 `bin_values=0` |
| **表现** | `concentration_mass=0` 但 `concentration_number≠0`（Hazy 分布提供），称为"幽灵粒子" |
| **影响面** | `tutorial_minimal`, `gmd_hazy_condensation`, `gmd_hazy_coag_cond` — 所有继承 `default_config.cfg` 的模板 |
| **证据** | `result/single/tutorial_minimal_*/performance_summary.csv`: final_mass=0.0；标准测试 `install_logs/t1/` 同理 |
| **修复** | 模板 `updates.scalars` 加 `tag_init: 0`（从 Hazy trimodal + 物种信息自动计算质量） |

### Bug #2: Prototype 模式拒绝零质量 cell

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/ModuleCoeffRepartitionBoxmodel.f90:546-547` |
| **触发条件** | `coeff_cell_total_mass(cell) <= N_species * TINYM` 时 cell 被标记不活跃 |
| **表现** | `coeff_pair_count=0`，`Rate()` 凝并循环完全跳过，`rate_number=0, rate_mass=0` |
| **影响面** | 所有 `mass=0` + `with_coag=1` 组合 |
| **证据** | `conservation_audit.csv`: `coag_event_rate_sum=0`, `mapping_calls_step=0`, `active_bins=0` |
| **修复** | Fortran 源码修改，对 `mass=0` 但有 `number` 的 cell 做 fallback（警告 + 纳入配对或标记） |

### Bug #3: Case Preset 时长不写入 cfg

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py:92-95` (prepare_run) vs `:302-309` (_with_case_preset) |
| **触发条件** | GUI 中选择任意 case preset 后运行 |
| **表现** | GUI 显示 0.5h，但生成 cfg 保持模板原始时长（tutorial=12h），仿真实际跑 12h |
| **影响面** | 所有通过 GUI 的运行，`duration_hours` 设定全部无效 |
| **证据** | `run.log:34`: `Simulation Time 43200s`（应为 1800s） |
| **修复** | `prepare_run` 中 `_with_mixing_assumption` 后调用 `_with_case_preset` |

### Bug #4: fixed_density = NaN

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/ModuleDiscretization.f90:135-150` |
| **触发条件** | `tagrho=1` + `init_mass` 全为零 → `per_mass_init = NaN` |
| **表现** | `fixed_density = NaN`，`fixed_density_l = NaN` |
| **影响面** | 所有零质量模板的质量→体积/直径转换路径 |
| **证据** | `run.log:27`: `fixed_density NaN` |
| **修复** | Python 端模板覆写 `tagrho=0`，固定密度由 `fixed_density` 标量提供 |

### Bug #5: Legacy/Prototype 双轨制不一致

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/ModuleCoagulation.f90:169-251` (Prototype) vs `:254-278` (Legacy) |
| **触发条件** | `mass=0` + `number≠0` + `with_coag=1` |
| **表现** | Legacy 仅检查 `c_number>0` → 会算凝并速率；Prototype 额外检查 mass → 跳过 |
| **影响面** | 切换 `SCRAM_COEFF_REPARTITION_MODE` 时零质量场景行为不同 |
| **修复** | 与 Bug #2 合并处理，统一两种模式的零质量行为 |

### Bug #6: GUI 单次运行不生成图片

| 项目 | 内容 |
|------|------|
| **位置** | `app/views/main_window.py:1118` |
| **触发条件** | GUI 点击"运行"（单次，非比较） |
| **表现** | `_on_run_completed` 传 `self.current_results_root` 给 `generate_all()` → 覆盖正确的单次输出路径 → csv 检查失败 → 静默跳过 |
| **影响面** | GUI 所有单次"运行"操作，`/result/single/*/figures/` 全空 |
| **证据** | 标准测试有 10 张图，GUI `result/single/*/figures/` 0 张 |
| **修复** | `_on_run_completed` 不传参给 `generate_all()`，使用已正确设置的 `plot_service.results_root` |

### Bug #7: euler_coupled redistribution 质量/数量非守恒

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/rdb/euler_coupled.f90:254-260` |
| **触发条件** | `redistribution_method=6` + `with_cond=1`（**零质量和非零质量均会触发**） |
| **表现** | 零质量：数量 3.42B→102.6B（30 倍）；非零质量：`IEEE_INVALID_FLAG + IEEE_DIVIDE_BY_ZERO`，数浓度反复跳动 0.047% |
| **影响面** | `gmd_hazy_coag_cond` 等同时开启冷凝和 euler_coupled 重分配的模板 |
| **证据** | 零质量：`run.log`: 法文数量不守恒报错 + 30x 跳变；非零质量：`0727_coag_cond run.log`: `non conservation du nombre total !!` + IEEE 异常 |
| **修复** | Fortran 端加质量/数量输入保护；临时方案：模板改用 `redistribution_method=2`（Moving Diameter） |

### Bug #8: Fortran STOP 返回 exit code 0

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py:160` + 多个 `.f90` 中的 `STOP` |
| **触发条件** | Fortran 内部 `STOP`（如 `euler_coupled.f90:270`） |
| **表现** | 模拟内部崩溃但 Python 报告 `status=ok` |
| **影响面** | 任何 Fortran 出错场景都被误判为成功 |
| **证据** | `gmd_hazy_coag_cond` 内部爆炸后 `performance_summary.csv` 仍显示 `status=ok` |
| **修复** | Python 端 `run_prepared` 后检查 `run.log` 是否含异常关键字（`non conservation`, `STOP`, `NaN`） |

### Bug #9: nucl_model=5 文件读取位置错位

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/ModuleDiscretization.f90:129-134` |
| **触发条件** | `nucl_model=5` + 配置文件含 `init_bin_number` 和 2 行 `init_bin_emission` |
| **表现** | `if(nucl_model.ne.5)` 跳过了 3 行读取，但文件指针未前进。后续 `read(10,*)(diameter(k),...)` 行读到 init_bin_number 数据，崩溃："Bad real number in item 8 of list input" |
| **影响面** | `nucl_model=5` 无法解析任何标准格式配置（必须手工删除 init_bin_number + emission 行） |
| **证据** | baseline12h 标准格式（56 行）→ 崩溃在 line 194；删除 init_bin_number+emission 后（53 行）→ 正常运行 |
| **修复** | `if(nucl_model.ne.5)` 的 `else` 分支补 dummy read：`read(10,*); do s=1,min(N_species,2); read(10,*); enddo` |
| **测试配置** | `docs/checktest/nucl_model5_test.cfg`（未修复，56 行，可复现崩溃）/ `docs/checktest/nucl_model5_fixed.cfg`（手工修复，53 行，可运行） |

### nucl_model=5 运行结果（2026-07-27，baseline12h 基座 + 30 物种）

| 指标 | 初始 | 最终 | 说明 |
|------|------|------|------|
| 总气溶胶质量 | 226.07 µg/m³ | — | hazy 场景参数化，远大于 tutorial（0.00148） |
| SO₄ 气溶胶 | 18.84 | 28.73 (+9.89) | 硬编码排放率 2.29e-4，12h 排放窗口 |
| BC 气溶胶 | 207.23 | 207.23 | 惰性，无变化 |
| Nub Nucl | — | +66,891,856 | 成核产生新粒子 |
| Nub Coag | — | −24,135,436,600 | 大量凝并消除 |
| Mass Cond | — | +2.39 | 冷凝净增质量 |
| total_water | — | 62.75 | 液态水大量生成 |
| 运行耗时 | — | 24.03 s | 30 物种全动力学 |

> nucl_model=5 是完全自成一体的硬编码验证模式：忽略配置文件物种数据，用 hazy 场景参数化 + 50/50 SO₄+BC 均分 + 硬编码 SO₄ 排放。结果与 tutorial/hazy 模板运行不可比。

### Bug #10: 截图文字全部渲染为方框（文档资产不可用）

| 项目 | 内容 |
|------|------|
| **位置** | `docs/screenshots/`（9 张）、`docs/user_manual_zh_assets/screenshots/`（8 张）、`docs/undergrad_lab_assets/`（8 张，含主界面与各面板截图）+ 生成脚本 `scripts/capture_screenshots.py`。手册资产目前**没有生成脚本**，靠人工从 pipeline 输出与新截图拷贝 |
| **触发条件** | 在**没有可用字体**（或缺少 CJK 回退）的环境运行 `capture_screenshots.py`。脚本只做 `app.setFont(QFont("Microsoft YaHei UI", 9))`，既无字体可用性检查，也无回退字体链 |
| **表现** | 截图中所有文字渲染成 □□□□——**中英文都是**，界面只剩空控件框；手册与 README 的界面示意图变成不可读 |
| **影响面** | 根 `README.md`、`docs/SCRAM_BoxApp_中文用户操作手册.md`、`docs/SCRAM_BoxApp_本科教学实验手册.md` 都引用这些界面图；学生对照手册看界面时无法使用（约 25 处引用） |
| **证据** | ① 目视 `main_zh.png` / `main_en.png`：满屏方框（中英文皆然）；② `python scripts/linux/check_assets.py --render` 自动判定 **9/9 张坏图**——仓库内资产密度仅为同场景新鲜渲染的 4%–35%（如 `main_zh` 0.0115 vs 0.1242），该对比还抓到了密度启发式漏掉的 `results_view.png`（35%）；③ 密度异常共 24 张（三个目录各 8 张）；④ 截图生成于 `d8e539b`（2026-07-22），而 `app/` 之后在 `c9b6310`（2026-07-27）又改过 → 按 devkit §7 判据同时已过期 |
| **修复方向** | ① 生成前检查字体可用性（`QFontDatabase.families()` 是否含目标字体或 CJK 覆盖），不满足则直接失败并提示安装字体；② `setFont` 改为带回退链（Windows: Microsoft YaHei UI → SimSun；Linux: Noto Sans CJK SC）；③ 生成后自检（渲染已知文本，宽度等于缺字宽度即判为方框）；④ 在有字体的 Windows 上重生成截图并同步替换三处目录的资产与手册引用；⑤ 为手册资产补一个生成/同步脚本（当前靠人工拷贝），在 §7 触发（改了 GUI）时生成对比图，人工确认后替换 |
| **测试配置** | `python scripts/capture_screenshots.py --out install_logs/shots`，校验产物非方框后与 `docs/screenshots/` 对照 |
| **备注** | 由"资产过期检查"发现（`app/` 最后改动时间晚于截图生成时间）；属探测类 P9「资产完整性」的首个实例。P9 已接入 `auto_round.sh` 每轮自动跑（`scripts/linux/check_assets.py`），修复前每轮都会报 WARN，直到本 Bug 关闭 |
