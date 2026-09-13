# SCRAM BoxApp Bug 追踪表

> **自主修复授权（2026-09-12）**：配置/契约层缺陷（base cfg、模板默认值、死控件、字段未落到核心）授权 agent 自主修复，路径限 app/**、examples/**、core/templates/**、core/defaults/**、scripts/linux/**、proposals/**、docs/checktest/**；每笔须附"数值影响证明 + 模板/契约体检输出 + 基线声明"三件套，并**先在本表登记**。物理口径/界面控件/发布资产/runtime-windows 源码仍须人工拍板（见 runbook §1）。
> **标签（2026-09-12 复核新增）**：每条另标 `port`（移植层，该修、计入闸门）/ `upstream`（本体固有，只记录、不计入闸门）/ `needs-domain`（需领域判断）。当前：upstream = #7、#2/#5、#14；needs-domain = #13；其余为 port。
> **结论三分类（2026-09-12 复核新增）**：`confirmed-bug`（有夹具+判据）/ `evidence-only`（证据已列、待人工定性）/ `unexplained`（如 Q-06 的 RH 跳变，不得以 clean 结案）。
> 创建日期: 2026-07-23 | 最后更新: 2026-09-11 | 本轮新增 #11（Case Preset 在运行路径覆盖过程开关与时长）；#10 登记人工决定（④ 暂缓，重生成按 25 张）

## 修复状态

| # | 严重性 | 类别 | 状态 | 验证结果 |
|---|--------|------|------|---------|
| 1 | 🔴 P0 | 初始化 | 🔄 已转自动复核（agent 权衡，2026-09-11） | 原 ❌ 未修复。2026-09-11 复核：触发条件（`base="default"` 的零质量骨架）**在应用里已不可达**——`c9b6310`（2026-07-27）把 `tutorial_minimal`/`gmd_hazy_condensation`/`gmd_hazy_coag_cond` 三个模板的基座从 `default` 改为 `teaching`（examples 配置，非零初值），实测 `tutorial_minimal` 终态质量 0.00148 = 手册基准，不再是 0。已备**夹具对** `docs/checktest/zero_initial_mass_{test,fixed}.cfg`（同结构，仅第 1 个物质第 1 个 bin 初值不同）与**自动判据**（`collect_metrics.py`：status=ok 且质量为 0 → 报警）。待 agent 按 hunt_plan Q-13 权衡"是否仍需修改/如何改"，并回答当年切基座时留下的疑点（Q-14：teaching 物种是否适合 GMD 冷凝验证） |
| 2 | 🔴 P2 | 凝并 | ❌ P2 待定 | 需重编译 Fortran |
| 3 | 🟡 P0 | 运行 | ✅ 已修复 | `Simulation Time 1800s`（原 43200s） |
| 4 | 🟡 P1 | 初始化 | ✅ 已修复 | `Fixed Density 1.8E-6`（原 NaN） |
| 5 | 🟢 P2 | 凝并 | ❌ P2 待定 | 与 #2 合并修复 |
| 6 | 🟡 P1 | 绘图 | ✅ 已修复 | `generate_all()` 不再传错参 |
| 7 | 🔴 P2 | 重分配 | 🟡 上游缺陷；**产品侧已消除**（模板默认值改回 method=2）；v4 补丁待人工决定是否给本体打 | 根因（2026-09-12 复核定位）：`euler_coupled.f90:378-400` 把 hand-out 累加器**重复交付**（累加器按 `kloc(k)` 索引、交付循环按源 bin 迭代；本相位 `kloc≡1` ⇒ 交出量被加回两次 → 数量净增 0.054% → 第 423 行 STOP）；另有 `euler_coupled.f90:244` 的 `RQ(k)/Q(k)`（空 bin）与 `ModuleThermodynamics.f90:264` 的 `log10(0)`（teaching 基座无 IH）两处无保护除法。**该文件与本体 `/home/yifeihu/SCRAM1.1` 逐字节一致 ⇒ 属上游缺陷，非移植引入**；实测本体 exe + method=6（仅改 cfg 第 7 行）同样报 `non conservation`，相对误差 9.6e-3。v1/v2/v3 guard 无效的原因：guard 条件在本相位恒假（要求 `kloc(k)>1`），"与 stock 逐位相同"是必然。**处置**：① 产品侧把 `gmd_hazy_coag_cond` 模板默认 `redistribution_method` 6→2（与本体/论文口径一致）→ 模板从 failed 变 ok（`install_logs/auto/template_audit/`）；② 若要保留 method=6 演示，则给本体打 `proposals/bug7_double_add_v4.patch`（已验证 failed→ok、精确守恒，按守卫 §1 属 Windows/人工侧动作）；③ 残留 Q-17（边界 hand-out 丢弃 9.8e-6）随补丁一起考虑 |
| 8 | 🟡 P1 | 运行 | ✅ 已修复 | gmd_hazy 正确检测为 `failed`（原误报 `ok`） |
| 9 | 🔴 P1 | 初始化 | ✅ 已修复（2026-09-11） | 已套用 `proposals/bug9_nucl_model5_file_pointer.patch`（nucl_model=5 时无条件读入那 3 行，不再跳过却不消费）；新核心 md5 `fb020540` 实测：标准格式（56 行）配置**跑通**，初始总质量 `226.07444159907240` 与 2026-07-27 记录一致；手工删行的 53 行版本作废（可留作负对照，补丁后应报错）。现行报错文本为 `Bad integer for item 1`（与 7 月记录的 `Bad real number in item 8` 不同） |
| 10 | 🟡 P1 | 文档资产 | ❌ 未修复 | **界面截图类资产共 24 张的密度异常**：`docs/screenshots/`（9）、`docs/user_manual_zh_assets/screenshots/`（8）、`docs/undergrad_lab_assets/`（8）文字全渲染为方框（中英文皆然）；被根 `README.md`、用户手册与教学手册引用。需在有字体的 Windows 上按 §7 重生成，并给生成脚本加字体可用性检查 |
| 11 | 🟠 P1 | 运行 | ✅ 已修复（2026-09-11） | 预设改为"建议值"：显式设置优先——`run_service.prepare_run/_with_case_preset` 接受 `explicit_keys`（须在 normalize 之前取出，normalize 只保留固定键）；GUI `_collect_data` 把"与当前预设建议值不同"的键标为显式；`probe_cell --set` 的键自动标记。验证：① `noop_probe.py --template tutorial_minimal` 关掉凝并后终态数量变化 5.3e-3（此前报"覆写未生效"）；② 完整标准测试数值**逐位**与基线一致（EXT 33.7511 / INT 32.7338，540/88 步，五项 smoke 全过）→ 行为保持 |
| 12 | 🟠 P1 | 运行/配置 | ❌ 未修复（2026-09-12 新发现） | GUI 的 `redistribution_option`（RDB 核心模式 legacy/core_conserv/core_nogrow/core_smallgrow）是**死控件**：app 仅经环境变量 `SCRAM_RDB_CORE_CONSERV`/`SCRAM_RDB_CORE_CONSERV_NAME` 传递（run_service.py:122-123），但编译的 Fortran（ModuleCoeffRepartitionBoxmodel.f90）只读 `SCRAM_COEFF_REPARTITION_MODE`（=映射方案，另一控件），对 RDB 核心模式**无任何变量/环境读取**，生成的 .cfg 也无此字段 → 选项永不生效。实测 gmd_paris_full（凝并开、540 步）四值终态**逐位相同**（EXT mass=33.751055266282556 / INT mass=32.73376655624839）。连带使 `docs/checktest/hazy_nogrow_{test,fixed}.cfg` 的 test/fixed 区分失效（二者 Fortran 可读字段逐字节相同）。已备夹具对 `redistribution_option_dead_{test,fixed}.cfg` 与 patch 提案 `proposals/bug12_rdb_core_mode_dead.patch` |
| 15 | 🟡 P2 | 运行/配置 | ❌ 未修（2026-09-12 复核发现，与 #12 同类） | 配置标量 `mapping_scheme`（`LEGACY`/`DETERMINISTIC_NEAREST`，模板与校验器都在用）**从不进入核心**：`run_service._coag_mapping_mode(scheme)` 收到的是**混合假设**（`INTERNAL_MIXING`/`EXTERNAL_MIXING`，见 `run_comparison` 的 `MIXING_ASSUMPTIONS` 循环），两者都不等于 `LEGACY` ⇒ 送给核心的 `SCRAM_COEFF_REPARTITION_MODE` **恒为 `COAG_TARGET_NEAREST`**。实测：手工把该 env 设为 `LEGACY` 跑 Mégapole/12h，终态与 `COAG_TARGET_NEAREST` **完全相同** ⇒ 该开关在当前配置下也观察不到影响。`run.log` 里记录的 `mapping_mode` 因此是固定值。GUI 的"mapping_scheme"下拉实际绑定的是混合假设（`main_window.py:214-218`），与这个标量不是一回事。**2026-09-12 22:15 轮夹具固化（Q-21）**：`probe_cell gmd_paris_condensation` 默认 vs `--set mapping_scheme=LEGACY` 两臂终态逐位相同（EXT mass=33.0654/INT mass=32.6176/number=3.44653e10/steps=42），两臂 `run.log` `mapping_mode` 均=`COAG_TARGET_NEAREST`、生成 cfg 无 mapping 字段 ⇒ 死配置确认；证据 `install_logs/auto/probes/q21_{default,legacy}/`，台账 `Q-21|mapping_scheme_env|app_to_core|contract`→bug |
| 16 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-12 复核发现，port；2026-09-13 Q-24 已定位根因，处置待人工） | GUI「环境状态」(init_scenario: 1 霾天/2 城市/3 清洁) **在出厂配置下无任何数值效果**：初值是否采用内置三套场景分布由 `tag_init`（初始化模式）决定，而所有基座 cfg 都是 `30 1`/`2 1`（=1，用配置里的逐档质量），且 `tag_init` 在 GUI 未暴露（用户改不了）。实测：`gmd_paris_full` 下 init_scenario=1/2/3 的 t=0 质量 21.583170063260344、数量 1.4625e10 **逐位相同**。**2026-09-13 Q-24 定位**：tag_init=0 臂三场景对照（gmd_paris_full,0.5h）status=ok 无 NaN/Inf、residual~1e-18，初值质量 2.560/2.581/2.587e-11（即本条注的 2.5e-11，是初值气溶胶质量，场景对数正态初值本应可忽略，非缺陷），终态质量 EXT 11.1139/11.1076/11.1028（来自冷凝 Mass Cond~11.09）三场景不同 ⇒ tag_init=0 路径数值可用、三场景确实产生差异 ⇒ 控件非设计性死，仅被未暴露的 tag_init 门控。历史依据：控件由 `321fca2`（2026-07-22）加入，对应 ModuleDiscretization.f90 三种三模态对数正态分布；`05d609c` 曾判定"tag_init=0 方案不可行"（Q-24 已证伪：路径可用）。处置（待人工，属"增删控件"类）：a) 场景与 tag_init 联动（**Q-24 已证可行**）；b) 暴露 tag_init 并标注条件；c) 移除下拉 |
| 17 | 🟡 P2 | 运行/配置 | ❌ 未修（2026-09-12 复核发现，upstream） | **普通模式排放窗口只有 2.64376e3 s（≈44.06 min）**，与模拟时长无关：`ModuleDiscretization.f90:1194-1205` 在 `nucl_model=5` 时 `time_emis=43200 s`，否则 `2.64376e3 s`；超出后 `emis_dt=0` ⇒ 停止排放。另两处同常数（:1274/:1287）只是"排放引起的步长限制"守卫，**不关闭凝并/冷凝**。代码无注释、全仓与本体无其它引用 ⇒ 判为作者为某场景调死的经验值。影响：本体论文 cfg（`INIT/cfg_megapole_01072009.cfg`）emission 全 0 ⇒ 其结论不受影响；仓库 baseline 基座 SO4 emission=1.72e-5 ⇒ 12h 只有前 44 分钟在排放。处置（待人工）：a) 与本体口径一致把 emission 置 0；b) 新增"排放时长可配"（新功能）。**2026-09-13 05:xx 轮数值确认（Q-23）**：`gmd_paris_emission_only` 全关过程 12h vs 0.5h 两臂，排放 delta 比值=0.6808484885=1800/2643.76 逐位精确 ⇒ 窗口 2643.76 s 确认、排放窗口内线性；upstream 固有，非移植缺陷，不计入 gate。证据 `install_logs/auto/probes/q23_emis_window_{12h,05h,30min}/`|
| 13 | 🟠 P1 | 初始化/混合假设 | ❌ 性质待判（2026-09-12 复核发现） | 零质量/微质量配置下 **EXT/INT 终态粒子数差 4 个数量级**：`docs/checktest/zero_initial_mass_test.cfg` → EXT `final_number=0.0` 而 INT `4.12452e9`；`tiny_initial_mass` → EXT `4.99998e5` 而 INT `4.12452e9`。证据：`install_logs/auto/probes/q07_zero_mass_test|q07_tiny_mass/probe.json`（2026-09-12 10:11 轮）。同一物理设置两侧不应差 4 个数量级 → 建议按 `_test/_fixed` 夹具登记后定性 |
| 14 | 🟡 P2 | 重分配 | ✅ 已判：设计使然（上游固有，2026-09-13 源码+数值分类，Q-19 关闭） | `redistribution_method=3/5` 下**粒子数暴增**：`gmd_paris_condensation + method=3` → EXT `5.28349e12`/INT `6.15417e12`，method=2 为 `3.44565e10`（**×153**）；method=5 → `1.07e11`（×3）；质量基本不变。同现象在 `fuzz_q11/fuzz_report.json` 里已存在（idx 9 达 ×383）却被判 clean——因为判据只查质量残差。euler_mass/hemen 本非数量守恒，故属"设计使然 vs 缺陷"待人工判定，但必须先入台账 |
| 18 | 🟠 P1 | 保真度/gate | ❌ gate 未达标（2026-09-13 Q-26 新发现，port 标签，计入 gate） | **移植保真度 gate 实际未达标**：同一本体规范 cfg（`~/SCRAM1.1/INIT/cfg_megapole_01072009.cfg`，coef_s5_f3_b7.nc，12h）跑本体 exe（sha256 `71473328`）与仓库 exe（sha256 `f03b90aa`，stock）：总质量**逐位一致** `36.48929720841787`（bit-identical，达标）；但气溶胶质量 `24.22834256300118` vs `24.22867515785633`，**相对差 `1.373e-05` > gate 阈值 `1e-5` ⇒ gate_pass=False**（未达标）。气相 `2.713e-05`、Mass Cond `1.258e-04`、total_water `4.320e-05`。**新发现**：手工轮（runbook P4 / 台账 `fidelity|upstream_vs_devkit|megapole12h`）把 `1.4e-5` 记为 clean，但按 release gate 阈值（气溶胶质量差 ≤1e-5）实际未达标——差异源于 `-g` vs `-O2` 编译标志（非代码改动），属"阈值/口径"问题而非移植缺陷。**处置（待人工，不得自行放宽阈值）**：a) 维持 1e-5 并给本体/仓库统一编译标志（重编译对齐）；b) 调整阈值并记录依据；c) 以"总质量逐位一致"为硬判据、气溶胶差为软信号（改 gate 定义）。已脚本化 `scripts/linux/fidelity_check.py`（建议挂 deep 轮）。证据 `install_logs/auto/fidelity_check/20260913-082220/` + `install_logs/auto/fidelity_q26/`；台账 `Q-26|fidelity_gate|upstream_vs_repo|contract`→bug |

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
| 12 | 🟠 P1 | 运行/配置 | `redistribution_option`（RDB 核心模式）死控件：app 经 env 传递但 Fortran 不读，四值终态逐位相同 | `redistribution_option` 任意值 + 任意模板 | `SRC/ModuleCoeffRepartitionBoxmodel.f90`（需新增 env 读取）+ `app/services/run_service.py` | `fix: Fortran 读取 SCRAM_RDB_CORE_CONSERV 并接入 RDB 核心模式分支` |

### 实测模板对照表（base="teaching"，非零初始质量，2026-07-27）

| 模板 | Case Preset | 过程 | redist. method | final_mass | final_number | 状态 | 结论 |
|------|------------|------|---------------|------------|-------------|------|------|
| tutorial_minimal | coag_only | 仅凝并, 0.25h | 2 | 0.00148 | 4.11B (−10.99M) | ✅ | 凝并正常，质量守恒 |
| gmd_hazy_condensation | gmd_hazy_condensation | 仅冷凝, 12h | 2 | 0.000174→（2026-09-12 起接论文源）| — | ✅ | **已修**：原 teaching 基座（2 物种）接不到论文源 ⇒ 冷凝空转（Q-18）；改用 `base=baseline`（30 物种，`ESO4=4`）+ `nucl_model=5`（本体自带的论文验证开关，硬编码 `gas_emision_rate(ESO4)=2.29e-4 µg/m³/s` = 5.5 µm³/cm³/12h）⇒ `Mass Cond=2.919`，模板名副其实 |
| gmd_hazy_coag_cond | coag_cond | 凝并+冷凝, 12h | **2**（原 6）| — | — | ✅ | 2026-09-12：默认 method 6→2（本体/论文口径）⇒ 不再崩溃；同时接上论文源（base=baseline + `nucl_model=5`），`Mass Cond=1.388` |

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
| **patch 验证（2026-09-12 16:2x 轮，Q-15）** | `proposals/bug7_euler_coupled_divzero.patch`（循环顶部 `diam(k)<=0 .OR. d(kloc(k))<=0` → CYCLE）**编译验证失败**：变异二进制 sha256=038d81c9…（≠stock f03b90aa…，euler_coupled.f90 已重编译，run.log 确认调用变异 exe）跑 `gmd_hazy_coag_cond + method=6` 仍 `status=failed`、step0 `IEEE_DIVIDE_BY_ZERO`+`non conservation du nombre total`、`1-N_new/N_old=5.4167e-4`（与 stock 逐位相同）→ **patch 无效**。根因细化：guard 只查 `diam(k)`/`d(kloc(k))`，但除零实际来自 `DQ=1-(d(kloc(k))/d(kloc(k)-1))^3` 的 **`d(kloc(k)-1)=0`**（下边界 bin 直径为 0，未被 guard 覆盖）→ 需改 guard 同时检查 `d(kloc(k)-1)`（或 `kloc(k)==1` 分支的 `dbound(1)`）。patch 需重做，物理判断待人工 |
| **patch 验证 v2/v3（2026-09-12 17:2x 轮，Q-15 后续）** | v2 `proposals/bug7_euler_coupled_divzero_v2.patch`（guard 增 `d(kloc(k)-1)`/`d(kloc(k)+1)`）与 v3 `proposals/bug7_euler_coupled_divzero_v3.patch`（v2 基础 + 退化 bin guard `d(kloc(k))==d(kloc(k)±1)`）均经变异构建验证**无效**：v2 变异 exe sha256=63e4cc5b…、v3=1e29e83d…（均≠stock f03b90aa…，euler_coupled.f90 已重编译），跑 `gmd_hazy_coag_cond + method=6` 仍 `status=failed`、`IEEE_DIVIDE_BY_ZERO`、`1-N_nouveau/N_ancien=5.4167525032922104E-004`（与 stock **逐位相同**）→ 三道 guard 均未 CYCLE 任何 bin。**关键结论：除零不在 euler_coupled.f90 的 `DO k=1,ns` 循环内**（v1/v2/v3 覆盖该循环全部原始直径与退化 bin 均无效）。run.log 的 `Note: IEEE exceptions` 是全局浮点陷阱报告，真实除零源需另行定位（候选：redist_euler.f90 调用前的 d_before/d_after 计算、或 isorropia/condensation 路径）。Q-05/Q-15 的"euler_coupled 除零"根因归属需修正。method=2 临时规避仍有效 |

| **根因修正（2026-09-12 21:xx 人工复核，推翻上面两行）** | 用 `-ffpe-trap=zero,invalid,overflow` 重编译（树 `/tmp/bug7_fpetrap/scram`，未动仓库运行时）后：首个浮点异常在 `ModuleThermodynamics.f90:264`（`total_PH=-log10(...)`，`total_IH=0` ⇒ `log10(0)`），加保护后陷阱落到 `euler_coupled.f90:244`（`RQ(k)/Q(k)`）；插桩打印证明失败来自**重复交付**（`kloc≡1`、交出量 H 与交付后净增 +H 十位有效数字吻合）。证物：`install_logs/auto/bug7_fpetrap{,2,3,4,5}/`（分别为首个 FPE 定位、log10 加保护后、重复交付插桩、修后陷阱构建、修后出厂构建）。**v1/v2/v3 的"除零不在循环内"结论不成立**——guard 条件在本相位不可达，逐位相同是必然 |
| **Q-17 插桩验证 + Q-27 新发现（2026-09-13 15:xx 轮）** | ① **Q-17 边界丢弃假设被推翻**：v4 修复+Q17 边界丢弃计数器（变异 exe sha256 `9b27cbcd`≠stock `f03b90aa`）跑 `gmd_hazy_coag_cond + method=6` 满 512 步，边界 hand-out 丢弃计数器（`N_2evap_esp(1,·)`/`N_2cond_esp(ns,·)` 未交付部分）EXT/INT 全程=0.0（0 步非零）⇒ 反证判据「计数>0 且与残差量级吻合⇒边界丢弃」未满足，**边界 hand-out 丢弃不是残差源**。**2026-09-13 复核更正：原"另有残差源"及随后登记的 Q-27"v4 未完整守恒数量"均作废**。② **Q-27 = 误报（已判 clean，人工复核请求撤销）**：`1-N_new/N_old` 的打印点是**交付给邻居之前**的中间量（`euler_coupled.f90:373`，上游该处 :377 即 `!STOP`），按 `AN/BN+CN/DN≡1` 互补关系，其值恒等于本次调用的 hand-out 比例，不是守恒残差；真正的交付后判据在 `:424/:428`（活 STOP），v4 跑满 512 步**全程 0 次触发**（v4 日志 `non conservation du nombre total` 计数 0；stock 同 cfg 8 次并 STOP）⇒ **v4 修复后数量守恒**。原记 9.77e-6 与 5.4168e-4 同出 `bug7_fpetrap5`（含 v4 主体）**同一判据点、两个不同子群体**，"降 55 倍"的对照不成立；峰值实测 0.877（非 0.67）。故 **v4 补丁仍然有效，仍按提案流程由人工/Windows 侧落盘**。附带修好 `scripts/linux/probe_cell.py` 的致命关键字误判（只认 "…total !!"，排除信息性 "sans STOP"）。证据 `install_logs/auto/{q17_boundary,q17_boundary_stock,bug7_fpetrap5}/`、`/tmp/bug7_fpetrap/scram` |
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
| **修复方向** | ① 生成前检查字体可用性（`QFontDatabase.families()` 是否含目标字体或 CJK 覆盖），不满足则直接失败并提示安装字体；② `setFont` 改为带回退链（Windows: Microsoft YaHei UI → SimSun；Linux: Noto Sans CJK SC）；③ 生成后自检（渲染已知文本，宽度等于缺字宽度即判为方框）；④ 在有字体的 Windows 上重生成截图并同步替换三处目录的资产与手册引用——**2026-09-11 人工决定：暂缓，待 Windows 有空时执行**；⑤ 为手册资产补一个生成/同步脚本（当前靠人工拷贝），在 §7 触发（改了 GUI）时生成对比图，人工确认后替换 |
| **测试配置** | `python scripts/capture_screenshots.py --out install_logs/shots`，校验产物非方框后与 `docs/screenshots/` 对照 |
| **备注** | 由"资产过期检查"发现（`app/` 最后改动时间晚于截图生成时间）；属探测类 P9「资产完整性」的首个实例。P9 已接入 `auto_round.sh` 每轮自动跑（`scripts/linux/check_assets.py`）。**2026-09-11 状态更新**：①③⑤ 已落地（`scripts/capture_screenshots.py` 字体回退链 + 生成后密度自检；`scripts/linux/sync_manual_assets.py` 漂移检查，默认 dry-run）；④ 按人工决定暂缓；P9 已把本 Bug 相关告警归入「已知项」单独计数——每轮 digest 显示 `WARN（仅已知项）`，只有出现**新**告警才显示 `WARN（有新增）`。**数量复核**：密度阈值抓到 24 张，`--render` 对比另判 `results_view.png` 为坏图（密度仅为同场景新渲染的 35%，属部分缺字），故 Windows 重生成时请按 **9+8+8=25 张**全量处理 |

### Bug #11: Case Preset 在运行路径上静默覆盖过程开关与运行时长

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py:308-315`（`_with_case_preset`）与调用点 `app/services/run_service.py:97-101`（`prepare_run`）。调用点上方注释（第 93-94 行）写的是 "Normalize without forcing preset values / the user may override them"，与代码实际行为相反 |
| **触发条件** | 任何带 `case_preset` 的配置（模板都自带）走 `prepare_run`：先套预设、再序列化 cfg，调用方设置的开关/时长已被预设覆盖 |
| **表现** | ① **用户可见**：GUI 里取消"启用凝并"（或改"模拟时长"）后运行，仍按 Case Preset 的过程与时长执行——用户设置被静默忽略；② **调试证据面**：`probe_cell.py --set with_coag=0` / `with_cond=1` / `duration_hours=…` 不生效，生成 cfg 仍是预设值，探测结论变成"什么都没测到"却记为 clean |
| **影响面** | 用户可见（GUI 过程开关与时长）；调试证据面：2026-09-10/11 期间凡用 `--set` 改这三个开关或时长的探测格，其"干净"结论不成立，需用加了校验的工具重探；与 Bug #3（2026-07-22 标 ✅ 已修复）同源——原修复只覆盖了 GUI 的"载入预设"路径，运行路径仍在强制套用 |
| **证据** | ① 代码：`_with_case_preset` 对四个键无条件赋值；② 复现：`.venv/bin/python scripts/linux/probe_cell.py --template tutorial_minimal --set with_coag=0` → `~/.cache/scram_boxapp_mixing/generated_configs/tutorial_minimal_internal_mixing.cfg` 第 2 行仍为 `1 ## coagulation switch`；`--set with_cond=1` 同样仍为 0；③ 对照：`--set dtmin_seconds=2` 正常落地（该键不受预设管制）→ 证明不是"所有覆写都无效"，而是被预设管制的四个键 |
| **修复方向** | ① `_with_case_preset` 仅在调用方**未显式设置**该键时填预设值（可加 `data["explicit_keys"]` 或比较 GUI 当前值）；或 ② 只在用户显式"载入预设"时套用、运行时不覆盖；③ 加回归测试：翻转任一过程开关后终态质量/数量必须改变——判据已由 `scripts/linux/noop_probe.py` 实现，修好后应全部报"有效" |
| **测试配置** | `.venv/bin/python scripts/linux/noop_probe.py --template tutorial_minimal`（现在报"覆写未生效：生成 cfg 里该开关仍为 1"；修复后应报"被检查的开关都真实起作用"） |
| **备注** | 由新增的"空转探测"工具（`scripts/linux/noop_probe.py`）首次运行即发现；`probe_cell.py` 已加"覆写落地校验"（跑完核对生成 cfg），此后同类静默丢弃会直接报错并计入 findings，不会再被误记为 clean |

### Bug #12: `redistribution_option`（RDB 核心模式）是死控件（app 传 env，Fortran 不读）

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py:122-123`（写 env `SCRAM_RDB_CORE_CONSERV`/`SCRAM_RDB_CORE_CONSERV_NAME`）vs `core/executables_or_wrappers/runtime/windows/source/SCRAM1.1/SRC/ModuleCoeffRepartitionBoxmodel.f90`（`coeff_boxmodel_init` 只读 `SCRAM_COEFF_REPARTITION_MODE`，无 RDB 核心模式读取） |
| **触发条件** | GUI 选择任意 `redistribution_option`（legacy/core_conserv/core_nogrow/core_smallgrow）后运行 |
| **表现** | 四个选项产生的终态**逐位相同**：gmd_paris_full（凝并开、EXT 540 步/INT 88 步）EXT mass=33.751055266282556、number=1.1638880310e10，INT mass=32.73376655624839、number=1.0260805990e10，anomaly/residual 全同；gmd_paris_condensation 与 gmd_hazy_coag_cond 同样四值相同 |
| **根因** | app 把 `redistribution_option` 映射为 int（`_rdb_core_mode`，RDB_CORE_MODE_MAP legacy=0/core_conserv=1/core_nogrow=2/core_smallgrow=3）后**只放进环境变量**；但 Fortran 核心不读这两个 env（`coeff_boxmodel_init` 仅读 `SCRAM_COEFF_REPARTITION_MODE`/`SCRAM_COEFF_CACHE_MODE`/`SCRAM_RESULTS_DIR`/`SCRAM_TESTCASE`/`SCRAM_PROCESS_COMBO`/`SCRAM_SCHEME_NAME`/`SCRAM_DEBUG`），且生成的 `.cfg` 无该字段 → 选项永远不进入 Fortran |
| **易混淆点** | `SCRAM_COEFF_REPARTITION_MODE` 是**映射方案**（mapping_scheme：LEGACY/COAG_TARGET_NEAREST 等），由 `_coag_mapping_mode(scheme)` 产生，与 `redistribution_option`（RDB 核心模式）是**两个不同控件**；前者 Fortran 有读，后者没有 |
| **影响面** | ① GUI 的 RDB 核心模式选择器对用户无效（误导）；② 既有夹具 `docs/checktest/hazy_nogrow_{test,fixed}.cfg` 的 test/fixed 区分失效（二者 Fortran 可读字段逐字节相同，仅注释不同）；③ 任何基于"切换 RDB 核心模式应改变结果"的探测/验证都无效 |
| **证据** | 2026-09-12 轮：`probe_cell --template gmd_paris_full --case gmd_paris_full --set redistribution_option=<4 值>` 四组 probe.json 终态逐位相同；`grep -rn RDB_CORE_CONSERV SRC/` 无匹配；`diff` 两夹具 Fortran 可读字段 IDENTICAL |
| **修复方向** | 二选一（需人工定夺）：A) Fortran 侧新增 `get_environment_variable('SCRAM_RDB_CORE_CONSERV')` 并接入 RDB 核心模式分支（真正启用该控件）；B) 若该控件本就不该存在，则从 GUI/schema 移除并清理 env 传递。patch 提案见 `proposals/bug12_rdb_core_mode_dead.patch`（方案 A 的最小骨架，未编译验证） |
| **回归资产** | `docs/checktest/redistribution_option_dead_{test,fixed}.cfg`（Fortran 可读字段逐字节相同，仅注释不同；修复后两文件应产生不同终态） |
