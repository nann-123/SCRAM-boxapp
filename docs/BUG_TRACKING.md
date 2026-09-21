# SCRAM BoxApp Bug 追踪表

> **自主修复授权（2026-09-12）**：配置/契约层缺陷（base cfg、模板默认值、死控件、字段未落到核心）授权 agent 自主修复，路径限 app/**、examples/**、core/templates/**、core/defaults/**、scripts/linux/**、proposals/**、docs/checktest/**；每笔须附"数值影响证明 + 模板/契约体检输出 + 基线声明"三件套，并**先在本表登记**。物理口径/界面控件/发布资产/runtime-windows 源码仍须人工拍板（见 runbook §1）。
> **标签（2026-09-12 复核新增）**：每条另标 `port`（移植层，该修、计入闸门）/ `upstream`（本体固有，只记录、不计入闸门）/ `needs-domain`（需领域判断）。当前：upstream = #7、#2/#5、#14；needs-domain = #13；其余为 port。
> **结论三分类（2026-09-12 复核新增）**：`confirmed-bug`（有夹具+判据）/ `evidence-only`（证据已列、待人工定性）/ `unexplained`（如 Q-06 的 RH 跳变，不得以 clean 结案）。
> 创建日期: 2026-07-23 | 最后更新: **2026-09-21** | 本轮：**nl=5 初始化口径专项审查**（补齐 #28 因果链；新登记 **#29**＝nl=5 多列分支重复投放；两个历史基线数字作废；撤回一条误判。完整报告 `docs/nl5与bug28审查_20260921.md`）——上一轮：**#9 归因更正 + 修复方向反转**（原记为内核「跳过却不消费」缺陷并改了 `ModuleDiscretization.f90`；实为 Python 写入器未复刻内核契约 ⇒ 现回退内核改动、只改 py 侧，**Windows 发行核无需重编译**）；此前 #19–#27（界面契约层体检：`explicit_keys` 丢失、`tag_thrm`/`dtmin` 死标签、`kind_composition` 被强制归零、归档 cfg ≠ 执行 cfg、混合假设恒为外混、方法号越界致核心死循环）；#11（Case Preset 在运行路径覆盖过程开关与时长）；#10 登记人工决定（④ 暂缓，重生成按 25 张）
>
> **标签体系待修改（2026-09-14 建议）**：现行 `upstream` 标签把三类性质完全不同的东西混在一起，建议拆为 `upstream-defect`（真实现错误，如 #7 → 需动核心）、`undefined-domain`（模型未定义域，如 #2/#5/#13 → 收权限即可消掉，不需要改核心）、`by-design`（有意为之，如 #14/#17 → 什么都不用做）。理由见 #19–#24 登记说明。
> **2026-09-20 追加第四类 `port-defect`（移植契约缺陷）**：#9 原被归入 `upstream-defect` 并据此改了内核，实为**移植方未复刻内核约定** ⇒ 内核不该动，只需改 py 侧。判据（可复用）：**本体源码 `/home/yifeihu/SCRAM1.1` 的读取语句序列与仓库内核一致 ⇒ 缺陷必在移植侧**；`scripts/linux/config_roundtrip.py` 的 B 节已在自动比对这条。
> ⚠️ 注意判据用**语句序列**而非逐字节：`ModuleDiscretization.f90` 在移植时被重排过缩进（全文 230 处差异，另有 `use CoeffRepartitionBoxmodel`、`Coefficient_file` 长度 40→256、`allocate(density_aer_size(N_size))` 等少数真实移植改动），逐字节比对会把格式差异误判成逻辑偏离。
>
> **2026-09-20 工具链收口（阅读本表前请先看这条）**：本表是**缺陷台账**，予以保留；但它大量引用
> 的下列内容**已随 Linux 自动排查工具链一并移除**，相关引用均为**历史记录**（可从 git 历史找回）：
> - 排查脚本：`scripts/linux/` 下的 `auto_round.sh`、`collect_metrics.py`、`probe_cell.py`、
>   `probe_suggest.py`、`noop_probe.py`、`fuzz_invariants.py`、`template_audit.py`、
>   `config_roundtrip.py`、`fidelity_check.py`、`check_assets.py`、`audit_plots.py`、
>   `check_windows_parity.sh`、`sync_manual_assets.py`
> - 文档与夹具：`docs/linux_debugging/`、`docs/checktest/`、`proposals/`
> - 保留：`scripts/linux/build_runtime.sh`（构建 Linux 内核）、`scripts/run_standard_tests.py`、
>   `scripts/check_field_registry.py` + `core/schema/gui_fields.json`
>
> 收口理由：多轮测试表明 **SCRAM 核心代码本身几乎没有问题**，绝大多数缺陷是移植层缺陷与静默控件
> （死控件/被覆盖的界面选项），因此自动化排查的边际收益已耗尽。

## 2026-09-20：升级到 SCRAM 1.2（本轮头条）

内核由 **SCRAM1.1 升级为 SCRAM1.2**，源码树同时改名
`core/executables_or_wrappers/runtime/windows/source/SCRAM1.1` → `.../SCRAM1.2`。
来源：`/home/wangfangyuan/SCRAM1.2`（作者说明见该树的 `UPDATE_SCRAM1.2.md`，已一并纳入）。

### 1. 79 文件 sha256 对照实验（作者声称"原始文件未改动"的复核）

作者在 1.2 树里留下 `ORIGINAL_SOURCE_SHA256.json`（79 条：`INC/`5 + `INIT/`7 + `SRC/`66 + 根 1），
两份 receipt 均记 `original_files_verified: 79` / `original_files_changed: []`。

**独立重跑结果：65 一致 / 11 不一致 / 3 缺失。**

- 11 不一致 = 1.2 **有意改写**的文件：`SConstruct`、`SRC/AtmoData/Aerosol.f`、
  `ModuleAdaptstep`、`ModuleBulkequibrium`、`ModuleCoagulation`、`ModuleCoeffRepartitionBoxmodel`、
  `ModuleCondensation`、`ModuleDiscretization`、`ModuleInitialization`、`ModulePhysicalbalance`、
  `ModuleRedistribution`
- 3 缺失 = 清理步骤删除：`ModuleBulkequibrium.f90.old`、`manual_compile.log`、`manual_compile3.log`
  （后两者 sha 为**空文件的 sha256**，即本来就空）
- 清单 mtime `2026-09-17 21:03`，而上述 `.f90` 改动在 `2026-09-18 08:27–08:39`
  ⇒ **清单是"升级前快照"，不是"与 1.1 相同"的证明**；receipts 的 `original_files_changed: []`
  应理解为「**2026-09-18 的目录清理步骤没有改动这些文件**」
- ⚠️ 该实验**无法按原设计复跑**：生成/校验脚本已不在 1.2 树内，且 `SCOPE_REVIEW_RECEIPT.json`
  引用的 `.backups/before_scope_review_20260918` 已被清理删除（见 `validation/CLEANUP_20260918.json`）
- 建议：请作者按当前树重生成清单与 receipt，并保留校验脚本

### 2. 移植层回合并

| 项 | 处理 |
|---|---|
| **`coeff_make_dir` 平台分支（阻塞级）** | 1.2 删掉了该子程序，改成无条件 `execute_command_line('mkdir -p …')`，全树无 `OS`/`windir` 判断 ⇒ **Windows 上建目录会失败**。已回合并（POSIX `mkdir -p` / Windows `cmd /c if not exist … mkdir …`），并加注释说明缘由 |
| `Coefficient_file`/`configuration_file` 长度 256 | 1.2 **已自带**，无需再改 ✅ |
| `isorropia/isocom.f`、`isrpia.inc` | 仅**行尾差异**（仓库 LF / 1.2 CRLF），内容逐字节相同 ✅ |
| `COEFF_REPARTITION/`、`INC/`、`coef_*.nc` | 完全相同 ✅ |
| `COEFF_REPARTITION/example/ORIGIN.txt` | 仓库专有（子模块转普通目录的说明），保留 |
| `INIT/cfg_megapole_01072009.cfg` | 1.2 第 1 行由系数文件名改为 `COAG_TARGET_NEAREST`（模式名）。内核两版处理逻辑相同（按扩展名判是否 `ReadCoefficient`）⇒ 语义兼容，但默认口径变了 |
| `INIT/cfg_cond_only.cfg` | 1.2 新增，已纳入 |
| `tests/`、`ORIGINAL_SOURCE_SHA256.json`、`UPDATE_SCRAM1.2.md` | 作者自带验证资产，已纳入留档 |
| `ModuleBulkequibrium.f90.old`、`rdb/redist_euler.f90~` | 备份垃圾，未纳入 |

引用同步：`source/SCRAM1.1` → `SCRAM1.2` 共 **11 处**（`run_service.py`、
`check_field_registry.py`、`build_runtime.sh`、`runtime/{linux,windows}/README.md`、
根 `README.md`×3、`docs/shared_runtime_layout.md`、`docs/windows_devkit_readme_zh.md`、
`WINDOWS_DEVKIT_README_zh.md`、`config_model.py` 注释）。
`.gitignore` 用的是 `runtime/*/source/**/ProgramSCRAM` 通配，无需改。

### 3. 验证结果

| 项 | 结果 |
|---|---|
| Linux 内核构建 | ✅ `bash scripts/linux/build_runtime.sh safe`，0 error；md5 `a60700a9`（连跑两次一致，可复现） |
| 标准测试 | ✅ `import_smoke` / `gui_smoke` / `report_smoke` / `runtime_smoke` / `standard_tests` 五项全过 |
| **Bug #9** | ✅ **仍修复**。两个 `nucl_model=5` 模板的 cfg 被内核正确解析（53 行契约成立），不再出现 `Bad integer/real in list input` |
| 全模板扫描（7 模板 × 2 臂） | ⚠️ **5 个模板正常，2 个失败** —— 见下方新 Bug #28 |

### 4. 新 Bug #28：`nucl_model=5` + 外混触发 1.2 新增的硬 STOP

| 项目 | 内容 |
|---|---|
| **严重性** | 🔴 P1（阻塞 2 个模板的外混臂；影响 `gmd_hazy_condensation`、`gmd_hazy_coag_cond`） |
| **归属** | ⚠️ **上游 `nucl_model=5` 设计洞（不是 1.2 缺陷、也不是我们 cfg 的错）**：该模式声明"不需要 `init_bin_number`"并跳过读它，但初始化分支 `ModuleDiscretization.f90:668-678` **仍在消费它** ⇒ **读未初始化内存**。1.2 只是把「静默用垃圾值」变成「显式 STOP」 |
| **位置** | 消费点 `SRC/ModuleDiscretization.f90:668-678`（该块**1.1 就有**，HEAD 的 1.1 在 `:656`）；暴露点 `SRC/ModuleRedistribution.f90:127-136`（1.2 新增检查） |
| **判据** | `(number(k)<=0 .and. sum(packed(k,:))>0) .or. (number(k)>0 .and. sum(packed(k,1:N_species))<=0)` ⇒ `error stop 'SCRAM1.2: orphan mass/number before remap'` |
| **触发条件** | `nucl_model=5` **且** `tag_external=0` **且** `N_frac>1`（外混臂正好满足）。内混臂（`N_frac=1`）不走该分支 ⇒ 正常 |
| **完整根因链（已逐环验证）** | ① nl=5 的 cfg **不含** `init_bin_number` 行（作者约定 + 我们 #9 修复后的 53 行写法，实测"含 initial bin number 的行数 = 0"）；② 内核 `:145` 的读取在 `if(nucl_model.ne.5)` 守卫内 ⇒ **nl=5 时从不读**，而 `:131` 只 `allocate` 不初始化 ⇒ 数组内容未定义；③ `:675` 却写 `concentration_number(j) = init_bin_number(k)`，同时 `:674` 把完整逐物种 `init_bin_mass(k,s)` 写进同一单元 ⇒ **有质量、数浓度取未定义值**；④ 本机该值恰为 0（k=7）⇒ 1.2 新检查判为 orphan ⇒ STOP |
| **表现** | 外混臂第 1 步 `Calculation in progress...` 之后立即 `ERROR STOP`，`status=failed`、`steps=1` |
| **实测定位（诊断构建）** | 触发点 `f=1, k=7`：该单元 `number=0` 但 `dry=1.2603962185956201`（完整 30 物种初值，`ESO4=0.06165`、`EBC=0.03126`）；同 k 的 `f=2` 全零；`f=3` 才是 nl=5 分支写的（`number=1922513.43`、`EBC=117.98`） |
| **影响** | ① 两个 hazy 模板的外混臂在 1.2 默认配置下**完全无法运行**；② **更重要的历史含义**：1.1 时代这两个模板的外混臂"跑通"是**建立在未初始化内存之上的**，其数值（`Mass Cond` 2.919 / 1.388 等）**不可信**；③ 论文恒定硫酸盐源（`gas_emision_rate(ESO4)=2.29D-4`）的验证暂时做不了 |
| **★ 对照实验（决定性）** | 设 `SCRAM_REDISTRIBUTION_MODE=legacy` 后同一案例 EXTERNAL 臂 `status=ok`（`mass=230.513076054`、`number=33771839324`）⇒ 差别**只在检查的存在与否**，不在初值数据。`conservative_remap12` 默认 `.true.`（`:86`），`scheme>=2` 时无条件走新内核（`ModuleRedistribution.f90:62-65`） |
| **正确的修法（供作者参考）** | **不要**改回 `:145` 的条件读（那会破坏作者自己的 nl=5 约定，也是我们 #9 刚回退的方向）。应二选一：a) `:668-678` 分支在 nl=5 时改用 `number_init(k)` 作为数浓度来源；b) 让 nl=5 的 cfg 契约包含 `init_bin_number`（即约定改为"必须带"）。定性权在作者 |
| **旁证** | 分数档循环用 `do f=1,N_fracmax`（=20），而 `N_frac=3` ⇒ 访问未使用档位。⚠️ 注意：**legacy 路径也循环 `N_fracmax`**，所以这不是 1.2 引入的问题（此前记录有误，已更正）。`N_fracmax`/`N_frac` 错配仍值得作者一并检查 |
| **附带结论** | **Bug #7 在 1.2 默认配置下已被绕过**：`scheme>=2` ⇒ 走新内核 ⇒ 有缺陷的 `euler_coupled.f90` 不再被调用。因此 `bug7_method6_v5.patch` 随 1.2 升级一并作废（保留在 git 历史） |
| **处置** | **需作者拍板**：a) 确认 nl=5 + 外混是否本就不该用（若是，产品侧把这两个模板改成内混或移除外混臂）；b) 若应可用，则需修 `redistribution_size12` 的判据或 nl=5 初始化补 `f=1` 档的数浓度。**不得自行放宽核心判据** |
| **★ 有必要修吗（本轮评估）** | **必须登记，但产品侧不宜自行改内核。** 理由：① 触发面窄（仅 nl=5 × 外混）**但后果重** —— 1.1 时代该组合"跑通"是建在未初始化内存上，数字不可信；② 触发**可达**：GUI 上"比较内混/外混"按钮就会走到；③ 修法在**核心内部**（初值来源），属作者设计权，我们单方面改会与后续版本冲突。**产品侧的正确动作**：登记 + 在 UI 上对这两个模板的外混臂给出明确告警/禁用（比静默 STOP 好），并把"1.1 时代这两个模板外混臂数字不可信"写进文档 |
| **临时绕行** | 产品侧可先把这两个模板的 `nucl_model` 从 5 改回 1（但会丢失论文源，冷凝空转，见 Q-18）—— 两者都不可接受，故**建议等作者答复** |

### 附：Bug #7 method 6 四臂对照实验（2026-09-20 执行）

目的：回答"1.2 到底是**修好了** method 6，还是只是**绕过**了它"。方法：同一模板、只切 `redistribution_method`
与 `SCRAM_REDISTRIBUTION_MODE`，比较是否**逐位相同**。

用模板 `gmd_paris_full`（`nucl_model=1`，避开 #28 干扰），12 h：

| 臂 | INTERNAL_MIXING | EXTERNAL_MIXING |
|---|---|---|
| 默认内核 + `method=2` | ok，78 步，`32.5603969039` | ok，83 步，`32.6756421734` |
| 默认内核 + `method=6` | ok，78 步，**逐位相同** | ok，83 步，**逐位相同** |
| `SCRAM_REDISTRIBUTION_MODE=legacy` + `method=6` | **failed**，63 步 | **failed**，1 步 |
| `SCRAM_REDISTRIBUTION_MODE=legacy` + `method=2` | ok，78 步，`32.5587359327` | ok，83 步，`32.6821742749` |

**结论**：

1. **默认下 method 号被完全忽略** —— 2 与 6 结果逐位相同，因为 `conservative_remap12`（默认 `.true.`）
   把 `scheme>=2` 全部送进 `redistribution_size12()`，`euler_coupled.f90` 根本不被调用。
2. **缺陷本体仍在**：`legacy` 模式下 method 6 立刻 `failed`（62 步 / 1 步时日志反复出现
   `non conservation du nombre total !!`），而 method 2 同模式下 ok ⇒ 故障**确实只在 method 6 的
   `euler_coupled` 路径**上，与 1.2 的其他改动无关。
3. ⇒ 所以 `bug7_method6_v5.patch` 作废是**合理的**（那段代码已不在默认执行路径上），但**不是"已修"**。
   一旦有人设 `SCRAM_REDISTRIBUTION_MODE=legacy` + `method=6`，缺陷会原样复现。
4. 副作用提醒：默认模式下 2/3/4/5/6 等价 ⇒ **界面上的方法号下拉现在大部分取值是"死"的**
   （只有 1 有区别：跳过尺寸重分布）。这与 #12/#15/#20 属同一类"控件与实际口径脱节"，建议在 UI 上注明。

### 5. 数值基线全部作废并重算

1.2 改动凝结传质（Kn=6D/(vd) + 全区间 Fuchs–Sutugin）、湿密度、moving-center dual-pivot 重分布
⇒ 文档中所有 1.1 时代的数值基线**一概失效**。已重测：

| 案例 | 1.1 基线 | **1.2 实测** | 变化 |
|---|---|---|---|
| `gmd_paris_full` INT | `32.73376655624839` / `1.0260805990e10`，88 步 | `32.669498799` / `10019885058.9`，**110 步** | 质量 −0.20% |
| `gmd_paris_full` EXT | `33.751055266282556` / `1.1638880310e10`，540 步 | `32.8722503821` / `9897654593.9`，**743 步** | 质量 −2.60% |
| `gmd_paris_full` 初始总质量 | `21.583170063260344` | `21.583170063260344` | **不变** ✅（初值口径未变） |
| `tutorial_minimal`（coag_only） | INT `24.482042410429116` / `9.55750171385341e9` | INT `0.001479701` / `4103288416.59` | ⚠️ 见下 |
| 两个 hazy 模板 | 初始总质量 `226.07444159907240`/`228.81807486240999` | 同值 | **不变** ✅ |

> ⚠️ `tutorial_minimal` 的 1.1 基线（24.48）来自**手册口径的 baseline 基座**，与当前模板的
> `teaching` 基座不是同一初值，两者本就不可比 —— 记录时需注明口径，避免误判为回归。
> ⚠️ 上表 1.2 数值由临时运行器以 12 位有效数字打印；**完整精度的基线需要专用工具重采**，
> 而原基线工具 `scripts/linux/collect_metrics.py` 已在 2026-09-20 随排查工具链移除。

### 6. 绘图缺陷处置（按"当 bug 调试"口径，**不进标准测试**）

原 `docs/checktest/绘图核查_20260915.md` 的重查结论见 `docs/绘图正确性核查_20260915.md`（已恢复）。
本轮改动全部落在 `app/services/plot_service.py`：

| 编号 | 内容 | 处置 |
|---|---|---|
| §二 | 组成档号硬编码 `{1,3,6,11,20}` | ✅ 已修（`e404efa`）`_derive_unmixed_bins()` 按 t=0 数据反推 |
| §三 | 高位异常被图吞掉 | ✅ 已修：`_anomaly_counts()` + 标注 |
| P1 | 缺 CSV 的臂导致崩溃 | ✅ 已修：`_scheme_names()` |
| P2 | 参考臂目录名写死 | ✅ 已修：`_pick_reference_scheme()` |
| P3 | 终态堆叠柱无人对过 | ✅ **核对通过，非缺陷**（逐位 = `final_mass`） |
| P4 | 未显式 encoding | ✅ 已修 |
| P5 | 纵轴无单位 | ✅ 已修 |
| P6 | 参考臂恒零线无语义 | ✅ 已修（标注 `identically 0`） |
| **P7** | `np.interp` 跨臂插值 | ⚠️ **实测定性**：原"插值伪影"假设被否证（粗化到 300 s 摆幅只降一半：`1.33e-2`→`5.92e-3`）⇒ 是**真差异 + 步长采样**。已改为两臂插到公共网格 + 图上注明。**附带线索**：振荡止于 t=2788.7 s，紧挨 #17 的排放窗口 2643.76 s |
| P8 | wallclock 当性能指标 | ✅ 已修（标注 machine-dependent） |
| **P9** | 全零数据照常出图 | ✅ 已修：叠 `NO NON-ZERO DATA` 水印（已看图验证） |
| §五 | 把绘图判据写进标准测试 | ❌ **按人工决定取消**。绘图按缺陷修，`run_standard_tests.py` 不动 |

验证：`py_compile` 通过；两个案例各 10 张图；`run_standard_tests.py` 五项全 ok（`import_smoke` /
`gui_smoke` / `report_smoke` / `runtime_smoke` / `standard_tests`）。

> 注：原自动判据脚本 `scripts/linux/audit_plots.py` 已随排查工具链移除，旧文档里的"三层判据"
> **不再自动执行**；本表的核对是人工 + 看图完成的。

### 7. 本轮遗留待办

- [ ] **#28 需作者确认**（1.2 新增不变量 vs 我们初值的合法性问题）
- [ ] 请作者重生成 `ORIGINAL_SOURCE_SHA256.json` 与两份 receipt（现与树不一致）
- [ ] 完整数值基线重采（需先决定用什么工具替代已移除的 harness）
- [ ] Windows 侧：`ProgramSCRAM.exe` 仍是 2026-05-15 的 1.1 构建，**与 1.2 源码不一致**，
      需在 Windows 重编译（本机无 Fortran 工具链）
- [ ] `docs/` 中仍有大量 1.1 时代的基线数字（手册、报告、本表历史行），需一并标注"1.1 口径"

---

## 2026-09-21：nl=5 初始化口径专项审查（#28 因果链补齐 + 新登记 #29）

> 完整报告：**`docs/nl5与bug28审查_20260921.md`**（含逐格实测数据、复现命令、给作者的问题清单）。
> 本次审查**未修改任何代码**；只读核查 + 登记。

### 1. 内核状态复核：Windows 侧仍是 1.1 构建

| 二进制 | md5 | mtime | 结论 |
|---|---|---|---|
| `runtime/windows/ProgramSCRAM.exe` | `aeaf4a5e…` | 2026-09-10（目录重排时的搬动 mtime） | ❌ **1.1 构建**。字符串扫描：`SCRAM1.2` / `SCRAM_REDISTRIBUTION_MODE` / `moving_center_dualpivot` / `orphan mass` **全部 0 命中**；1.1 时代的 `COAG_TARGET_NEAREST` / `SCRAM_COEFF_REPARTITION_MODE` 命中 |
| `runtime/linux/ProgramSCRAM` | `a60700a9…` | **2026-09-20 16:14:40** | ✅ 与 1.2 源码一致 |
| `~/.local/state/scram_boxapp_mixing/runtime/linux/ProgramSCRAM`（本轮实测所用） | `a60700a9…` | 同上 | ✅ 用户态暂存副本，与上一行**逐字节相同** |

- 1.2 相对 1.1 多了 **3 个 `.f90`**（`ModuleCoagulationNearest12` / `ModuleConservativeRemap12` / `ModuleCondSurrIO`；SRC 文件数 **17 vs 14**）⇒ Windows exe 不重编译，用户侧连"1.2 新重分布内核"和"1.2 新体检"都用不到。**这已不只是 #18 的保真度问题**。
- Linux 核的来历（git）：`b3cf6f7`（2026-06-01 初版）**只有 Windows 运行时**；`45de542`（2026-09-10）提交信息为"新增 Linux 原生运行时：从源码构建核心并在 Linux 上运行模型"⇒ 由本移植方新增；`7cc59c7`、`0cbac3c` 各重建一次。改 Fortran 后必须重建（#9 的教训）。

### 2. #28 因果链补齐

**触发三件套（缺一不可）**：`nucl_model=5` **且** `tag_external=0` **且** `N_frac>1`。

对 nl=5，`init_bin_number` 全核**只有 `:675` 一处消费**，且它在块 `:669-679`（该块位于 `if/else nucl_model` **之外**——`:668` 才是那个 `endif`）。

**时序**：① `:131` `allocate`（**未清零**；紧邻的 `init_bin_emission` 有 `=0.d0`）→ ② `:145` 读取被 `if(nucl_model.ne.5)` 跳过（数组保持垃圾）→ ③ `:458` 算内置 Hazy（`mass_init`/`number_init`）→ ④ `:584-596` 块②写好初值（此时质量与粒子数都正确）→ ⑤ **`:675` 用 A（垃圾）覆盖第 1 列的粒子数** ← 缺陷诞生点 → ⑥ 组成重分布搬运 → ⑦ 首次尺寸重分布前体检 ⇒ `error stop`。

**"不守恒"的确切含义**：1.2 新内核（`MOVING_CENTER_DUALPIVOT`）**用两套权重同时守数量与质量**（`:3-4` "never reconstruct number from mass"、`:154-156` `V_lo/N_lo = pivot_volume(lo)`），孤儿格子让两个守恒量只能保一个 ⇒ 宁可提前拒绝。1.1 无此不变量 ⇒ 静默算错（"跑得通、数字不可信"的由来）。

**判据是成对看的**：`(0,0)` 空格子正常；`(>0,0)` 孤儿 → STOP；`(0,>0)` 幽灵 → STOP。所以"不允许 0"是误解，禁止的是**不配套**。

**`tag_external=1` 不是另一个缺陷**：它使块 `:669`、`:681` 都不执行 ⇒ A **从未被读** ⇒ 无后果。但属**潜在隐患**（未被清初始化的数组仍在），建议作者顺手清零或填 `number_init(k)`。同类隐患：`kind_composition=2–9` 时 `frac_bound` 已 allocate 未赋值（#24 附注）。

### 3. 【新登记 #29】nl=5 多列分支重复投放（外混臂初值虚高 6×/18×）

见上方 Bug 总览第 29 行。要点：

- **位置** `SRC/ModuleDiscretization.f90:584-596`（nl=5 的 `else !external mixing`）。
- **机制** 两条判定不对称：硫酸盐用"第 1 族**上限**=1"（唯一命中 1 列）；黑碳用"第 1 族**下限**=0"（命中 **11 列**；`n_frac=5` 时 **35 列**）⇒ 同一份 `mass_init(k)/2` 写 12/36 份，随后被"组成相同即累加"的组成重分布合并成 1 格（值放大 11/35 倍）。
- **推断**：作者本意应是"每档两列：纯硫酸盐 + 纯黑碳"（`N_frac=1` 时退化为内混），黑碳那条判定偷懒写成"第 1 族下限=0"。
- **与 #28 的关系**：同一段代码里的**两个独立缺陷**——加模式分岔只修 #28（STOP 消失），**质量与总量一分不变**。
- **实测**（`gmd_hazy_condensation`，nl=5，12 h）：初值 SO4 两臂相同 `18.8395368`；BC `18.8395368` vs `207.2349048`（**11.00×**）；总量 `37.679073599845388` vs `226.07444159907240`（**6.0000×**）；终态粒子数比 **6.0000**（模板未开凝并 ⇒ 差异全部来自初值）；`Mass Cond` 3.1231764329 vs 1.1228773009（**此差异不可解释为"内混 vs 外混"**）。

### 4. 两个"历史基线"数字作废

| 记录值 | 今天的解释 |
|---|---|
| `226.07444159907240` | = `12 × Σ mass_init/2`（纯重复投放产物；`tag_external=1` 臂实测） |
| `228.81807486240999` | = `226.07444159907240 − 18.839536799922694（被块④覆盖掉的 1 份） + 21.583170063260344（cfg 的 30 物种总量）`，与记录值相对差 3.5e-16（`tag_external=0` 臂实测） |

⇒ 二者**都不是 hazy 场景的物理初值**，不得再作基线引用；手册/报告/本表历史行需标注或重算。

### 5. 连带发现（新增/更正）

- **nl=5 与物种布局强耦合**：初值/排放钉死在编译期槽位 `EBC=2 / ESO4=4`（`INC/pointer.inc`）⇒ 只在含槽位 4 的 30 物种布局下成立。2 物种布局实测：`exit=0`、**不报错**，但初始总质量只剩一半、**`Mass Cond = 0`**（与 Q-18 同源）。
- **nl=5 初值幅值也随物种表变**：`fixed_density` 由物种表 `per_mass_init` 加权算出 ⇒ 同一 hazy 场景在 2 物种布局为 57.537、30 物种布局为 37.679。
- **`SCRAM_REDISTRIBUTION_MODE` 全 app 从不设置** ⇒ 产品路径永远走 1.2 新内核；`redistribution_method` 在默认下 **2–9 逐位相同**（GUI 0–9 大多为死值，与 #12/#15/#20/#24 同批）。
- **`RESULT/result_inter.bin` 的 `inti` = internal（内部混合）而非 initial**；由 `ModuleResultoutput.f90:125-129` 写出（`j, jesp, concentration_inti`，行数 = `N_size × N_inside_aer(=21)`），产品侧不读它。
- **【更正】** 撤回"内混臂 `mass_init(j)` 越界读"的说法：`N_frac=1 ⇒ N_fracmax=1 ⇒ N_size=N_sizebin=7`，**不越界**（`:650` 注释同此）。实测佐证：内混臂 `inital total mass = 37.679073599845388` 与独立复算逐位一致，`result_mass.bin` 只有 217 行 = 7×31。
- **nl=5 初值独立验证通过**：按 `dist_init_mass_number` 公式独立复算（100 点/档积分），7 档 `mass_init`/`number_init` 与内核相对差 ~1e-10（打印精度量级）；总量 37.6790735998454（质量）/ 6.140334422e9（数量，= 6140 个/cm³）；平均直径 ≈ 0.215 µm；质量小于全积分 47.73 是因为粒径档只到 10 µm（粗模态尾巴被截断）。

### 6. 给作者的问题清单（待回函）

1. **nl=5 是否只支持 `n_frac=1`？** 若是 ⇒ `n_frac>1` 应显式报错；若否 ⇒ 请给出"多列时两种物质摆哪几列"的约定。
2. **`:592` 为何用"第 1 族下限=0"而非"第 4 族（BC）上限=1"？**（前者命中 11/35 列，后者唯一命中）
3. **`:669-679` 缺模式分岔**：请选 a) 该块对 nl=5 跳过；b) 按模式取 `number_init(k)`。
4. **能否给 nl=5 下不用的 `init_bin_number` 显式清零？**（同类：`frac_bound`）
5. **两处耦合提醒**：初值幅值经 `fixed_density` 依赖物种表；初值/排放钉死槽位 2/4。

### 7. 本轮遗留待办（2026-09-21 更新）

- [ ] 与作者讨论上述 5 问（尤其"nl=5 是否支持多列"）
- [ ] 产品侧：两个 hazy 模板**外混臂拦截/告警** + 相关数字**作废标注**
- [x] 本次证据已转存 `install_logs/nl5_20260921/`（188 KB / 15 个文件）；`/tmp` 下的临时产物已清理（2026-09-21）
- [ ] 读上游发布包 `cesm-scram-optics-20260915-r2`（作者 `/data/users/wangfangyuan/model/` 下有正式副本）中的 `source/scram/doc/OPTICS_INTEGRATION_HANDOFF_20260915.md` 与 `test_scram_orphan_population.py`：CESM 侧已有 `SCRAM_ORPHAN_MASS_CLEAN` 语义（孤儿质量清理而非报错），可能直接回答"nl=5 外混怎么处置孤儿格子"
- [ ] 沿用上轮遗留：Windows 核重编译、1.2 基线重采、`docs/` 中 1.1 口径数字标注

---

## 一页看懂（说人话）

> 给不熟悉内部术语的读者。逐条的精确证据、判据与代码位置见下方「修复状态」与「详细信息」两节。
> 一句话总览：**该修的都修完了；剩下的是"在 Windows 上重做几件事"和"你要拿的几个主意"。**

### A. 已经修好，不用再管

| # | 一句话 |
|---|--------|
| 3 | 选了案例预设后，模拟时长没写进配置文件，实际跑的是模板原时长 → 已修 |
| 4 | 初始质量为零时密度算成 NaN → 已修 |
| 6 | 界面点"运行"不生成结果图 → 已修 |
| 8 | 核心内部崩了却报告"成功" → 已修 |
| 11 | 界面里改过程开关/时长被案例预设静默忽略 → 已修 |
| 14 | 换重分配方法 3/5 时粒子数暴涨 → 查明是方法定义使然，不是缺陷（产品默认用方法 2） |
| 1 | 零质量模板初始质量为 0 → 现在的模板基座都换成非零初值，该路径在应用内已不可达，转为自动检查 |
| 9 | 选了「论文验证专用」成核模式（`nucl_model=5`）后运行会崩 → **原因在软件这边不在核心**：配置文件多写了内核按约定不收的 3 行，核心读串行了。已改成"这个模式下就不写这 3 行" ⇒ 修好了，**Windows 版不用重编译** |
| 绘图核查 8 项 | 组成档号写死 / 参考臂目录名写死 / 缺 encoding / 纵轴缺单位 / 参考臂恒零线无语义 / 缺 CSV 的臂导致崩溃 / 全零数据照常出图 / 高位异常被图吞掉 → **全修**。另 1 项（终态堆叠柱自行聚合）核对后**确认无缺陷**（逐位等于 `final_mass`）。详见 `docs/绘图正确性核查_20260915.md` |

### B. 要在 Windows 上做的（机械动作，不需要你判断）

| # | 一句话 | 怎么做 |
|---|--------|--------|
| 10 | 三个目录共 26 张界面截图，文字全是方框 | **根因已修（2026-09-14）**：不是缺字体，是脚本强制 `offscreen` 平台导致 Qt 字体库为空 → 已改为平台自适应 + 字体回退。剩下只需跑 `python scripts/capture_screenshots.py` 重生成发布资产 |
| 18 | 移植前后的数值差越过了合格线（十万分之一点四） | 在 Windows 重编译核心后重测 |

### C. 要你拿主意的（多数不用写代码）

| # | 一句话 | 选项 |
|---|--------|------|
| 12 | 界面"RDB 核心模式"下拉框选了没用（死控件） | A 接上核心 / B 删掉控件 |
| 15 | 配置里的 `mapping_scheme` 也是死配置（与 #12 同类） | A 接上 / B 移除（与 #12 同批处理） |
| 16 | 界面"环境状态"选了没用（被另一个界面上没有的开关挡住） | a 联动（**已证可行**，推荐）/ b 暴露那个开关 / c 删掉下拉 |
| 17 | 排放只在前 44 分钟发生，与模拟时长无关 | a 置 0 与本体一致 / b 做成可配 |
| 18 | 保真度的合格线定在哪 | a 统一编译参数、守住 1e-5 / b 放宽并记录依据 / c 改判据（**推荐**） |
| 24 | 方法号取值范围过宽：`dynamic_solver` 填 3–9 会让核心**死循环挂住**（实测，只能强杀） | a 把方法号改成只列有效值的下拉（**推荐**）/ b 保留数字框但加前置校验拦截 |
| 20 | 界面"热力学标记"（`tag_thrm`）是死标签：核心读了就扔 | A 接上核心 / B 移除控件（与 #12/#15 同批） |
| 25 | 界面"最小时间步"（`dtmin`）也是死标签：核心读了就扔，且注释里承诺的步长上下限从未实现 | a 移除控件（**推荐**，它本来就没生效）/ b 在核心补上 DTMIN/DTMAX 钳制（需改核心 + 重编译，属新功能） |
| 21 | 界面"组分离散模式"（`kind_composition`）选什么都没用：运行前被强制归零 | a 允许用户选 / b 移除控件 |
| 22 | 归档的 `experiment_config.cfg` 和真正拿去跑的配置不是同一份 | a 归档改用变换后的数据（**推荐**）/ b 归档时附差异说明 |
| 23 | 上传内混配置后界面恒按外混跑，且解释文字因键名拼错根本看不到 | a 从 cfg 反推内混/外混 / b 放开手选 / c 维持现状（至少修 i18n 键名） |
| 13 | 零质量时内混/外混的粒子数差 4 个数量级 | 需物理判断：设计使然 or 缺陷 |
| 2 / 5 | 零质量时两套凝并路径行为不一致（本体自带的老毛病） | 是否要修（要动核心 → 先出提案） |
| 7 | 本体自带的"数量不守恒"老毛病 | 产品侧已绕开（模板默认改回方法 2）；要不要给本体打补丁由你定 |
| 28 | **1.2 新增的检查**让"论文验证专用"成核模式（`nucl_model=5`）的**外混臂直接硬停**。根因不在 1.2：该模式下内核消费了一个**从未被读入**的数组（读的是未初始化内存）——1.1 一直在静默使用垃圾值，1.2 只是把它变成显式报错。**含义：1.1 时代这两个 hazy 模板外混臂的数字不可信** | a 请作者在核心侧改用 `number_init(k)`（推荐，改动最小）/ b 请作者把 nl=5 的 cfg 契约改成"必须带数浓度行" / c 产品侧先给这两个模板的外混臂加告警或禁用（不动内核，**可在等作者答复期间先做**） |

---

## 修复状态

| # | 严重性 | 类别 | 状态 | 验证结果 |
|---|--------|------|------|---------|
| 1 | 🔴 P0 | 初始化 | 🔄 已转自动复核（agent 权衡，2026-09-11） | 原 ❌ 未修复。2026-09-11 复核：触发条件（`base="default"` 的零质量骨架）**在应用里已不可达**——`c9b6310`（2026-07-27）把 `tutorial_minimal`/`gmd_hazy_condensation`/`gmd_hazy_coag_cond` 三个模板的基座从 `default` 改为 `teaching`（examples 配置，非零初值），实测 `tutorial_minimal` 终态质量 0.00148 = 手册基准，不再是 0。已备**夹具对** `docs/checktest/zero_initial_mass_{test,fixed}.cfg`（同结构，仅第 1 个物质第 1 个 bin 初值不同）与**自动判据**（`collect_metrics.py`：status=ok 且质量为 0 → 报警）。待 agent 按 hunt_plan Q-13 权衡"是否仍需修改/如何改"，并回答当年切基座时留下的疑点（Q-14：teaching 物种是否适合 GMD 冷凝验证） |
| 2 | 🔴 P2 | 凝并 | ✅ **现象已复现**（2026-09-14，用核心自打的过程计数直接证明） | **2026-09-14 实测**（零质量夹具，INTERNAL 臂，1h）：`with_coag=1` → 日志 `Nub Coag=0.0`、`Mass Cond=0.0`、2 步；`with_coag=0` → 同样 `Nub Coag=0.0`、2 步。**开着凝并时凝并计数为 0 = 一次都没发生**。**对照（非零质量 `gmd_paris_full`，同样 1h）**：`with_coag=1` → `Nub Coag=-1.1069e14`、59 步、`Mass Cond=8.115`；`with_coag=0` → `Nub Coag=0.0`、42 步 ⇒ **仪器有效**（开关能被测出差异），故零质量时的"无差异"是真实现象而非测量失效。**附带发现**：零质量时 `Mass Cond` 也为 0 ⇒ 冷凝同样空转（与 Q-18 同类）。**性质仍待人工判**：零质量本身是否合法输入 |
| 3 | 🟡 P0 | 运行 | ✅ 已修复 | `Simulation Time 1800s`（原 43200s） |
| 4 | 🟡 P1 | 初始化 | ✅ 已修复 | `Fixed Density 1.8E-6`（原 NaN） |
| 5 | 🟢 P2 | 凝并 | ⚠️ **描述待更正**（2026-09-14 复现，症状与原文不符） | 原文称「Legacy 仅检查 `c_number>0` ⇒ 会算凝并速率；Prototype 额外检查 mass ⇒ 跳过」。**2026-09-14 实测（Windows 核，零质量夹具 `zero_initial_mass_test.cfg`）**：`COAG_TARGET_NEAREST` → `status=ok`、2 步、`Nub Coag=0.0`；**`LEGACY` → `status=failed`、0 步、`Program received signal SIGSEGV`（段错误）**。两模式行为确实不同（#5 的"不一致"现象成立），但**不是"一个算一个不算"，而是"一个静默不动、一个直接段错误"**；LEGACY 在 0 步即崩，无从比较速率 ⇒ 原文的机理论述**未经复现证实**，需重新定位。证据 `install_logs/verify_bugs*/`、`install_logs/verify_bugs_r3/result.json`。**2026-09-14 追加四臂实测**：零质量 + `LEGACY` → failed/0 步/段错误；零质量 + `COAG_TARGET_NEAREST` → ok/2 步/凝并计数 0；**非零质量 + `LEGACY` → ok/92 步**；非零质量 + `COAG_TARGET_NEAREST` → ok/82 步 ⇒ **零质量是 LEGACY 崩溃的必要条件**；在非零质量下两条路径都能跑完但步数不同（92 vs 82），说明两路径行为确有差异。证据 `install_logs/verify_q5_q13b/` |
| 6 | 🟡 P1 | 绘图 | ✅ 已修复 | `generate_all()` 不再传错参 |
| 7 | 🔴 P2 | 重分配 | 🟡 上游缺陷；**产品侧已消除**（模板默认值改回 method=2）；v4 补丁待人工决定是否给本体打 | 根因（2026-09-12 复核定位）：`euler_coupled.f90:378-400` 把 hand-out 累加器**重复交付**（累加器按 `kloc(k)` 索引、交付循环按源 bin 迭代；本相位 `kloc≡1` ⇒ 交出量被加回两次 → 数量净增 0.054% → 第 423 行 STOP）；另有 `euler_coupled.f90:244` 的 `RQ(k)/Q(k)`（空 bin）与 `ModuleThermodynamics.f90:264` 的 `log10(0)`（teaching 基座无 IH）两处无保护除法。**该文件与本体 `/home/yifeihu/SCRAM1.1` 逐字节一致 ⇒ 属上游缺陷，非移植引入**；实测本体 exe + method=6（仅改 cfg 第 7 行）同样报 `non conservation`，相对误差 9.6e-3。v1/v2/v3 guard 无效的原因：guard 条件在本相位恒假（要求 `kloc(k)>1`），"与 stock 逐位相同"是必然。**处置**：① 产品侧把 `gmd_hazy_coag_cond` 模板默认 `redistribution_method` 6→2（与本体/论文口径一致）→ 模板从 failed 变 ok（`install_logs/auto/template_audit/`）；② 若要保留 method=6 演示，则给本体打 `proposals/bug7_double_add_v4.patch`（已验证 failed→ok、精确守恒，按守卫 §1 属 Windows/人工侧动作）；③ 残留 Q-17（边界 hand-out 丢弃 9.8e-6）随补丁一起考虑 |
| 8 | 🟡 P1 | 运行 | ✅ 已修复 | gmd_hazy 正确检测为 `failed`（原误报 `ok`） |
| 9 | 🔴 P1 | 初始化 | ✅ **已修复**（2026-09-20 更正方向：改 py 侧，内核保持本体原样） | **归因更正**：原记为内核「跳过却不消费」缺陷，实为**移植契约缺陷** —— 内核在 `nucl_model=5` 时**按设计跳过**那 3 行（该模式是自成一体的硬编码验证分支，这两个数组读了也不用；本体 `/home/yifeihu/SCRAM1.1/SRC/ModuleDiscretization.f90` 的读取语句序列与仓库原内核一致），而 Python 写入器 `config_model.py` 自初始提交 `b3cf6f7` 起**无条件写出**这 3 行 ⇒ 文件指针错位。**修复**：`7cc59c7` 对内核的改动**已回退**（恢复 `if(nucl_model.ne.5)`），改为 py 侧按 `nucl_model` 条件化写出/读入（`_has_emission_block`）。**实测**：① 原始内核 + 53 行夹具 → 退出码 0、初始总质量 `226.07444159907240`，与 2026-07-27 记录**逐位一致**；② 原始内核 + 56 行夹具 → `Bad integer for item 1 in list input` 崩溃（负例仍有效）；③ py 生成的 cfg 现为 53 行，跑原始内核退出码 0；④ `probe_cell --cfg docs/checktest/nucl_model5_fixed.cfg` 双臂 `status=ok`；⑤ 5 个 `nucl_model≠5` 模板输出**逐字节未变**（零回归）。新增守卫 `scripts/linux/check_cfg_contract.py`（修复前 4/16 项红灯、修复后 16/16 全绿）。**⇒ Windows 发行核（2026-05-15 构建）无需重编译即可生效**，原「必须重编译」的前提随之作废 |
| 10 | 🟡 P1 | 文档资产 | 🟡 **根因已定位并修复脚本；资产待重生成**（2026-09-14 更新） | **根因不是缺字体，而是脚本强制了 `offscreen` 平台**：`scripts/capture_screenshots.py:11` 写 `os.environ.setdefault("QT_QPA_PLATFORM","offscreen")`，而 **Qt 的 offscreen 插件在 Windows 上返回空的字体库**（实测 `QFontDatabase.families()` = **0 个家族**；改用真实 `windows` 平台 = **140 个家族**，含脚本想要的 `Microsoft YaHei UI`）⇒ 所有字形退化为 □。**这意味着按原文"在有字体的 Windows 上重生成"永远修不好** —— 任何 Windows 机器上跑都会是方框。**已修脚本**（平台自适应 + 字体文件回退 + 拿不到 CJK 字体则显式报错退出），本机实测：`main_zh` 密度 **0.0115 → 0.0470**、`main_en` 0.0114 → 0.0368、`help_panel` 0.0066 → 0.0517，目视文字全部可读。**剩余**：三处发布资产（9+9+8 张）仍需重生成；自检对稀疏面板（`running_state`/`report_panel`/`settings_panel`/`results_view`）会误报 LOW 密度（已目视确认文字正常） |
| 11 | 🟠 P1 | 运行 | ✅ 已修复（2026-09-11） | 预设改为"建议值"：显式设置优先——`run_service.prepare_run/_with_case_preset` 接受 `explicit_keys`（须在 normalize 之前取出，normalize 只保留固定键）；GUI `_collect_data` 把"与当前预设建议值不同"的键标为显式；`probe_cell --set` 的键自动标记。验证：① `noop_probe.py --template tutorial_minimal` 关掉凝并后终态数量变化 5.3e-3（此前报"覆写未生效"）；② 完整标准测试数值**逐位**与基线一致（EXT 33.7511 / INT 32.7338，540/88 步，五项 smoke 全过）→ 行为保持 |
| 12 | 🟠 P1 | 运行/配置 | ❌ 未修复（2026-09-12 新发现） | GUI 的 `redistribution_option`（RDB 核心模式 legacy/core_conserv/core_nogrow/core_smallgrow）是**死控件**：app 仅经环境变量 `SCRAM_RDB_CORE_CONSERV`/`SCRAM_RDB_CORE_CONSERV_NAME` 传递（run_service.py:122-123），但编译的 Fortran（ModuleCoeffRepartitionBoxmodel.f90）只读 `SCRAM_COEFF_REPARTITION_MODE`（=映射方案，另一控件），对 RDB 核心模式**无任何变量/环境读取**，生成的 .cfg 也无此字段 → 选项永不生效。实测 gmd_paris_full（凝并开、540 步）四值终态**逐位相同**（EXT mass=33.751055266282556 / INT mass=32.73376655624839）。连带使 `docs/checktest/hazy_nogrow_{test,fixed}.cfg` 的 test/fixed 区分失效（二者 Fortran 可读字段逐字节相同）。已备夹具对 `redistribution_option_dead_{test,fixed}.cfg` 与 patch 提案 `proposals/bug12_rdb_core_mode_dead.patch` |
| 13 | 🟠 P1 | 初始化/混合假设 | ❌ 性质待判（2026-09-12 复核发现） | 零质量/微质量配置下 **EXT/INT 终态粒子数差 4 个数量级**：`docs/checktest/zero_initial_mass_test.cfg` → EXT `final_number=0.0` 而 INT `4.12452e9`；`tiny_initial_mass` → EXT `4.99998e5` 而 INT `4.12452e9`。证据：`install_logs/auto/probes/q07_zero_mass_test/`、`q07_tiny_mass/probe.json`（2026-09-12 10:11 轮）。同一物理设置两侧不应差 4 个数量级 → 建议按 `_test/_fixed` 夹具登记后定性 |
| 14 | 🟡 P2 | 重分配 | ✅ 已判：设计使然（上游固有，2026-09-13 源码+数值分类，Q-19 关闭） | `redistribution_method=3/5` 下**粒子数暴增**：`gmd_paris_condensation + method=3` → EXT `5.28349e12`/INT `6.15417e12`，method=2 为 `3.44565e10`（**×153**）；method=5 → `1.07e11`（×3）；质量基本不变。同现象在 `fuzz_q11/fuzz_report.json` 里已存在（idx 9 达 ×383）却被判 clean——因为判据只查质量残差。euler_mass/hemen 本非数量守恒，故属"设计使然 vs 缺陷"待人工判定，但必须先入台账 |
| 15 | 🟡 P2 | 运行/配置 | ❌ 未修（2026-09-12 复核发现，与 #12 同类） | 配置标量 `mapping_scheme`（`LEGACY`/`DETERMINISTIC_NEAREST`，模板与校验器都在用）**从不进入核心**：`run_service._coag_mapping_mode(scheme)` 收到的是**混合假设**（`INTERNAL_MIXING`/`EXTERNAL_MIXING`，见 `run_comparison` 的 `MIXING_ASSUMPTIONS` 循环），两者都不等于 `LEGACY` ⇒ 送给核心的 `SCRAM_COEFF_REPARTITION_MODE` **恒为 `COAG_TARGET_NEAREST`**。实测：手工把该 env 设为 `LEGACY` 跑 Mégapole/12h，终态与 `COAG_TARGET_NEAREST` **完全相同** ⇒ 该开关在当前配置下也观察不到影响。`run.log` 里记录的 `mapping_mode` 因此是固定值。GUI 的"mapping_scheme"下拉实际绑定的是混合假设（`main_window.py:214-218`），与这个标量不是一回事。**2026-09-12 22:15 轮夹具固化（Q-21）**：`probe_cell gmd_paris_condensation` 默认 vs `--set mapping_scheme=LEGACY` 两臂终态逐位相同（EXT mass=33.0654/INT mass=32.6176/number=3.44653e10/steps=42），两臂 `run.log` `mapping_mode` 均=`COAG_TARGET_NEAREST`、生成 cfg 无 mapping 字段 ⇒ 死配置确认；证据 `install_logs/auto/probes/q21_{default,legacy}/`，台账 `Q-21 · mapping_scheme_env · app_to_core · contract` → bug |
| 16 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-12 复核发现，port；2026-09-13 Q-24 已定位根因，处置待人工） | GUI「环境状态」(init_scenario: 1 霾天/2 城市/3 清洁) **在出厂配置下无任何数值效果**：初值是否采用内置三套场景分布由 `tag_init`（初始化模式）决定，而所有基座 cfg 都是 `30 1`/`2 1`（=1，用配置里的逐档质量），且 `tag_init` 在 GUI 未暴露（用户改不了）。实测：`gmd_paris_full` 下 init_scenario=1/2/3 的 t=0 质量 21.583170063260344、数量 1.4625e10 **逐位相同**。**2026-09-13 Q-24 定位**：tag_init=0 臂三场景对照（gmd_paris_full,0.5h）status=ok 无 NaN/Inf、residual~1e-18，初值质量 2.560/2.581/2.587e-11（即本条注的 2.5e-11，是初值气溶胶质量，场景对数正态初值本应可忽略，非缺陷），终态质量 EXT 11.1139/11.1076/11.1028（来自冷凝 Mass Cond~11.09）三场景不同 ⇒ tag_init=0 路径数值可用、三场景确实产生差异 ⇒ 控件非设计性死，仅被未暴露的 tag_init 门控。历史依据：控件由 `321fca2`（2026-07-22）加入，对应 ModuleDiscretization.f90 三种三模态对数正态分布；`05d609c` 曾判定"tag_init=0 方案不可行"（Q-24 已证伪：路径可用）。处置（待人工，属"增删控件"类）：a) 场景与 tag_init 联动（**Q-24 已证可行**）；b) 暴露 tag_init 并标注条件；c) 移除下拉 |
| 17 | 🟡 P2 | 运行/配置 | ❌ 未修（2026-09-12 复核发现，upstream） | **普通模式排放窗口只有 2.64376e3 s（≈44.06 min）**，与模拟时长无关：`ModuleDiscretization.f90:1194-1205` 在 `nucl_model=5` 时 `time_emis=43200 s`，否则 `2.64376e3 s`；超出后 `emis_dt=0` ⇒ 停止排放。另两处同常数（:1274/:1287）只是"排放引起的步长限制"守卫，**不关闭凝并/冷凝**。代码无注释、全仓与本体无其它引用 ⇒ 判为作者为某场景调死的经验值。影响：本体论文 cfg（`INIT/cfg_megapole_01072009.cfg`）emission 全 0 ⇒ 其结论不受影响；仓库 baseline 基座 SO4 emission=1.72e-5 ⇒ 12h 只有前 44 分钟在排放。处置（待人工）：a) 与本体口径一致把 emission 置 0；b) 新增"排放时长可配"（新功能）。**2026-09-13 05:xx 轮数值确认（Q-23）**：`gmd_paris_emission_only` 全关过程 12h vs 0.5h 两臂，排放 delta 比值=0.6808484885=1800/2643.76 逐位精确 ⇒ 窗口 2643.76 s 确认、排放窗口内线性；upstream 固有，非移植缺陷，不计入 gate。证据 `install_logs/auto/probes/q23_emis_window_{12h,05h,30min}/`|
| 18 | 🟠 P1 | 保真度/gate | ❌ gate 未达标（2026-09-13 Q-26 新发现，port 标签，计入 gate） | **移植保真度 gate 实际未达标**：同一本体规范 cfg（`~/SCRAM1.1/INIT/cfg_megapole_01072009.cfg`，coef_s5_f3_b7.nc，12h）跑本体 exe（sha256 `71473328`）与仓库 exe（sha256 `f03b90aa`，stock）：总质量**逐位一致** `36.48929720841787`（bit-identical，达标）；但气溶胶质量 `24.22834256300118` vs `24.22867515785633`，**相对差 `1.373e-05` > gate 阈值 `1e-5` ⇒ gate_pass=False**（未达标）。气相 `2.713e-05`、Mass Cond `1.258e-04`、total_water `4.320e-05`。**新发现**：手工轮（runbook P4 / 台账 `fidelity · upstream_vs_devkit · megapole12h`）把 `1.4e-5` 记为 clean，但按 release gate 阈值（气溶胶质量差 ≤1e-5）实际未达标——差异源于 `-g` vs `-O2` 编译标志（非代码改动），属"阈值/口径"问题而非移植缺陷。**处置（待人工，不得自行放宽阈值）**：a) 维持 1e-5 并给本体/仓库统一编译标志（重编译对齐）；b) 调整阈值并记录依据；c) 以"总质量逐位一致"为硬判据、气溶胶差为软信号（改 gate 定义）。已脚本化 `scripts/linux/fidelity_check.py`（建议挂 deep 轮）。证据 `install_logs/auto/fidelity_check/20260913-082220/` + `install_logs/auto/fidelity_q26/`；台账 `Q-26 · fidelity_gate · upstream_vs_repo · contract` → bug |
| 19 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-14 新发现） | **#11 的修复在 GUI 路径上失效**：`_collect_data()` 结尾 `return self.config_model.normalize(data)`，而 `normalize()` 构建的新字典**不含 `explicit_keys`**（`config_model.py:180-195`）⇒ `prepare_run` 收到空集 ⇒ `_with_case_preset` 无条件套预设。实测（模板 `gmd_paris_full`，模拟"界面关掉凝并 + 时长改 1h"）：探针路径 `with_coag=0 / final_time_hours=1.0`（保住），**GUI 路径 `with_coag=1 / final_time_hours=12.0`（被覆盖）**。当初 #11 的验证用的是 `noop_probe.py`（探针路径显式传 `explicit_keys`），故未照到 GUI |
| 20 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-14 新发现，与 #12/#15 同类） | GUI「热力学标记」`tag_thrm` 是**死标签**：`grep -rni "tag_thrm" SRC INC` **仅 1 处命中**（`SRC/ModuleDiscretization.f90:89` 的 `read(10,*)dynamic_solver,tag_thrm`），核心读入后**从未使用**。对照词频：`tagrho` 3 / `tag_external` 6 / `Tag_init` 8。GUI 上 `main_window.py:349` 提供 0–9 数字框 ⇒ 改任何值结果逐位相同 |
| 21 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-14 新发现） | GUI「组分离散模式」`kind_composition` 在运行路径**被强制归零**：`run_service._with_mixing_assumption` 的 INTERNAL/EXTERNAL **两个分支都赋值 `= 0`**（`run_service.py:338,345`），而 cfg 序列化发生在其后（`prepare_run:107-108`）⇒ 用户选的 1 永远进不了实跑的 cfg。附带：归档 cfg 反而保留了用户值（见 #22），造成两份配置不一致 |
| 22 | 🟠 P1 | 运行/可复现性 | ❌ 未修（2026-09-14 新发现） | **归档的 `experiment_config.cfg` ≠ 实际执行的配置**：`_start_runs` 先用 `self.data` 序列化归档（`main_window.py:1101-1102`），再调 `prepare_run` 生成实跑 cfg；而 `prepare_run` 内部会先跑 `_with_mixing_assumption`（改 `n_frac`/`fraction_bounds`/`tag_external`/`kind_composition`）与 `_with_case_preset`（改过程开关/时长）**再**序列化 ⇒ 二者在任一变换生效时不同。影响：教学/报告场景下用户照归档文件重跑会得到不同结果 |
| 23 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-14 复核；设计意图存在但实现缺失） | **载入任何 cfg 后"混合假设"恒为 `EXTERNAL_MIXING`**：`config_model.parse()` 第 63 行写死该值，cfg 中**根本不存在此字段** ⇒ `_load_data_into_widgets` 再把它当"锁定值"（`main_window.py:647`）⇒ 上传内部混合配置也只能按外混跑。i18n 提示语声称"混合假设由载入的配置文件决定，不可手动修改"，但**没有任何代码从文件反推**（未用 `n_frac==1` 等判据）。**附带**：该提示语键名写错——代码用 `mixing_scheme_readonly_tip`，两个语言文件里只有 `mapping_scheme_readonly_tip`（同一提交 `3455826` 引入）⇒ 用户连解释都看不到 |
| 24 | 🔴 P1 | 运行/健壮性 | ✅ **已实测确认**（2026-09-14） | **方法号越界导致核心死循环挂住**：`ModuleAdaptstep.f90:86-100` 的 solver 分发只判 0/1/2，**无 `else` 分支**；而唯一推进子步时钟的 `current_sub_time = current_sub_time + sub_timestep_splitting` **只存在于三个求解器内部**（`:415`/`:482`/`:634`）⇒ 越界值时时钟不前进，外层 `do while (current_sub_time .lt. final_sub_time)` 永不退出。**实测**：同模板同时长（0.01h），`dynamic_solver=2` → 0.26s 跑完、日志 5 条 `Progress`；`dynamic_solver=5` → **60s 被强杀（exit 124）、日志停在 `Calculation in progress...`、0 条 `Progress`**。GUI 数字框给的是 0–9 ⇒ 用户可直接踩中。**同类越界语义**：`redistribution_method` 7–9 命中 `CASE DEFAULT` 只打印提示、**静默不重分配**；`kind_composition` 2–9 两个分支都不进 ⇒ **`frac_bound` 已 `allocate` 却未初始化**（读未初始化内存） |
| 25 | 🟠 P1 | 运行/配置 | ❌ 未修（2026-09-14 新发现，与 #12/#15/#20 同类） | GUI「最小时间步 (秒)」`dtmin` 是**死标签**：全核心 3 处命中 —— `ModuleAdaptstep.f90:293` 的**注释**、`ModuleDiscretization.f90:101` 的**读取**、`ModuleInitialization.f90:105` 的**声明**，**0 处使用**。注释称 DTMIN/DTMAX「defined in time.inc」，但 **`time.inc` 在本仓库不存在**、也没有任何 `INCLUDE 'time.inc'` 语句；`adaptime` 计算新步长处（`T_dt = T_dt*DSQRT(EPSER/n2err)`，`:300`）**没有任何上下限钳制** ⇒ 注释里承诺的「keep new time step between DTMIN and DTMAX」从未实现。**含义**：界面上的「最小时间步」改任何值都不影响结果，且自适应步长实际没有下限保护。**发现方式**：由新增的 `scripts/check_field_registry.py`（字段登记表对账）自动报出 —— 该脚本对每个字段核对「核心是否读 / 读后是否用」，排除了声明行、注释行与读取语句本身 |
| 26 | 🟠 P1 | 运行/对比功能 | ❌ 未修（2026-09-14 新发现） | **界面「比较 internal / external」在两臂上同时改了「表示能力」和「初始态」**：`_with_mixing_assumption` 的 INTERNAL 分支把 `tag_external` 强制为 0（`run_service.py:336`），而 EXTERNAL 分支**保留原值**（`:349`）。实测同一份配置做两臂变换：**出厂模板**（`tag_external=0`）→ 两臂只差 `n_frac`(1↔3) 与 `fraction_bounds`，对比干净；**用户载入的配置**（如 `zero_initial_mass_test.cfg`，`tag_external=1`）→ 两臂差 **3 项**：`n_frac`(1↔3)、**`tag_external`(0↔1)**、`fraction_bounds`。⇒ 后者的结果差异**不能只归因于内混/外混表示能力**，初始态也变了。附带：用户在结构编辑页设的 `n_frac` 与 fraction 表在两臂中都被静默改写（与 #23 同类）；比较运行只归档一份 `experiment_config.cfg`，而两臂各跑一份不同的 cfg（#22 的对比场景特例）。**2026-09-14 补充（自我更正）**：实测 `tag_init` **两臂始终相同**（按钮从不碰它）；且「内混臂强制 `tag_external=0`」**很可能不可避免** —— `n_frac=1` 时组成只有 1 段，「初始外混」在语义上无处安放；核心也正是这样用的（`ModuleDiscretization.f90:656` 专门处理 `tag_external=0 .and. N_frac.gt.1` 这一组合）⇒ **「是否算缺陷」需重新定性**，真正站得住的问题也许只是「界面没告诉用户两臂差异里包含初始态」 |
| 27 | 🟠 P1 | 运行/健壮性 | ❌ 未修（2026-09-14 新发现） | **案例名含非 ASCII 字符时，结果 CSV 的编码不一致会让程序崩溃**：核心自带的结果写出（`SRC/ModuleCoeffRepartitionBoxmodel.f90:223`/`:1405` 写 `csv/timestep_summary.csv`，其中的 `testcase`/`process_combo` 取自环境变量 `SCRAM_TESTCASE`/`SCRAM_PROCESS_COMBO`）在 Windows 上按 **ANSI 码页（GBK）** 落盘，而 `run_service.summarize_run`（`:221`）用 `timestep_path.open()` **按 UTF-8** 读回 ⇒ `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc1 in position 289` 崩溃。**实测**：案例名传 `"零质量 + NEAREST"` → 崩溃；换 ASCII 标签 → 正常。**触发面**：GUI 默认流程的 `case_name` 取自案例预设（ASCII），故当前不会踩到；但任何把非 ASCII 作为 `case_name` 传入 `prepare_run` 的调用（如我们的探测脚本）都会崩。**另一层隐患**：路径本身也会含中文（结果目录用「实验名_案例预设」命名），核心能否打开中文路径未验证 |
| 28 | 🔴 P1 | 初始化（**上游设计洞**） | ❌ 未修（2026-09-20 升级 1.2 时发现） | **`nucl_model=5` 时内核消费从未初始化的 `init_bin_number`**（详见上方 2026-09-20 章节 §4）：消费点 `ModuleDiscretization.f90:668-678`（**1.1 就有**），而 `:131` 只 `allocate`、`:145` 的读取被 `if(nucl_model.ne.5)` 跳过 ⇒ 读未初始化内存；1.2 在 `ModuleRedistribution.f90:127-136` 新增的不变量把它暴露为 `error stop 'SCRAM1.2: orphan mass/number before remap'`。实测触发点 `f=1, k=7`：有完整 30 物种质量 `1.2603962185956201` 而 `number=0`。**含义：1.1 时代这两个模板外混臂的数值建立在未初始化内存上，不可信** |
| 29 | 🔴 P1 | 初始化（**上游缺陷**） | ❌ 未修（2026-09-21 新发现） | **nl=5 多列分支重复投放**（详见下方 2026-09-21 章节 §3）：`ModuleDiscretization.f90:584-596` 两个判定条件不对称——`comp(k,f,1,2)==1`（硫酸盐）命中 **1 列**，`comp(k,f,1,1)==0`（黑碳）命中 **11 列**（`n_frac=5` 时 35 列）⇒ 同一份 `mass_init(k)/2` 被写 12/36 份，组成重分布再按"组成相同"累加合并。实测：内混臂 `37.679073599845388` vs 外混臂 `226.07444159907240`（= 12 × Σmass_init/2，**6 倍**）、`n_frac=5` 时 `678.22332479721695`（**18 倍**）；两臂终态粒子数比 **6.0000**（本模板未开凝并 ⇒ 差异全部来自初值）。**含义：外混臂初值不是"论文 hazy 场景"（硫酸盐:黑碳 = 1:1 vs 1:11），其数字一律作废** |

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
| 9 | 🔴 P1 | 初始化（移植契约） | nucl_model=5 时 cfg 多写了内核按约定不收的 3 行 ⇒ 文件指针错位 | nucl_model=5 + 配置含 init_bin_number/emission 行 | `app/config_binding/config_model.py`（内核保持本体原样） | `fix(port): 按 nucl_model 条件化写出/读入那三行；回退 7cc59c7 对 ModuleDiscretization.f90 的改动` |
| 10 | 🟡 P1 | 文档资产 | 界面截图文字全渲染为方框（三处目录共 25 张） | 在缺中文字体的环境运行截图脚本 | `scripts/capture_screenshots.py`、`docs/screenshots/`、`docs/user_manual_zh_assets/`、`docs/undergrad_lab_assets/` | `fix: 截图脚本加字体回退链与生成后自检`（已做）；**图需在 Windows 重生成** |
| 11 | 🟠 P1 | 运行 | Case Preset 在运行路径静默覆盖过程开关与运行时长 | 任何带 `case_preset` 的配置走 `prepare_run` | `app/services/run_service.py` | `fix: _with_case_preset 仅在调用方未显式设置时填预设（explicit_keys）` |
| 12 | 🟠 P1 | 运行/配置 | `redistribution_option`（RDB 核心模式）死控件：app 经 env 传递但 Fortran 不读，四值终态逐位相同 | `redistribution_option` 任意值 + 任意模板 | `SRC/ModuleCoeffRepartitionBoxmodel.f90`（需新增 env 读取）+ `app/services/run_service.py` | `fix: Fortran 读取 SCRAM_RDB_CORE_CONSERV 并接入 RDB 核心模式分支` |
| 13 | 🟠 P1 | 初始化/混合假设 | 零质量下内混/外混终态粒子数差 4 个数量级 | 初始质量为 0 或极小 | 待定（核心） | 待人工按物理定性（needs-domain） |
| 14 | 🟡 P2 | 重分配 | `redistribution_method=3/5` 粒子数暴增（×153 / ×383）而质量不变 | `redistribution_method` = 3 或 5 | 无需改（上游固有） | 已判：设计使然（Q-19） |
| 15 | 🟡 P2 | 运行/配置 | `mapping_scheme` 死配置（从不进核心，恒为 `COAG_TARGET_NEAREST`） | 任意配置 | `app/services/run_service.py`（或 schema） | 待人工：A 接入核心 / B 移除 |
| 16 | 🟠 P1 | 运行/配置 | 界面「环境状态」被未暴露的 `tag_init` 门控，出厂设置下无效果 | 出厂配置（`tag_init=1`） | GUI + 模板（`tag_init` 联动或暴露） | 待人工三选一（a/b/c） |
| 17 | 🟡 P2 | 运行/配置 | 普通模式排放窗口仅 2643.76 s（≈44 min），之后停止排放 | 所有 `nucl_model≠5` 运行 | `SRC/ModuleDiscretization.f90:1194-1205` | 待人工：a 置 0 / b 做成可配 |
| 18 | 🟠 P1 | 保真度/gate | 移植保真度 gate 未达标（气溶胶质量相对差 1.373e-5 > 1e-5） | 本体规范 cfg vs 仓库 exe | 无需改代码（编译标志 / 阈值口径） | 待人工三选一（a/b/c），并在 Windows 重测 |
| 19 | 🟠 P1 | 运行/配置 | `explicit_keys` 被 `normalize()` 丢弃 ⇒ #11 在 GUI 路径未修，预设仍覆盖过程开关与时长 | 载入配置能匹配上 `CASE_PRESETS` 时，在界面改过程开关/时长后运行 | `app/config_binding/config_model.py`、`app/views/main_window.py` | `fix: normalize 保留 explicit_keys，使 GUI 路径的显式设置优先` |
| 20 | 🟠 P1 | 运行/配置 | `tag_thrm`（热力学标记）死标签：核心 `read` 后零引用 | 任意模板，改「热力学标记」 | `app/views/main_window.py`（移除）或 `SRC/ModuleDiscretization.f90`（接入） | 与 #12/#15 同批：A 接上核心 / B 移除控件 |
| 21 | 🟠 P1 | 运行/配置 | `kind_composition` 运行前被 `_with_mixing_assumption` 强制归零 ⇒ 界面选择失效 | 在界面改「组分离散模式」后运行 | `app/services/run_service.py:338,345` | 待人工：a 允许用户选 / b 移除控件 |
| 22 | 🟠 P1 | 运行/可复现性 | 归档 `experiment_config.cfg` 与实际执行的 cfg 不是同一份 | 预设覆盖或 `_with_mixing_assumption` 生效时 | `app/views/main_window.py:1101-1102` | `fix: 归档改用变换后的数据（与 runtime cfg 一致）` |
| 23 | 🟠 P1 | 运行/配置 | 载入 cfg 后混合假设恒为 `EXTERNAL_MIXING`（cfg 无此字段）；提示语键名拼错不可见 | 任意 cfg 载入 | `app/config_binding/config_model.py:63`、`app/views/main_window.py:647`、`app/i18n/*.json` | 待人工：a 从 cfg 反推 / b 放开手选 / c 至少修 i18n 键名 |
| 24 | 🔴 P1 | 运行/健壮性 | 方法号越界（`dynamic_solver`=3–9）致核心**死循环挂住**，只能强杀；`redistribution_method` 7–9 静默空转；`kind_composition` 2–9 读未初始化内存 | 在上述控件填越界值后运行 | `app/views/main_window.py`（收窄范围/校验）；根因在 `SRC/ModuleAdaptstep.f90:86-100`（无 `else`，本体重编译才可改） | `fix: 方法号改为只列有效值的下拉 + 提交前范围校验` |
| 25 | 🟠 P1 | 运行/配置 | `dtmin`（最小时间步）死标签：核心读了不用；注释承诺的步长上下限从未实现 | 改「最小时间步」后运行（任何值都无效） | `app/views/main_window.py`（移除控件）；若要生效需在 `SRC/ModuleAdaptstep.f90:adaptime` 补钳制（改核心 + 重编译） | 待人工：a 移除控件 / b 核心补 DTMIN/DTMAX 钳制 |
| 26 | 🟠 P1 | 运行/对比功能 | 内外混对比在 `tag_external=1` 的配置上被混淆（两臂同时改表示能力与初始态） | 载入 `tag_external=1` 的 cfg 后点「比较 internal / external」 | `app/services/run_service.py`（`_with_mixing_assumption`） | 待人工：a 对比时把 `tag_external` 固定在两臂一致 / b 在界面标注该混淆 |
| 27 | 🟠 P1 | 运行/健壮性 | 案例名含中文时结果 CSV 编码不一致（核心按 GBK 写、Python 按 UTF-8 读）→ 崩溃 | `prepare_run` 的 `case_name` 含非 ASCII 字符 | `app/services/run_service.py`（读写编码）；核心侧见 `ModuleCoeffRepartitionBoxmodel.f90:223` | `fix: 读写 CSV 统一显式 encoding="utf-8"（或 errors="replace"），核心侧另行提案` |
| 28 | 🔴 P1 | 初始化（上游设计洞） | `nucl_model=5` 时内核消费从未初始化的 `init_bin_number`（1.2 新检查暴露为 `orphan mass/number before remap` 硬 STOP） | `nucl_model=5` **且** `tag_external=0` **且** `N_frac>1`（两个 hazy 模板的外混臂） | 消费点 `SRC/ModuleDiscretization.f90:669-679` 的 `:675`（块内**唯一**在 nl=5 下仍执行的读取点；`:619/:641/:664` 都在 `else nucl_model.NE.5` 里）；暴露点 `SRC/ModuleRedistribution.f90:127-136`（1.2 新增） | 待作者定性：a) 该块对 nl=5 跳过（推荐）；b) 该处按模式取 `number_init(k)`；c) 或把 nl=5 的 cfg 契约改为"必须带 `init_bin_number`"。**不要**改回 `:145` 的条件读（会破坏作者约定，也是 #9 刚回退的方向） |
| 29 | 🔴 P1 | 初始化（上游缺陷） | nl=5 多列初始化分支**重复投放**同一份初值（黑碳判定命中 11/35 列）⇒ 外混臂初值总量 = 内混臂的 **6 倍 / 18 倍** | `nucl_model=5` **且** `N_frac>1`（与 `tag_external` 无关） | `SRC/ModuleDiscretization.f90:584-596`（黑碳判定用"第 1 族下限=0"，而硫酸盐用"第 1 族上限=1"） | 待作者定性：a) 块 `:669-679` 对 nl=5 不执行；b) 黑碳判定改"第 4 族（BC）上限=1"（唯一命中 f=3）；c) 明确 nl=5 只支持 `n_frac=1` 并显式拒绝多列 |

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

### Bug #9: nucl_model=5 的 cfg 与内核读取契约不一致（**归因已于 2026-09-20 更正**）

> **一句话**：内核在「论文验证专用」成核模式（`nucl_model=5`）下**按设计不收**配置文件里的 3 行；软件这边却每次都写上去 ⇒ 核心读串行崩溃。**问题在软件侧，不在核心。**

| 项目 | 内容 |
|------|------|
| **位置（更正后）** | `app/config_binding/config_model.py`：`serialize()` 无条件写那三行、`parse()` 无条件读那三行，**两端都硬编码了「三行必在」** |
| **内核契约（不变的事实）** | `SRC/ModuleDiscretization.f90:129-136` 用 `if(nucl_model.ne.5)` 守卫那三行。**这是有意的**：`nucl_model=5` 是自成一体的硬编码验证模式（初始化走 `:564`/`:674`/`:713` 的 `if(nucl_model.eq.5)` 分支，排放硬编码 `gas_emision_rate(ESO4)=2.29D-4`），`init_bin_number`/`init_bin_emission` 读了也不使用。对照：**物种行是无条件读入的**（同文件 `:117-127`，读了丢弃）⇒ 契约本身是**不对称**的 |
| **归属铁证** | 本体源码 `/home/yifeihu/SCRAM1.1/SRC/ModuleDiscretization.f90`（作者原始树，2025-11-12）**同样**是 `if(nucl_model.ne.5)` 守卫，**读取语句序列与仓库内核一致**（`config_roundtrip.py` B 节自动比对通过）⇒ 内核无缺陷，是**移植方没有复刻这个约定**。（该文件在移植时重排过缩进，故非逐字节相同；逻辑语句本身一致） |
| **触发条件** | `nucl_model=5` + 配置文件含 `init_bin_number` 和 2 行 `init_bin_emission`（即 Python 写入器的默认格式） |
| **表现** | 那三行内核不消费 ⇒ 文件指针不前进；后续 `read(10,*)(diameter(k),...)` 读到 `init_bin_number` 数据 ⇒ `Bad real number/integer in list input` 崩溃。现行报错文本为 `Bad integer for item 1`（原文记的 `Bad real number in item 8` 是同因的另一种数据切分） |
| **影响面** | ① 两个 GMD 验证模板（`gmd_hazy_condensation`、`gmd_hazy_coag_cond`，均设 `nucl_model=5`）在发行核上必崩；② 同一缺陷阻塞了 `probe_cell --cfg docs/checktest/nucl_model5_fixed.cfg` —— **53 行夹具连解析都过不去**（`parse()` 抛 `IndexError`），即内核契约格式的文件在 app 侧不可读 |
| **修复（更正后）** | **py 侧**：新增单一判据 `_has_emission_block(scalars)`，`serialize()` 与 `parse()` 都跟随它；`parse()` 在 nl=5 时把偏移改到 `after_species` 本身，尾部若仍多出内容则**显式报 `ValueError`**（不再静默错位）；`normalize()` 的默认值不再给 nl=5 填 `1.0e3`。**内核侧**：回退 `7cc59c7` 对 `ModuleDiscretization.f90` 的改动，恢复本体原样 |
| **配套** | `main_window.py` 的 bin 数来源由 `len(init_bin_number)` 改为 `int(scalars["n_sizebin"])`（否则 nl=5 时排放表/初始质量表会塌成 0 列） |
| **守卫** | 新增 `scripts/linux/check_cfg_contract.py`：① 每个模板写出行数 == 契约行数且可往返；② 56 行文件喂 nl=5 必须报错；③ 53 行夹具必须读回且 diameter bounds 不错位。**修复前 4/16 项红灯，修复后 16/16 全绿** |
| **测试配置** | `docs/checktest/nucl_model5_test.cfg`（56 行 = **错误格式负例**，内核必崩）/ `docs/checktest/nucl_model5_fixed.cfg`（53 行 = **内核契约正例**，内核跑通） |

#### 实测记录（2026-09-20，Linux/gfortran 12.2）

内核用**回退后的原始源码**重建（`bash scripts/linux/build_runtime.sh`，内含 `FC=gfortran CC=gcc scons mode=safe`，md5 `e2b5212b`）。回退前的"修复版"内核为 `fb020540`，它保存在 git 的 `runtime/linux/ProgramSCRAM` 里，可用 `git checkout 7cc59c7 -- <该路径>` 取回。

| # | 实验 | 结果 |
|---|------|------|
| 1 | 原始内核 + `nucl_model5_fixed.cfg`（53 行） | ✅ 退出码 0，`inital total mass = 226.07444159907240`，与 2026-07-27 记录**逐位一致** |
| 2 | 原始内核 + `nucl_model5_test.cfg`（56 行） | ❌ 退出码 2，`Bad integer for item 1 in list input`（负例有效） |
| 3 | **py 生成的 cfg**（`gmd_hazy_condensation` 模板，改后 53 行）+ 原始内核 | ✅ 退出码 0 —— **这就是修复成立的决定性证据** |
| 4 | `probe_cell --cfg docs/checktest/nucl_model5_fixed.cfg` | ✅ EXT/INT 双臂 `status=ok`，无 `Bad real` |
| 5 | 全部 7 个模板 cfg 回归（改前 vs 改后逐字节比对） | ✅ **5 个 `nucl_model≠5` 模板完全相同（零回归）**；2 个 nl=5 模板恰好只少那三行 |
| 6 | `check_cfg_contract.py`：改前 / 改后 | ❌ 4/16 失败 → ✅ 16/16 通过 |

| 7 | **Linux 运行时内核刷新后**复测：① nl=5 + 53 行 → | ✅ 退出码 0（`228.81807486240999`） |
| | ② nl=5 + 56 行（负例）→ | ❌ 退出码 2，`Bad integer for item 1`（负例仍有效） |
| | ③ nl≠5（`gmd_paris_full`）+ 56 行 → | ✅ 退出码 0，`21.583170063260344`（与 #16 记录的基线**逐位吻合**） |
| 8 | `probe_cell --template gmd_hazy_coag_cond`（不设 `SCRAM_PROGRAMSCRAM`，走 `run_service` 自己的运行时分派） | ✅ 双臂 `status=ok` |

**证据**：`install_logs/bug9_20260920/`（被 `.gitignore` 忽略、不入库，含上表 1–7 的原始日志、改前/改后 7 个模板的 cfg；目录内有 `README.md` 索引）。

#### ⚠️ 连带后果：被 git 跟踪的 Linux 运行时内核必须同步重建（2026-09-20 补）

仓库里有**三个**容易混淆的二进制，务必分清：

| 路径 | 类型 | git | 本次是否变动 |
|---|---|---|---|
| `runtime/windows/ProgramSCRAM.exe` | PE32+ Windows | ✅ 跟踪（仅 `b3cf6f7`） | **从未变过** —— 发行件，用户侧那份 |
| `runtime/linux/ProgramSCRAM` | ELF Linux | ✅ 跟踪（`33c7f63`→`45de542`→`7cc59c7`） | **变了**：`fb020540` → `e2b5212b` |
| `runtime/windows/source/SCRAM1.1/ProgramSCRAM` | ELF Linux | ❌ gitignore（scons 产物） | 变了：`fb020540` → `e2b5212b` |

**第 2 个是必须动的**：`scripts/linux/build_runtime.sh` 的流程就是"在 `source/SCRAM1.1/` 跑 scons → `install` 到 `runtime/linux/`"，所以 `7cc59c7` 把 #9 的内核改动**编进了这个被跟踪的 Linux 内核**（md5 `fb020540`）。回退内核源码后若不重建它，就会出现**反向不兼容**：

- `runtime/linux/ProgramSCRAM`（`fb020540`，无条件读）**要求 56 行** cfg
- py 侧修好后 nl=5 **只写 53 行**
- ⇒ Linux 上跑 `gmd_hazy_condensation`/`gmd_hazy_coag_cond` **必崩**（实测：退出码 2，`Bad real number in item 2`）

**处置**：已执行 `bash scripts/linux/build_runtime.sh`（内部即 `FC=gfortran CC=gcc scons mode=safe` + `install`），`runtime/linux/ProgramSCRAM` 现为 `e2b5212b`，与回退后的源码一致。第 3 个（gitignore 的 scons 产物）随之同步，属正常构建产物刷新。

> 关于"信息损失"：**没有**。`fb020540` 一直安全保存在 git 里的 `runtime/linux/ProgramSCRAM`（`git checkout 7cc59c7 -- <该路径>` 可随时取回），原先记录的"该二进制不在版本库内、无法用 git 恢复"是**错的**。被刷新的 55 个 `.o`/`.mod` 也是纯中间产物。
> ⚠️ 用户态暂存副本仍需清理才能生效：`rm -rf ~/.local/state/scram_boxapp_mixing/runtime/linux`（GUI 检测到共享运行时变化会自动重暂存，强制刷新用这条；`build_runtime.sh` 输出里也有此提示）。

#### 平台影响：Windows 发行核**无需重编译**（与原记录相反）

| 项目 | 内容 |
|------|------|
| **原判断（已作废）** | 2026-09-14 复核认为「修复做在内核里 ⇒ 必须重编译 Windows 核，否则用户侧崩溃依旧」。该判断的前提是"修复必须动内核" |
| **更正后的结论** | 修复改在 py 侧后，**与内核二进制无关**：用户侧那个 2026-05-15 的 `ProgramSCRAM.exe` 本来就实现了 `if(nucl_model.ne.5)` 的原逻辑，py 侧生成 53 行 cfg 后它就能正常读 ⇒ **无需重编译、无需重发安装包** |
| **反而要注意的反向风险** | 若保留 `7cc59c7` 的内核改动（无条件读）**同时**又做 py 侧条件化，则 nl=5 会在新位置再次崩（`diameter` 行被当 `init_bin_number` 读走）。两者**互斥，绝不能同时成立**。本次已回退内核，故工作区为"内核原样 + py 条件化"这一种组合 |
| **仍然遗留的构建前置缺口** | Windows 机无 Fortran 工具链（原文记录属实）。但它只影响 **#18**（数值保真度复测）与将来的核心改动，**不再影响 #9** |
| **附带工具坑（套用其它补丁时，仍然有效）** | 本仓库 `core.autocrlf=true` 且工作树行尾混杂：`proposals/*.patch` 与 `ModuleCoeffRepartitionBoxmodel.f90`、`ModuleDiscretization.f90` 为 CRLF，而 `euler_coupled.f90`、`ModuleThermodynamics.f90` 为 LF ⇒ `git apply` 套 `bug7_double_add_v4.patch` 及 v1/v2/v3 会失败。加 `--ignore-whitespace` 后以上补丁均干净套用（已实测） |

#### 既有工具其实早就照到过这次内核偏离

`scripts/linux/config_roundtrip.py` 的 B 节会**按 `read(10,*)` 语句序列与本体 `/home/yifeihu/SCRAM1.1` 比对**。回退前它的输出是：

```
✓ 语句序列与本体一致（仓库含已知的 #9 改动（把条件读取改成无条件，语句本身相同））
```

即工具记录了偏离，但因为"语句条数相同"只作提示、未判失败。回退后恢复为干净的 `✓`（无 #9 标记）。**后续若要收紧：把这条提示升级为硬失败**（本体是条件读取时，仓库也必须条件读取）。


#### 2026-09-14 Windows 标准测试数值核查（**归属 Bug #18**；⚠️ 待重编译后复测）

背景：Windows 侧首次跑 devkit §6 全套标准测试，五项 smoke 全过（`import_smoke` / `gui_smoke` / `report_smoke` / `runtime_smoke` / `standard_tests`），报告 PDF 正常生成（LaTeX 可用）。**但标准测试只校验"跑通 / 数值有限 / status=ok"，不校验与基线的一致性**，故另行做了数值对照：

| 案例 | Windows 实测（核 `c9bb9df4`） | 既有基线（Linux / 手册） | 判定 |
|------|------|------|------|
| 仅凝并 `coag_only` | INT `24.482042410429116` / `9.55750171385341e9`；EXT 同质量 / `9.432931383598658e9` | 手册 `24.4820` / `9.5575e9` / `9.4329e9` | ✅ **逐位一致** |
| 全过程 `gmd_paris_full` INT | `32.70389840243378` / `1.0478035764210327e10`，**79 步** | `32.73376655624839` / `1.0260805990e10`，88 步 | ❌ 质量 −0.091%、数量 +2.12% |
| 全过程 `gmd_paris_full` EXT | `33.86200404514652` / `1.2289972366584045e10`，**635 步** | `33.751055266282556` / `1.1638880310e10`，540 步 | ❌ 质量 +0.329%、数量 **+5.59%**（对手册 `1.1436e10` 为 +7.47%）；步数 +17.6% |

已逐项排除的原因：

- **不是 9 月两次源码改动造成的**：`45de542` 只改 `coeff_make_dir`（建目录），`7cc59c7` 只改配置解析且对 `nucl_model≠5` 等价 ⇒ 对本案例**无数值影响**（已逐行核对 diff）。
- **不是模板 / 预设差异**：`core/templates`、`examples/` 自 `b3cf6f7` 起无提交改动；`gmd_paris_full` 定义（`app/services/template_service.py:136-149`，base=baseline、with_coag/cond/nucl=1、12h）在 `fe6656d` 中未变（该提交只改两个 hazy 模板）。
- **不是配置生成差异**：期间 `app/` 无提交改动，cfg 由同一套代码生成（运行时 manifest：`cache_mode=ALWAYS_REBUILD`）。

⇒ 剩余唯一解释：**同一份源码、同一份 cfg，2026-05-15 构建的 Windows 核与 2026-09 构建的 Linux 核跑出不同结果**（连自适应步数都不同）。对照案例 `coag_only` 逐位一致，说明核心逻辑未见损坏，全过程案例对构建差异敏感。两种可能**尚未区分**：① 纯构建/工具链差异（编译器与浮点参数不同）经自适应步长放大；② 5 月发行核与提交源码本就不一致。

**待办与判据**：本项已归属 **Bug #18**，与 #9 **无关** —— #9 的修复改在 py 侧（见上方 #9 章节），不需要重编译任何核心，故原"与 #9 放在同一次重编译里"的安排作废。跑一次 Windows 核心重编译后复跑上表三例——若重编后与 Linux / 手册基线一致 ⇒ 判为旧核问题、本项关闭；若仍偏离 ⇒ 按 **Bug #18** 的阈值口径（总质量逐位一致为硬判据、气溶胶质量相对差 ≤1e-5）与 Windows 规划 **W5** 的决策一并处置。

> 旁证（因步数不同，不可直接比较）：`anomaly_flags.csv` 条目数 Windows EXT 1413 / INT 522，brief §2.2 记录的 Linux 基线为 EXT 1232 / INT 578。
> 证据（本机 `install_logs/` 被 `.gitignore` 忽略、不入库）：`install_logs/auto/20260914-151550/standard_tests/`、`install_logs/auto/20260914-151726/quick_test/`（两处共约 415 MB）。


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

**说人话**：手册和 README 里的界面截图，文字全变成"□□□□"。原来的判断是"生成截图的机器缺中文字体，要在有字体的 Windows 上重新生成"。**这个判断是错的** —— 2026-09-14 实测证明：这台 Windows 的 `C:\Windows\Fonts` 里明明有 `msyh.ttc`（微软雅黑）、`Deng.ttf`（等线），但 Qt 报"**0 个字体家族**"。真正的原因是脚本自己把渲染平台强制成了 `offscreen`，而 Qt 的 offscreen 插件在 Windows 上**不加载系统字体库**。所以在**任何** Windows 机器上跑都会是方框 —— 这个"去 Windows 重生成"的方案本身就不可能成功。

| 项目 | 内容 |
|------|------|
| **根因（2026-09-14 实测定位）** | `scripts/capture_screenshots.py:11`：`os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`。Qt 的 `offscreen` 平台插件在 Windows 上返回**空字体库** ⇒ `QFontDatabase.families()` = **0** ⇒ `app.setFont(QFont("Microsoft YaHei UI", 9))` 找不到任何字形 ⇒ 全部退化为 □（中英文与数字皆然） |
| **决定性对照实验** | 同一台机器、同一段代码，只切平台：`QT_QPA_PLATFORM=offscreen` → **0 个家族**；`QT_QPA_PLATFORM=windows` → **140 个家族**，其中含 `Microsoft YaHei UI`／`Microsoft YaHei`／`DengXian`／`FangSong`。⇒ 字体从未缺失，是平台插件的问题 |
| **为什么原文的修复方向永远不会成功** | 原文（含「T1/T2/T4」加固项与人工决定 ④）写的是"需在有字体的 Windows 上重生成"。但**问题是平台插件而非字体**，所以在任何 Windows 上重生成都还是方框 —— 这正是该条目长期卡住的真正原因 |
| **修复（2026-09-14，已落地）** | `scripts/capture_screenshots.py` 三处改动：① 平台自适应 —— Windows 用 `windows`、其他平台仍用 `offscreen`；② `pick_cjk_font` 在家族名拿不到时**按字体文件注册**（`C:/Windows/Fonts/msyh.ttc` 等）；③ 仍拿不到任何 CJK 字体则 `SystemExit` 显式报错并给出安装提示（落实原 T1 意图"不满足则直接失败"，不再静默产方框图） |
| **实测验证（2026-09-14）** | 不设任何环境变量直接跑修复后的脚本：字体正确识别为 `Microsoft YaHei UI`，密度 **`main_zh` 0.0115 → 0.0470**、`main_en` 0.0114 → 0.0368、`structure_editor` 0.0116 → 0.0312、`help_panel` 0.0066 → 0.0517；目视 `main_zh.png` 文字全部可读（"新建实验／运行／停止／查看结果／导出报告／实验设置／结构编辑…"）。产物在 `install_logs/shots_verify/`（未覆盖发布资产） |
| **剩余待办** | ① 三处发布资产共 26 张（`docs/screenshots/` 9、`docs/user_manual_zh_assets/screenshots/` 9、`docs/undergrad_lab_assets/` 8）仍需按 §7 重生成 —— 但**现在可以在本机一次做成**，不必再找别的机器；② 自检阈值对**结构稀疏**的面板会误报（`running_state` 0.0154 / `results_view` 0.0124 / `report_panel` 0.0114 / `settings_panel` 0.0106）—— 已目视确认这 4 张文字正常，属"页面本来就空"而非缺字；建议给这 4 张设白名单或按面板分级阈值 |
| **顺带发现（i18n，非本 Bug）** | 修好字体后截图暴露出 3 个 i18n 缺键，界面直接显示英文键名：① `config_preview`（实验设置页分组框标题显示 "config preview"）；② `mixing_scheme_readonly_tip`（JSON 里只有拼错的 `mapping_scheme_readonly_tip`，导致 #23 的说明文字不可见）；③ `status`（运行监控页首行标签显示英文 "status"）。另：真有 **9** 个键定义了但从未被引用（`about`/`about_text`/`about_text_full`/`load_experiment`/`mapping_scheme_readonly_tip`/`new_from_defaults`/`open_tables`/`raw_preview`/`save_experiment`）——**更正**：2026-09-14 早前在《配置开关与标签总表.md》中记为"33 个键未引用"是错的，那是只统计了 `i18n.t("字面量")` 而漏掉了循环里的 `i18n.t(key)` 动态引用 |
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

### Bug #13: 零质量时内混/外混的粒子数差 4 个数量级

**说人话**：没有气溶胶（或气溶胶极少）的配置下，两种混合假设算出来的粒子数天差地别——一边是 0，另一边是 41 亿。同一个物理设置，两侧不该差这么多，所以要判断这属于"本来就该这样"还是"算错了"。

| 项目 | 内容 |
|------|------|
| **触发条件** | 初始质量全零或极小（`docs/checktest/zero_initial_mass_test.cfg`、`tiny_initial_mass`） |
| **表现** | `zero_initial_mass_test`：EXT `final_number=0.0`，INT `4.12452e9`；`tiny_initial_mass`：EXT `4.99998e5`，INT `4.12452e9` |
| **证据** | `install_logs/auto/probes/q07_zero_mass_test/probe.json`、`q07_tiny_mass/probe.json`（2026-09-12 10:11 轮） |
| **性质** | ❓ **待人工物理判断**（标签 `needs-domain`）：设计使然 or 缺陷 |
| **为什么还没定** | ① 零质量路径在应用内不可达（模板基座都是非零初值），只能手工载入配置触发；② 两侧差异是否合理需要懂模型语义的人判断 |
| **下一步** | 按 `_test/_fixed` 夹具惯例固化后定性；若判为缺陷，走"先出提案、再动核心"的流程 |

### Bug #14: 重分配方法 3/5 会让粒子数暴涨（已判：设计使然）

**说人话**：换用"重分配方法 3 或 5"时，粒子数会涨 3 倍到 383 倍，但总质量基本不变。这是**这两种方法本身的定义**决定的——它们保证质量守恒、粒子数则按新直径重算。与论文里的定义一致，**不是缺陷**。产品默认用方法 2，用户碰不到。

| 项目 | 内容 |
|------|------|
| **触发条件** | `redistribution_method` = 3（euler_mass）或 5（hemen） |
| **表现** | `gmd_paris_condensation + method=3` → EXT `5.28349e12` / INT `6.15417e12`（method=2 为 `3.44565e10`，**×153**）；method=5 → `1.07e11`（×3）；质量基本不变 |
| **判定依据** | `redist_euler.f90:152`（3=EULER_MASS）与 `hemen.f90:357/371` 在重分配后按 `N(k)=6*Q/(PI*rho*d^3)` 由质量重算数量，且 `1-Qnew/Qold` 超 `Eps_machine` 即 STOP（质量守恒被强制）；`euler_number.f90:154` 则守恒数量。与 Zhu et al. (2015) 的方法定义一致 ⇒ 上游固有、非移植缺陷 |
| **为什么曾漏判** | 既有的模糊测试判据只查质量残差与有限性，不查数量守恒，故 `fuzz_q11` 报告里 idx 9 出现 ×383 却记为 clean —— 判据盲区，已记录 |
| **结论** | ✅ 设计使然（Q-19 关闭），产品侧默认 method=2 不受影响 |

### Bug #15: `mapping_scheme` 是死配置

**说人话**：配置里有个 `mapping_scheme` 开关（可选 `LEGACY` / `DETERMINISTIC_NEAREST`），模板和校验器都在用它，但它**从来没送到核心程序**——送过去的是"混合假设"那个值，两者不是一回事，结果核心实际永远按 `COAG_TARGET_NEAREST` 跑。所以这个开关选了什么都没用，**和 #12 是同一类毛病**。

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py` 的 `_coag_mapping_mode(scheme)`；调用点在 `run_comparison` 的 `MIXING_ASSUMPTIONS` 循环 |
| **根因** | `_coag_mapping_mode` 收到的是混合假设（`INTERNAL_MIXING`/`EXTERNAL_MIXING`），两者都不等于 `LEGACY` ⇒ 送给核心的 `SCRAM_COEFF_REPARTITION_MODE` **恒为 `COAG_TARGET_NEAREST`**；`run.log` 里记录的 `mapping_mode` 因此是固定值 |
| **易混淆点** | GUI 的"mapping_scheme"下拉实际绑定的是**混合假设**（`app/views/main_window.py:214-218`），与这个配置标量不是一回事 |
| **证据** | 2026-09-12 22:15 轮夹具固化（Q-21）：`probe_cell gmd_paris_condensation` 默认 vs `--set mapping_scheme=LEGACY` 两臂终态**逐位相同**（EXT mass=33.0654 / INT mass=32.6176 / number=3.44653e10 / steps=42），两臂 `run.log` 的 `mapping_mode` 均 = `COAG_TARGET_NEAREST`、生成 cfg 无 mapping 字段；证据 `install_logs/auto/probes/q21_{default,legacy}/` |
| **下一步** | 待人工二选一：A) 真正接上核心；B) 从界面/schema 移除并清理 env 传递（**与 #12 同批处理**） |

### Bug #16: 界面上的「环境状态」选了没用

**说人话**：界面上"环境状态"有霾天/城市/清洁三个选项，出厂设置下选哪个结果都一样。原因不是这功能坏了，而是**要不要用这三套内置场景分布，由另一个开关 `tag_init` 决定，而这个开关界面上没有、用户改不了**。把它设成 0 之后实测三个场景确实会产生不同结果，所以功能是好的，只是被挡住了。

| 项目 | 内容 |
|------|------|
| **触发条件** | 出厂配置（所有基座 cfg 的 `tag_init` 都是 1，即用配置里的逐档质量） |
| **表现** | `gmd_paris_full` 下 init_scenario=1/2/3 的 t=0 质量 `21.583170063260344`、数量 `1.4625e10` **逐位相同** |
| **根因（Q-24 已定位）** | 初值是否采用内置三套场景分布由 `tag_init` 决定，而 `tag_init` 在 GUI 未暴露 |
| **关键证据** | `tag_init=0` 臂三场景对照（`gmd_paris_full`, 0.5h）：status=ok、无 NaN/Inf、residual~1e-18，终态质量 EXT `11.1139`/`11.1076`/`11.1028` **三场景不同**，来自冷凝（Mass Cond~11.09）⇒ **路径数值可用、控件非设计性死，仅被门控**。历史依据：控件由 `321fca2`（2026-07-22）加入，对应 `ModuleDiscretization.f90` 的三种三模态对数正态分布；`05d609c` 曾判"tag_init=0 方案不可行"（Q-24 已证伪） |
| **证据** | `install_logs/auto/probes/q24_taginit0_s{1,2,3}/` |
| **下一步** | 待人工三选一（属"增删控件"类）：a) 场景与 `tag_init` 联动（**Q-24 已证可行**，推荐）；b) 暴露 `tag_init` 并标注条件；c) 移除下拉 |

### Bug #17: 排放只在前 44 分钟发生

**说人话**：普通模式下，排放只在前 2643.76 秒（约 44 分钟）发生，之后就完全停止，跟你设置模拟多久无关。这是上游代码里写死的经验值。

| 项目 | 内容 |
|------|------|
| **位置** | `SRC/ModuleDiscretization.f90:1194-1205`：`nucl_model=5` 时 `time_emis=43200 s`，否则 `2.64376e3 s`；超出后 `emis_dt=0` ⇒ 停止排放。另两处同常数（`:1274`/`:1287`）只是"排放引起的步长限制"守卫，**不关闭凝并/冷凝** |
| **性质** | 代码无注释、全仓与本体无其它引用 ⇒ 判为作者为某场景调死的经验值；**上游固有**，非移植缺陷，不计入 gate |
| **数值确认（Q-23）** | `gmd_paris_emission_only` 全关过程，12h 与 0.5h 两臂的排放量比值 = `0.6808484885` = `1800/2643.76` **逐位精确** ⇒ 窗口 2643.76 s 确认、窗口内排放线性 |
| **影响** | 本体论文 cfg（`INIT/cfg_megapole_01072009.cfg`）emission 全 0 ⇒ 论文结论不受影响；仓库 baseline 基座 SO4 emission=1.72e-5 ⇒ 12 小时里只有前 44 分钟在排放 |
| **证据** | `install_logs/auto/probes/q23_emis_window_{12h,05h,30min}/` |
| **下一步** | 待人工二选一：a) 与本体口径一致，把 emission 置 0；b) 新增"排放时长可配"（新功能） |

### Bug #18: 移植保真度 gate 未达标（数值差一点点）

**说人话**：拿同一份配置、同一份系数数据，让"原始研究版本"和"移植过来的开发包"各跑 12 小时，比最后的数字。**总质量完全一样，一个数字都不差**；但**气溶胶质量差了 1.373e-5**（十万分之一点四），而仓库自己定的合格线是 1e-5，所以判不合格——**差得极小，但越线了**。原因不是代码写错，是两边**编译时用的参数不一样**（本体 `-g`、仓库 `-O2`），浮点数相加顺序不同，末位就会有差别。

| 项目 | 内容 |
|------|------|
| **口径 / 工具** | `scripts/linux/fidelity_check.py`（已脚本化，建议挂 deep 轮） |
| **实测** | 总质量 `36.48929720841787` 两侧**逐位一致**（达标）；气溶胶质量 `24.22834256300118` vs `24.22867515785633`，**相对差 `1.373e-05` > 阈值 `1e-5` ⇒ `gate_pass=False`**；气相 `2.713e-05`、Mass Cond `1.258e-04`、total_water `4.320e-05` |
| **成因** | `-g` vs `-O2 -ffp-contract=off` 的编译标志差异（非代码改动）⇒ 属"阈值/口径"问题、非移植缺陷。**注意：该归因目前是推断，尚未做"同一份源码、两种标志各编一次"的决定性实验** |
| **历史遗漏** | 手工轮（runbook P4 / 台账条目 `fidelity · upstream_vs_devkit · megapole12h`）把 `1.4e-5` 记为 clean，但按 release-gate 阈值实际未达标 |
| **证据** | `install_logs/auto/fidelity_check/20260913-082220/`、`install_logs/auto/fidelity_q26/`；台账条目 `Q-26 · fidelity_gate · upstream_vs_repo · contract` → bug |
| **下一步** | 待人工三选一（**不得自行放宽阈值**）：a) 维持 1e-5 并给本体/仓库统一编译标志（重编译对齐）；b) 调整阈值并记录依据；c) 以"总质量逐位一致"为硬判据、气溶胶差为软信号（**推荐**）。另需在 Windows 重编译后复测（见本表上方的「2026-09-14 Windows 标准测试数值核查」，该节现归属 #18） |

### Bug #19: #11 的修复在 GUI 路径上失效（`explicit_keys` 被 `normalize()` 丢弃）

**说人话**：这个软件里有个"案例预设"，会规定"这次跑哪些过程、跑多久"。界面上你手动改了过程开关或时长，本该以你的为准（这是 #11 修过的东西）。但实测发现：**探针脚本路径修好了，界面路径没有** —— 在界面上关掉凝并、把时长改成 1 小时，生成的配置文件里仍然是"开凝并、12 小时"。

| 项目 | 内容 |
|------|------|
| **位置** | `app/config_binding/config_model.py:180-195`（`normalize()` 构建的新字典不含 `explicit_keys`）+ `app/views/main_window.py:780`（`_collect_data` 结尾 `return self.config_model.normalize(data)`）+ 消费点 `app/services/run_service.py:96` |
| **触发条件** | 载入的配置能匹配上 `CASE_PRESETS`（即 `_match_case_preset` 返回非空），且用户改动了与预设建议值不同的过程开关/时长，然后点运行 |
| **表现** | 界面上关掉凝并（`with_coag` 0）、时长改 1 小时 → 生成的 cfg 仍是 `1 ## coagulation switch` 与 `12 ## simulation time hours`。用户设置被静默忽略，且**界面不回显任何提示** |
| **根因** | `_collect_data` 在 return 之前正确算好了 `data["explicit_keys"]`（`main_window.py:704-718`），但随即调用的 `normalize()` 只保留一组固定键，把该键丢掉；`prepare_run` 取到的是空集 ⇒ `_with_case_preset` 无条件套用预设四元组（`with_coag`/`with_cond`/`with_nucl`/`final_time_hours`） |
| **实测（2026-09-14）** | 模板 `gmd_paris_full`，模拟界面操作"关凝并 + 时长 1h"：<br>· 路径 A（`explicit_keys` 保留，即 `probe_cell`/`noop_probe`）→ `with_coag=0`、`final_time_hours=1.0` ✅<br>· 路径 B（`explicit_keys` 已丢，即 GUI 真实路径）→ `with_coag=1`、`final_time_hours=12.0` ❌ |
| **为什么当初验证漏掉** | #11 的验证用的是 `noop_probe.py --template tutorial_minimal`（`docs/BUG_TRACKING.md` 修复状态栏），该脚本走探针路径、显式传 `explicit_keys`，因此**从未覆盖 GUI 路径** |
| **影响面** | ① 用户可见：界面改的过程开关/时长对能匹配预设的配置全部无效；② 证据面：凡以 GUI 运行产生的 `install_logs` 数值，都不代表界面上显示的参数 |
| **结论分类** | `confirmed-bug`（有实测对照） |
| **标签** | `port`（计入 gate） |
| **下一步** | `normalize()` 保留 `explicit_keys`（或在 `_start_runs` 传参前暂存）；补回归判据：界面改开关后生成 cfg 必须变 |

### Bug #20: `tag_thrm`（热力学标记）是死标签 —— 核心读了就扔

**说人话**：界面上「高级参数 → 热力学标记」这个 0–9 的数字框，**改什么都没用**。因为核心程序把它读进来之后，就再也没看过它一眼。

| 项目 | 内容 |
|------|------|
| **位置** | GUI：`app/views/main_window.py:349`（`field_widgets["tag_thrm"] = self._int_spin(0, 9)`）与 `:354`；核心：`SRC/ModuleDiscretization.f90:89`（`read(10,*)dynamic_solver,tag_thrm`） |
| **证据** | `grep -rni "tag_thrm" SRC INC` → **仅 1 处命中**（就是那行 `read`）。对照词频：`tagrho` 3 处 / `tag_external` 6 处 / `Tag_init` 8 处 —— 这些才是真被用的 |
| **表现** | 在「热力学标记」填任意 0–9，终态逐位相同 |
| **易混淆点** | 它与 `dynamic_solver` **挤在同一行**（`read(10,*)dynamic_solver,tag_thrm`），很容易被误认为"和求解器一起生效" |
| **结论分类** | `confirmed-bug`（grep 证据为确定性判据） |
| **标签** | `port`（与 #12/#15 同类："界面有控件、核心不用"） |
| **下一步** | 与 #12/#15 同批处理：A) 核心接入该标签；B) 从 GUI/schema 移除 |

### Bug #21: `kind_composition`（组分离散模式）在运行路径被强制归零

**说人话**：界面上「组分离散模式」选了 1，实际跑的时候会被悄悄改回 0。

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py:338`（INTERNAL 分支）与 `:345`（EXTERNAL 分支）—— 两个分支都写 `data["scalars"]["kind_composition"] = 0` |
| **触发条件** | 任何 GUI 运行（单次或比较） |
| **表现** | 界面填 1 → 实跑 cfg 恒为 `0 ## composition discretization mode` |
| **根因** | `prepare_run` 的调用序是 `_with_mixing_assumption`（强制归零）→ `_with_case_preset` → `serialize`（`run_service.py:97-108`）⇒ 界面值在序列化之前就被覆盖 |
| **连带** | 归档 cfg（`experiment_config.cfg`）反而保留了用户的 1（见 #22）⇒ 归档与实跑两份配置不一致 |
| **结论分类** | `confirmed-bug`（代码路径无条件执行） |
| **标签** | `port` |
| **下一步** | 明确 `kind_composition` 是否**应当**由混合假设决定：若是，则应在 GUI 上禁用并说明；若不是，删掉这两行赋值 |

### Bug #22: 归档的 `experiment_config.cfg` ≠ 实际执行的配置

**说人话**：软件会把这次的参数存一份到结果目录，方便你事后追溯。但存下来的那份，和真正拿去算的那份**可能不是同一个内容** —— 你照着归档文件重跑，结果会对不上。

| 项目 | 内容 |
|------|------|
| **位置** | 归档：`app/views/main_window.py:1101-1102`（`auto_cfg = output_root / "experiment_config.cfg"`，序列化 `self.data`）；实跑：`app/services/run_service.py:97-108`（先 `_with_mixing_assumption` + `_with_case_preset`，**再**序列化） |
| **触发条件** | 任一变换生效时：① 案例预设覆盖过程开关/时长（见 #19）；② `_with_mixing_assumption` 改 `n_frac`/`fraction_bounds`/`tag_external`/`kind_composition` |
| **表现** | 归档文件与 `boxapp_cfg/<case>_<scheme>.cfg` 在过程开关、时长、`n_frac`、`fraction_bounds`、`tag_external`、`kind_composition` 上可能不同 |
| **影响面** | 教学/报告场景的**可复现性**：用户照归档文件手动重跑会得到与归档结果不同的数值；报告里引用的参数与实际算的参数不符 |
| **结论分类** | `confirmed-bug`（调用序决定，无条件） |
| **标签** | `port`（计入 gate） |
| **下一步** | 归档改用与 runtime cfg 相同的、变换后的数据；或在归档头写明"本次实际生效值" |

### Bug #23: 载入 cfg 后"混合假设"恒为 `EXTERNAL_MIXING`（设计意图未实现）

**说人话**：界面上有个「混合假设」下拉框，是锁住的、不让你改，旁边写着"由载入的配置文件决定"。听起来合理 —— 但**代码从来没从文件里读过这个值**，cfg 里压根没有这个字段，所以它永远是"外混"。结果：你上传一份内部混合的配置，软件也只能按外混跑。而且那段解释文字**还因为一个键名拼错，你根本看不到**。

| 项目 | 内容 |
|------|------|
| **位置** | `app/config_binding/config_model.py:63`（`parse()` 的返回字典里写死 `"mixing_assumption": "EXTERNAL_MIXING"`）；`app/views/main_window.py:647`（读该值当"锁定值"）、`:975-981`（`_on_mixing_scheme_changed` 把用户改动弹回）；i18n 键名见下 |
| **设计意图** | i18n 提示语（`app/i18n/zh_CN.json`）："混合假设由载入的配置文件决定，不可手动修改。内混和外混的 fraction 表结构和计算逻辑不同，请载入对应类型的 cfg 文件。"—— 意图是**合理的**（错误切换确实会导致 fraction 表结构与计算逻辑不匹配），引入于提交 `3455826`（2026-07-23） |
| **实现缺口** | `parse()` 没有任何"从 cfg 反推内混/外混"的逻辑（例如 `n_frac == 1` ⇒ 内混、`n_frac > 1` ⇒ 外混 的判据未被使用）⇒ 所谓"由文件决定"实为"恒为外混" |
| **附带缺陷** | 提示语键名拼错：代码写入的是 `mixing_scheme_readonly_tip`（`main_window.py:218` 的 `setToolTip`、`:981` 的 status 提示），而两个语言文件里只有 `mapping_scheme_readonly_tip` ⇒ 查不到该键、回退到 `en_US` 也查不到 ⇒ **直接显示英文键名本身**。代码与 JSON 的键名在同一提交 `3455826` 引入，属笔误 |
| **表现** | ① 上传任何 cfg（含 `n_frac=1` 的内混配置）后，下拉恒显示 `EXTERNAL_MIXING`；② 用户尝试手改会被弹回；③ 弹回时状态栏显示的是键名字符串而不是解释文字，用户完全不知道发生了什么 |
| **结论分类** | `confirmed-bug`（`parse()` 硬编码 + 实测输出已验证） |
| **标签** | `port` |
| **下一步** | 三选一（属"增删/改界面控件"类，需人工拍板）：a) 从 cfg 反推（`n_frac` 判据），真正做到"由文件决定"；b) 放开手选，并校验 fraction 表结构与所选假设一致；c) 维持现状，但**至少修正 i18n 键名**让解释可见。另：修正键名可与本批同做，属纯文字修复 |

### Bug #24: 方法号越界导致核心死循环挂住（已实测）

**说人话**：「动力学求解器」这类控件给的是 0–9 九个数字，但核心只认 0/1/2。**你要是填了 3 到 9，核心会卡死在里面 —— 不报错、不退出、不写日志，界面上"运行中"永远不动，只能强杀进程。**

| 项目 | 内容 |
|------|------|
| **位置（界面）** | `app/views/main_window.py:348-351` —— `dynamic_solver` / `tag_thrm` / `kind_grid` / `kind_composition` 全部用 `self._int_spin(0, 9)` |
| **位置（核心）** | `SRC/ModuleAdaptstep.f90:86-100` 的 solver 分发只判 `eq.0` / `eq.1` / `eq.2`，**没有 `else` 分支**；而唯一推进子步时钟的 `current_sub_time = current_sub_time + sub_timestep_splitting` **只存在于 `Etr_solver`(`:415`) / `Euler_solver`(`:482`) / `Ros2_solver`(`:634`) 内部**；外层是 `do while (current_sub_time .lt. final_sub_time)` 且**无 `exit`**（`:63-126`） |
| **机理** | 越界值 ⇒ 不调用任何求解器 ⇒ 时钟不前进 ⇒ `do while` 永不退出。程序不报错（因为控制流合法，只是空转） |
| **实测（2026-09-14）** | 同一模板、同一时长（`gmd_paris_full`，0.01h）：<br>· **对照组** `dynamic_solver=2` → `status=ok`、`wallclock=0.26s`、EXT 6 步/INT 4 步、日志含 **5 条 `Progress`** 并正常收尾<br>· **实验组** `dynamic_solver=5` → `timeout 60` **强杀（exit 124）**、`run.log` 停在 `Calculation in progress...`、**0 条 `Progress`**、连第二个混合假设臂都没跑到<br>证据：`install_logs/auto/probes/gmd_paris_full__gmd_paris_full__dynamic_solver-5__final_time_hours-0.01/` |
| **同类越界语义（同一批界面范围问题）** | ① `redistribution_method` 7–9 → `redist_euler.f90:184` 的 `SELECT CASE` 有 `CASE DEFAULT`，**只打印一句提示就返回** ⇒ 该步骤被静默跳过（不崩，但结果错）；0–1 → `ProgramSCRAM.f90:134` 的 `if(...ge.2)` 为假 ⇒ 压根不调用重分配。② `kind_composition` 2–9 → `ModuleDiscretization.f90:217-221` 的 `if(==1)/elseif(==0)` 两个分支都不进 ⇒ **`frac_bound` 已 `allocate` 却从未赋值**，后续读未初始化内存。③ `nucl_model` ∉ {1,5} → 成核静默不发生（即使勾着"启用成核"）。④ 其余：`sulfate_computation`/`kind_grid`/`tagrho`/`Tag_init`/`init_scenario` 都是 `if(...)/else` 结构，越界值被**当成另一个值**处理 |
| **结论分类** | `confirmed-bug`（有实测对照臂） |
| **标签** | `port`（界面侧可完全解决；核心侧的 `else` 缺失属 `upstream`，但不必改核心也能挡住） |
| **下一步** | ① 把方法号控件从"0–9 数字框"改为"只列有效值的下拉"（**推荐**，越界值根本选不到）；② 或在提交前加范围校验并拒绝运行；③ 登记 `tag_thrm`/`kind_composition` 的处置与 #12/#15 同批进行 |


### Bug #25: 界面「最小时间步」是死标签，且注释承诺的步长上下限从未实现

**说人话**：界面上「最小时间步 (秒)」这个数字框，**改什么都没用** —— 核心把它读进来之后就没再看它一眼。而且更值得注意：代码注释里写着"要把新步长限制在 DTMIN 和 DTMAX 之间"，但**这个限制从来没写进代码**，注释提到的那个 `time.inc` 文件在本仓库里根本不存在。

| 项目 | 内容 |
|------|------|
| **发现方式** | 由新增的 `scripts/check_field_registry.py`（字段登记表对账）**自动报出**。该脚本对登记表里每个字段核对两件事：核心的 `read(10,*)` 是否读它、读完之后是否真的使用。判定"使用"时排除了三类不算使用的出现：类型声明行、纯注释行、以及读取语句本身 |
| **证据（全核心 3 处命中，0 处使用）** | ① `SRC/ModuleAdaptstep.f90:293` —— **注释**：`! DTMIN and DTMAX defined in time.inc`<br>② `SRC/ModuleDiscretization.f90:101` —— **读取**：`read(10,*)dtmin`<br>③ `SRC/ModuleInitialization.f90:105` —— **声明**：`double precision :: final_time,dtmin! Time step and finnal time` |
| **关键旁证：`time.inc` 不存在** | `INC/` 目录只有 `CONST.INC`、`CONST_A.INC`、`paraero.inc`、`parameuler.inc`、`pointer.inc`；全仓库 `find -iname "time.inc*"` **无结果**；`grep INCLUDE` 也没有任何文件引用它 |
| **钳制确实缺失** | `ModuleAdaptstep.f90:290-300`（`adaptime`）：注释写 `! and to keep new time step between ! DTMIN and DTMAX defined in time.inc`，紧接着 `R=(1.D+02)/(1.D-05)`、`n2err=DMIN1(n2err,EPSER*tmp)`、`n2err=DMAX1(EPSER/tmp,n2err)`、`T_dt=T_dt*DSQRT(EPSER/n2err)` —— **全程没有出现 DTMIN/DTMAX 的钳制语句**，只有对 `n2err` 的上下限约束 |
| **用户可见影响** | ① 界面「最小时间步」改任何值，终态逐位相同；② 自适应步长**实际没有下限保护**（只有 `n2err` 的间接约束）—— 与注释承诺的行为不符 |
| **与其它条目的关系** | 与 #12（`redistribution_option`）、#15（`mapping_scheme`）、#20（`tag_thrm`）同属「界面有控件、核心不用」这一类。**这是第四个同类条目**，也是第一个由对账脚本而非人工阅读发现的 |
| **结论分类** | `confirmed-bug`（全核心词频扫描 + `time.inc` 存在性核查，均为确定性判据） |
| **标签** | `port`（界面侧可解决）；若要让步长钳制真正生效则属 `upstream` 新功能 |
| **下一步** | 待人工二选一：a) 从界面/schema **移除该控件**（推荐 —— 它当前本就没有任何效果，移除不影响任何既有结果，且避免误导用户）；b) 在 `adaptime` 里补上 DTMIN/DTMAX 钳制（需改核心 + 重新编译，属新增功能，且会改变既有数值基线）。另：移除控件会改变界面布局 ⇒ 触发 §7（截图与三处手册资产同步） |

> **附：本轮新增的对账工具**
> `core/schema/gui_fields.json` + `scripts/check_field_registry.py`。对账五方：`config_schema.json`（配置声明）、登记表、`SRC/*.f90`（核心是否读/用）、`app/i18n/*.json`（两个语言的标签是否齐）、`app/views/main_window.py`（界面到底有没有控件）。当前输出：死标签 3 个（`tag_thrm` / `redistribution_option` / `dtmin_seconds`）、死控件 1 个（`redistribution_option`）、界面上改不了的配置项 1 个（`tag_init`，即 #16 的成因）、运行时变换丢弃 `explicit_keys`（#19）、归档配置与实际执行配置不一致（#22）。退出码沿用 0 干净 / 3 仅已知项 / 1 有新问题。

---

## 2026-09-14 复现核对：#2 / #5 / #9 / #13 / #17

背景：用户质疑「这些是不是都由特定 cfg 触发、训练模板改过之后还能不能触发、当年是否误判」。
本轮在**当前代码 + 当前 Windows 核**上重跑了全部触发条件。夹具统一为
`docs/checktest/zero_initial_mass_test.cfg`（30 物种、初始质量全 0、`tag_init=1`、7 粒径段），
固定 `final_time_hours=1.0` 以便比较；对照组为 `gmd_paris_full`（非零初始质量）。

### 结论一览

| Bug | 现象是否仍可复现 | 判定 | 说明 |
|---|---|---|---|
| **#2** | ✅ **是** | 现象真实 | 零质量 + `with_coag=1` ⇒ `Nub Coag=0.0`（凝并一次未发生）。**对照组 `Nub Coag=-1.1069e14`、59 步**，证明仪器有效。性质（是否算缺陷）仍取决于"零质量是否合法输入" |
| **#5** | ✅ 现象成立，⚠️ **描述不符** | **需更正描述** | `COAG_TARGET_NEAREST` → ok/2 步/`Nub Coag=0`；`LEGACY` → **failed/0 步/`SIGSEGV` 段错误**。原文"Legacy 会算速率、Prototype 跳过"**未被复现证实** |
| **#9** | ✅ **是** | 现象真实，**归因已于 2026-09-20 更正** | Windows 核跑 56 行标准夹具：`Fortran runtime error: Bad real number in item 8 of list input`，0 步，与 2026-07 原始记录**逐字一致**。**但据此推断「Windows 核为修复前旧逻辑」方向错了**：Windows 核用的是**本体原逻辑**（`if(nucl_model.ne.5)` 条件读取，与 `/home/yifeihu/SCRAM1.1` 的读取语句序列一致），而这份 56 行夹具本身就不符合内核契约 ⇒ 缺陷在 py 写入器，不在内核。详见上方 **Bug #9** 章节 |
| **#13** | ✅ **是，数值逐位吻合** | 现象真实 | INT `final_number=4.12452e9` / EXT `final_number=0` —— 与台账记录的 `4.12452e9` / `0.0` **完全一致** |
| **#17** | ✅ 机制确认 | 已计入（`upstream`），但**当时漏收入致作者文档** | 排放窗口写在 `ModuleDiscretization.f90:1194-1198` 的 `if(nucl_model.eq.5)` 分支里 ⇒ **与 #9 共用同一个开关** |

### 关于"tutorial 模板改过还能不能触发"

**能，而且与本轮无关**：`c9b6310`（2026-07-27）把三个教学模板的基座从 `default`（零质量骨架）改成 `teaching`（非零初值），
这确实让"应用内点几下触发零质量"变成不可达。但**夹具 `docs/checktest/zero_initial_mass_*.cfg` 是独立存在的**，
直接跑夹具即可复现 ⇒ #2 / #13 的触发路径**从未消失**，只是从"GUI 默认流程"变成了"手工载入夹具"。
这也正是 #1 被转为"自动复核"的原因。

### #17 与 #9 的耦合（用户发现）

`ModuleDiscretization.f90:1194-1198`：

```fortran
    if(nucl_model.eq.5) then
    time_emis=60.d0*60.d0*12.d0      ! 43200 s
    else
    time_emis=2.64376d3              ! ≈ 44.06 min
    endif
```

**同一个 `nucl_model` 开关同时控制两件事**：cfg 里那三行的读/不读（#9 —— 内核侧是正确约定，缺陷在 py 写入器）与排放窗口（#17）。
更值得注意的是**同一常数还出现在另外两处且互相矛盾**：

| 位置 | 表达式 | 是否随 `nucl_model` 变 |
|---|---|---|
| `:1195` | 条件表达式（43200 / 2.64376e3） | ✅ 随 |
| `:1274` | `if(with_coag.eq.1.and.current_time.lt.2.64376d3)` | ❌ **恒为 2.64376e3** |
| `:1287` | `if (with_cond+tag_nucl.gt.0.and.current_time.lt.2.64376d3)` | ❌ **恒为 2.64376e3** |

⇒ 当 `nucl_model=5` 时，**排放跑满 43200 s，但步长限制的两个守卫在 2643.76 s 后就失效** ——
两处对同一物理量的界定不一致。这一点已补入《本体缺陷说明_致原作者.md》。

### 本轮踩到的两个实验设计坑（记录以备复用）

1. **在 EXTERNAL 臂上测 #2 无效** —— 该臂终态粒子数本就是 0（#13 的效果），两臂都 0 无法区分"凝并没生效"与"整体没运行"。**教训：选臂要先确认该臂的判据量本身非零。**
2. **用模板做对照会被 #19 静默覆盖** —— `ts.load_template("gmd_paris_full")` 自带 `case_preset`，脚本改的 `with_coag=0` 在 `prepare_run` 里被 `_with_case_preset` 改回 1，两臂自然相同。**教训：做开关对照必须清空 `case_preset`（夹具方式）或显式给 `explicit_keys`** —— 这条本身就是 Bug #19 的一次现场复现。
3. **最终采用直接仪器**：读核心自己打印的 `Nub Coag` / `Nub Nucl` / `Mass Cond` 计数，而不是靠终态推断"是否生效"。

证据：`install_logs/verify_bugs/verify_result.json`、`install_logs/verify_bugs_r2/result.json`、
`install_logs/verify_bugs_r3/result.json`；脚本 `install_logs/verify_bugs_{2_5_9_13,round2,round3}.py`。

### Bug #26: 内外混对比在 `tag_external=1` 的配置上被混淆

**说人话**：软件的核心功能是"同一份配置，跑内混和外混两遍，比数字"。但如果**你载入的配置里"初始粒子按外混放置"是勾着的**，那么这两遍就不只是"换了个算法" —— **连初始状态也被换了**。于是两边的差异到底来自"内混/外混"，还是来自"初始状态不同"，就分不清了。

| 项目 | 内容 |
|------|------|
| **位置** | `app/services/run_service.py` 的 `_with_mixing_assumption`：INTERNAL 分支 `tag_external = 0`（`:336`）；EXTERNAL 分支保留原值（`:349`）。调用点 `app/views/main_window.py:_start_runs`（比较运行时生成两臂） |
| **实测（2026-09-14，同一份配置做两臂变换后逐字段 diff）** | **出场模板**（`tag_external=0`）：两臂仅差 `n_frac`(1↔3)、`fraction_bounds`([0,1]↔[0,0.2,0.8,1.0]) ⇒ **对比干净，差异纯来自表示能力**<br>**用户载入的配置**（`zero_initial_mass_test.cfg`，`tag_external=1`）：两臂差 **3 项** —— `n_frac`(1↔3)、**`tag_external`(0↔1)**、`fraction_bounds`([0,1]↔[0,0.333,0.667,1.0]) ⇒ **对比被混淆** |
| **"内外"到底指什么（顺带澄清）** | 决定"内混还是外混"的是 **`n_frac`（质量分数分段数）**：`n_frac=1` ⇒ 组成维度不存在（每个粒径段只有一个平均组成）；`n_frac≥3` ⇒ 组成被切成多段。**`tag_external` 是另一个独立维度**，只控制"**初始**粒子怎么放"。所以"内混/外混"主体是**表示能力**，不是初始态 —— 而本 Bug 的问题正是代码在一个臂里顺手把初始态也改了 |
| **附带问题** | ① 用户在结构编辑页设的 `n_frac` 与 fraction 表在**两臂中都被静默改写**（与 #23 同类：用户不知道自己的表被覆盖了）；② 比较运行只归档**一份** `experiment_config.cfg`，而两臂实际各跑一份不同的 cfg ⇒ 归档既不等于内混那份、也不等于外混那份（#22 的对比场景特例，可复现性受影响） |
| **为什么值得注意** | 出厂模板的 `tag_external` 都是 0，所以**用模板做对比时看不出来**；一旦用户载入自带配置（或手动勾上"初始粒子按外混放置"），对比结论就不再纯粹 |
| **结论分类** | ⚠️ **行为事实 confirmed；"是否算缺陷"待定性**（2026-09-14 自我更正：原判 confirmed-bug 并建议"固定两臂一致"，但 `n_frac=1` 时 `tag_external=1` 语义上不可实现，故"强制为 0"可能是唯一自洽的选择，原建议**可能不可行**） |
| **标签** | `port`，但**不计入 gate**（待定性） |
| **下一步** | 待人工判断：a) 若"强制为 0"是唯一自洽选择 ⇒ 本项降级为**文档/界面提示问题**，只需在界面上说明"两臂差异包含初始态"；b) 若认为两臂应严格只差表示能力 ⇒ 需先确认 `n_frac=1` 下 `tag_external=1` 在本体里是否有意义（可问作者）。**注意**：把 EXTERNAL 臂也强制成 0 会破坏论文巴黎场景的口径（该场景正是"外混但初始内混"），不可取 |

### Bug #27: 案例名含非 ASCII 字符时，结果 CSV 编码不一致导致崩溃

**说人话**：核心程序会把这次运行的结果写成 CSV，其中"案例名"这一列取自我们传给它的环境变量。如果案例名里有中文，**核心会按中文系统的老编码（GBK）写，而我们读的时候按 UTF-8 读** —— 两边对不上，Python 直接抛异常崩溃，整个运行结果收集不了。

| 项目 | 内容 |
|------|------|
| **位置（写）** | 核心自带的结果写出：`SRC/ModuleCoeffRepartitionBoxmodel.f90:223` 与 `:1405`，把 `csv/timestep_summary.csv` 写到 `SCRAM_RESULTS_DIR` 下；其中 `testcase`/`process_combo` 两列来自环境变量 `SCRAM_TESTCASE`/`SCRAM_PROCESS_COMBO`（由 `run_service.prepare_run` 设为案例名） |
| **位置（读）** | `app/services/run_service.py:221`：`rows = list(csv.DictReader(timestep_path.open()))` —— 未指定 `encoding`，跟随进程默认编码（本环境 `PYTHONUTF8=1` ⇒ **UTF-8**） |
| **实测（2026-09-14）** | 案例名传 `"零质量 + NEAREST"` → `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc1 in position 289: invalid start byte`；出错字节 `\xc1\xe3\xd6\xca\xc1\xbf` 按 GBK 解正是"零质量"。**换 ASCII 标签后同一实验正常通过** |
| **触发面（重要）** | **GUI 默认流程踩不到** —— `main_window._start_runs` 的 `case_name` 取自案例预设下拉（全是 ASCII）。但**任何把非 ASCII 作为 `case_name` 传给 `prepare_run` 的调用都会崩**，例如我们自己的探测脚本（本轮就是这么撞上的）。⇒ 属"潜伏缺陷"，不是用户当前会遇到的错误 |
| **另一层未验证的隐患** | 结果目录用「实验名_案例预设」命名（`main_window.py:1095`），**用户如果把实验名写成中文，路径就含中文**；核心（Fortran）能否正确打开中文路径**尚未验证** —— 需要单独做一次实验 |
| **结论分类** | `confirmed-bug`（有崩溃复现 + 字节级证据） |
| **标签** | `port` |
| **下一步** | ① 读写 CSV 处统一显式 `encoding="utf-8"`（或读取用 `errors="replace"`，避免因单个坏字节丢掉整轮结果）；② 补一次"中文实验名 + 中文结果路径"的端到端实验，确认核心能否打开该路径；③ 若核心侧无法保证 UTF-8，则在 `prepare_run` 里对 `case_name` 做 ASCII 化（或改用与路径无关的短标识） |
| **本轮教训** | 我们的探测脚本用中文做案例标签，无意中撞出了这个缺陷 —— 之后探测脚本一律用 ASCII 标签，避免把工具自身的问题混进探测结论 |
