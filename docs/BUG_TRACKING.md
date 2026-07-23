# SCRAM BoxApp Bug 追踪表

> 创建日期: 2026-07-23 | 最后更新: 2026-07-23 | 基于 tutorial_minimal / gmd_hazy_coag_cond / gmd_paris_emission_only 测试

## 修复状态

| # | 严重性 | 类别 | 状态 | 验证结果 |
|---|--------|------|------|---------|
| 1 | 🔴 P0 | 初始化 | ❌ 未修复 | `tag_init=0` 方案不可行（cfg 解析时 bin_values 已定型），需改 `default_config.cfg` 或模板系统支持 per-species mass |
| 2 | 🔴 P2 | 凝并 | ❌ P2 待定 | 需重编译 Fortran |
| 3 | 🟡 P0 | 运行 | ✅ 已修复 | `Simulation Time 1800s`（原 43200s） |
| 4 | 🟡 P1 | 初始化 | ✅ 已修复 | `Fixed Density 1.8E-6`（原 NaN） |
| 5 | 🟢 P2 | 凝并 | ❌ P2 待定 | 与 #2 合并修复 |
| 6 | 🟡 P1 | 绘图 | ✅ 已修复 | `generate_all()` 不再传错参 |
| 7 | 🔴 P2 | 重分配 | ❌ P2 待定 | 需重编译 Fortran |
| 8 | 🟡 P1 | 运行 | ✅ 已修复 | gmd_hazy 正确检测为 `failed`（原误报 `ok`） |

## Bug 总览

| # | 严重性 | 类别 | 简要描述 | 触发条件 | 修改文件 | Git 提交备注 |
|---|--------|------|---------|---------|---------|------------|
| 1 | 🔴 P0 | 初始化 | tutorial_minimal 初始质量为零，数量不为零 | `base="default"` + `Tag_init=1` + 全零 `bin_values` | `app/services/template_service.py` | `fix: tutorial_minimal 模板 tag_init=0，让 Hazy 分布自动生成质量` |
| 2 | 🔴 P2 | 凝并 | Prototype 模式 `coeff_build_pair_mapping` 拒绝零质量 cell | `mass=0` + `number≠0` + `with_coag=1` | `SRC/ModuleCoeffRepartitionBoxmodel.f90` | `fix: Prototype 模式零质量 cell 静默跳过保护` |
| 3 | 🟡 P0 | 运行 | Case Preset 时长未写入生成的 cfg | 所有 GUI 运行 | `app/services/run_service.py` | `fix: prepare_run 调用 _with_case_preset 确保时长写入 cfg` |
| 4 | 🟡 P1 | 初始化 | `fixed_density = NaN`（全零质量 + `tagrho=1` 除零） | `mass=0` + `tagrho=1` | `app/services/template_service.py` | `fix: 零质量模板默认 tagrho=0 避免除零 NaN` |
| 5 | 🟢 P2 | 凝并 | Legacy/Prototype 双轨制对零质量行为不一致 | `mass=0` + `with_coag=1` + 切换模式 | `SRC/ModuleCoagulation.f90` | `fix: Legacy/Prototype 零质量输入行为统一` |
| 6 | 🟡 P1 | 绘图 | GUI 单次运行不生成图片（传错参数） | GUI "运行"按钮 | `app/views/main_window.py` | `fix: _on_run_completed 传正确 results_root 给 generate_all` |
| 7 | 🔴 P2 | 重分配 | `euler_coupled` redistribution 零质量数据爆炸 30 倍 | `mass=0` + `with_cond=1` + `redistribution_method≥2` | `SRC/rdb/euler_coupled.f90` | `fix: euler_coupled 零质量保护` |
| 8 | 🟡 P1 | 运行 | Fortran 内部 STOP 返回 exit code 0，Python 误报成功 | Fortran 内部任何 STOP | `app/services/run_service.py` | `fix: 检测 run.log 异常关键字，标记 failed` |

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

### Bug #7: euler_coupled redistribution 零质量爆炸

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/rdb/euler_coupled.f90:254-260` |
| **触发条件** | `mass=0` + `number≠0` + `with_cond=1` + `redistribution_method≥2` |
| **表现** | 数量从 3.42B 爆炸到 102.6B（30倍），触发 `non conservation du nombre` 报错 |
| **影响面** | `gmd_hazy_coag_cond` 等同时开启冷凝和重分配的本模板 |
| **证据** | `run.log:75-87`: 法文数量不守恒报错 + 30x 数量跳变 |
| **修复** | Fortran 端加零质量输入保护，或 Python 端检测零质量时禁用 redistribution |

### Bug #8: Fortran STOP 返回 exit code 0

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py:160` + 多个 `.f90` 中的 `STOP` |
| **触发条件** | Fortran 内部 `STOP`（如 `euler_coupled.f90:270`） |
| **表现** | 模拟内部崩溃但 Python 报告 `status=ok` |
| **影响面** | 任何 Fortran 出错场景都被误判为成功 |
| **证据** | `gmd_hazy_coag_cond` 内部爆炸后 `performance_summary.csv` 仍显示 `status=ok` |
| **修复** | Python 端 `run_prepared` 后检查 `run.log` 是否含异常关键字（`non conservation`, `STOP`, `NaN`） |
