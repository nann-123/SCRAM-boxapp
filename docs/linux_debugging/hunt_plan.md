# 发现驱动的调试方案（把"定时重复"换成"验证假设"）

> 2026-09-11 制定。配套：`runbook.md`（怎么操作）、`probe_backlog.md`（探测池与覆盖矩阵）、`BUG_TRACKING.md`（缺陷台账）。
> 本文件回答一个问题：**怎么让自动化继续发现新 Bug，而不是每小时重复跑同一批格子。**
> 人的接口只有一处：本文件 §5 的队列（你只维护"假设与优先级"，机械活交给 agent）。

## 1. 为什么会空转（诊断）

1. **内容来源单一**：每轮从 `probe_suggest.py` 的候选池挑格子；池子 = 矩阵空格 + 固定源码规则。
   矩阵跑满后池子内容不再变化 → 反复跑同类格子。
2. **探测没有反证判据**：只记 clean/bug。"跑一遍没崩"不携带信息——无法区分"确实没问题"和"这个参数根本没生效"。
3. **缺负对照**：从不检验"这条代码路径到底有没有被执行"，而这正是 Bug #2/#5 那一类（开关已开却
   `coag_event_rate_sum=0`/`active_bins=0`）的表现。
4. **结论不回流**：产生结论的方法没有写回规则库/队列，下一轮从零开始想做什么。
5. 代价已经在 2026-09-11 兑现：**Bug #11**（Case Preset 在运行路径覆盖开关与时长）让一批 `--set` 探测
   实际"什么都没测到"，却被记为 clean。不修这个，再跑 100 轮也不会推进。

## 2. 四个机制（M1–M4）

### M1 假设队列（唯一入口，取代"从候选池随便挑"）
每条假设必须写清四件事，缺一不可：
`假设` / `反证判据`（什么结果算推翻）/ `最小实验`（一条命令）/ `期望信息增益`（验证或推翻，各自意味着什么）/ `判据可达性`（**该条件在本相位是否可能为真**——写 guard 或补丁前必须先证明，否则"结果与 stock 逐位相同"是必然，不构成反证）。
没有"反证判据"或不写可达性的条目不允许进队列——这正是现在空转的根源。

### M2 反证式探测：空转检测（**已实现**，`scripts/linux/noop_probe.py`）
判据：**关掉某个过程开关后，终态质量/数量必须改变**。
- 不变 ⇒ 该开关在本次配置下没起作用（沉默失败嫌疑）；
- 关掉后生成 cfg 里仍是 1 ⇒ 设置被丢弃（工具/应用缺陷，Bug #11 即此类）。
成本：秒级～1 分钟/格（无需重编译）。**这是当前性价比最高的机制**，直接针对 Bug #2/#5 的类别。

### M3 差分定位（把"哪里不对"缩小到"哪一步、哪一行"）
- 首个分歧步：从 `conservation_audit.csv`/`anomaly_flags.csv` 找第一处越界的时间步，再回看该步的 bin 分布；
- 双轨差分：同 case 下 `legacy` vs `core_*`，比较**逐时步**（现在只比终态）；
- 阈值扫描：把物理参数（RH、初始质量、dtmin）扫一遍，找行为跳变点，再与 L3 扫出的源码阈值
  （`TINYM` 类极小阈值、无保护除法）对齐——跳变点即嫌疑位置。
成本：分钟级；需要"逐时步紧凑摘要"（见 §4）。

### M4 不变量模糊测试（用性质而不是用例来抓 Bug）
随机生成**合法**配置（物种数/bin 数/粒径边界/时间步在 schema 约束内），断言性质：
质量守恒、数量非负、无 NaN/Inf、以及**"开关必须起作用"**（M2 的批量版）。
成本：单次秒级；一次跑 20 组即可覆盖大量参数组合。

## 3. 反停滞与调度（不再机械重复）

- **队列驱动**：每轮必须从队列取 1 项，记录"预测 → 结果 → 结论"，并把结论回流（更新队列；若是新的
  源码线索，写进 `probe_suggest.py` 的 `CODE_SOURCES`，让规则库变强）。
- **可视化停滞**：`digest.md` 每行增加"新增数"（`WARN（有新增）`/`WARN（仅已知项）`已实现）；
  连续 **8 轮无新增**且队列为空 → 正式宣布"**探测饱和**"，转 release-gate 模式（只做发布检查与
  Windows 交接），停止探测。
- **层级判定写死**：由脚本按"距上次 deep 的小时数"决定层级，不再由模型自行判断（2026-09-11 就出现过
  把 12 小时前才跑过的 deep 又判成 deep，导致拿 540 步结果跟 2 步结果比、凭空 5 条假警报）。
- **平台三个任务（建议）**：
  1. 哨兵：每 30 分钟，只跑守卫 + 生成候选（秒级，不构建）；
  2. 猎手：每 4 小时，读队列 → 干 1 项（M2/M3/M4 任一）→ 登记结论；
  3. 深轮：每天 1 次（固定时间），完整标准测试 + 流水线 + 1 项队列。
- **人的接口**：队列文件。你只做两件事——加"物理层面的假设"、排优先级；其余由 agent 完成并回报证据。

## 4. 支撑条件（先做的小改动）

1. `probe_cell.py` 保存**逐时步紧凑摘要**（每步 mass/number/最大 bin 占比，几百行 CSV），
   替代现在动辄数百 MB 的 `runs/`——M3 的"首个分歧步"需要它。
2. 变异二进制缓存目录 `install_logs/mutants/<tag>/ProgramSCRAM`（约 15 MB/个，限 5 个），
   供"源码级变异"（临时关掉某段代码看输出是否改变）复用；已验证在本机可行（复制源码树 → 打补丁 → scons）。
3. `digest.md` 增列"新增数/连续无新增计数"（前者已实现）。

## 5. 队列（种子，人工维护优先级）

| ID | 假设 | 反证判据 | 工具/成本 | 状态 |
|----|------|----------|-----------|------|
| Q-01 | 关闭凝并开关后结果不变 ⇒ 该过程未生效 | 终态质量或数量改变 | `noop_probe.py`（秒级） | ✅ 已做（2026-09-11 21:14 轮 Q-12）：noop_probe 关掉该开关后终态改变 → 生效 |
| Q-02 | 关闭冷凝/成核开关后结果不变 ⇒ 未生效 | 同上 | 同上 | 被 Bug #11 阻塞 |
| Q-03 | `redistribution_option`（legacy/core_*）在多模板下都不改变结果 ⇒ 该选项在 RDB 路径上是空转 | 至少一个模板下结果不同 | `probe_cell --set`（分钟级） | ✅ 已重探（2026-09-12，Bug #11 修复后）：gmd_paris_full（凝并开、540 步）四值 legacy/core_conserv/core_nogrow/core_smallgrow 终态**逐位相同**（EXT mass=33.751055266282556/INT mass=32.73376655624839），gmd_paris_condensation 与 gmd_hazy_coag_cond 亦同 → **反证判据未推翻，假设成立**：`redistribution_option` 是死控件。根因：app 经 env `SCRAM_RDB_CORE_CONSERV`/`_NAME` 传递（run_service.py:122-123），但 Fortran（ModuleCoeffRepartitionBoxmodel.f90）只读 `SCRAM_COEFF_REPARTITION_MODE`（=映射方案，另一控件），对 RDB 核心模式无读取，.cfg 亦无此字段。**新 Bug #12**；台账 `cell:gmd_paris_full|rdb_option_4way`→bug；夹具 `docs/checktest/redistribution_option_dead_{test,fixed}.cfg` + patch `proposals/bug12_rdb_core_mode_dead.patch` |
| Q-04 | `redistribution_method=2` 可规避 Bug #7（hazy 下不守恒） | method2 下 `status=ok` 且残差 ≤1e-6 | `probe_cell --set redistribution_method=2` | ✅ 已做（2026-09-12 00:25 轮）：gmd_hazy_coag_cond + method=2 双侧 status=ok，mass=0.000173701，residual=2.8e-22/0.0，has_nan=0/has_inf=0，anomaly=8/8 → 反证判据未推翻，method=2 规避 Bug #7（默认 method=6 euler_coupled 非守恒+IEEE_DIVIDE_BY_ZERO），无新 Bug；台账 cell:gmd_hazy_coag_cond\|method2=clean |
| Q-05 | Bug #7 的非守恒从**第 N 步**开始，且与某个数组同步 | 找到首个残差越界步并定位到变量 | M3（需 §4.1） | ✅ 已做（2026-09-12 12:xx 轮，M3 差分定位）：重跑 `probe_cell --template gmd_hazy_coag_cond --set redistribution_method=6`，首个非守恒步=**第 0 步（首步）**，且**仅总粒子数 N** 非守恒（1-N_new/N_old≈±5.4e-4，质量守恒），伴随 IEEE_DIVIDE_BY_ZERO（external 另 IEEE_INVALID_FLAG）。根因定位到 `SRC/rdb/euler_coupled.f90` 重分配算法对 `diam(k)`/`d(kloc(k))` 的**无保护除法**（AQ/CQ=1-(d(...)/diam(k))^3 等），bin 直径为 0 时除零→Inf/NaN→N_1_esp 负值→STOP。已出 patch `proposals/bug7_euler_coupled_divzero.patch`（循环顶部 diam(k)≤0 或 d(kloc(k))≤0 时 CYCLE，`git apply --check` 通过，未编译验证）。属已知 Bug #7 的定位，非新 Bug；台账 `gmd_hazy_coag_cond|method6_m3_step0`→done。反证判据（找到首步+变量）已满足。 |
| Q-06 | RH 0.99→0.999 存在行为跳变点，位置对应 `isofwd/isorev` 的极小阈值 | 扫描曲线无跳变 ⇒ 推翻 | 阈值扫描（分钟级） | ✅ 已做（2026-09-12 02:xx 轮）：RH 扫描 0.99/0.992/0.993/0.994/0.9945/0.9947/0.9949/0.99495/0.99497/0.99499/0.994999/0.995/0.999 → 在 RH=0.995 处出现 ~2.5% 质量跳变（EXT mass 35.1567→36.0418，num 恒 3.44653e10，steps=42）；0.994999 仍低支、0.995 起高支；跳变位置对应 isorropia regime 切换（isofwd.f DRNH42S4/DRLC 阈值），属物理行为非 Bug；反证判据「扫描曲线无跳变⇒推翻」被推翻（确有跳变），clean，无新 Bug；台账 cell:gmd_paris_condensation|humidity0.99/0.995/0.999=clean |
| Q-07 | 初始质量趋近 0 时存在静默跳过（质量守恒但过程不执行） | 质量守恒且**过程计数为 0** ⇒ 命中 | M4 + `probe_cell`（分钟级） | ✅ 已做（2026-09-12 10:11 轮）：`probe_cell --cfg docs/checktest/zero_initial_mass_test.cfg`（凝并/冷凝/成核全开、零质量骨架）→ **反证判据被推翻（命中）**：mass=0 守恒（residual=0）且过程计数全 0（INT active_bins=0 / coag_event_rate_sum=0 / mapping_calls_step=0，EXT 同）。属 Bug #1 已知零质量路径（应用内不可达，Q-13 已确认），非新 Bug；**附带发现**：EXT final_number=0.0 而 INT 保留初值 4.12452e9（两侧不对称，待人工确认是否预期）。台账 `Q-07|zero_mass_silent_skip|zero_initial_mass_test`→done |
| Q-08 | `nucl_model=5` 结果与其他模式不可比（硬编码路径） | 与其他模板终态无任何对应关系 | `probe_cell --cfg` 夹具复核 | 已复核（20260911-221431）：#9 修复后 56 行标准格式可运行（EXT mass=238.853，residual 9.8e-20），反证判据未推翻，clean；"与其他模板不可比"转人工（关联 Q-14） |
| Q-09 | `tutorial_minimal` 在 `base=default` 路径上仍会得到 mass=0（Bug #1 的残留路径） | 该路径下 mass≠0 ⇒ 推翻 | `probe_cell`/GUI 对照 | ✅ 已做（2026-09-12 13:13 轮）：直接跑 `core/defaults/default_config.cfg`（=base=default 骨架，与 zero_initial_mass_test.cfg 逐字节相同）→ EXT mass=0/num=0、INT mass=0/num=4.12452e9，status=ok、residual=0、无 NaN/Inf。**反证判据（mass≠0⇒推翻）未推翻**：该路径确实 mass=0。可达性：模板系统不可达（7 模板均 base=teaching/baseline），但 GUI 手动 Load Config（main_window.py:994-995，对话框根=core/）可加载该骨架 → 零质量路径**经手动加载可达**。属已知 Bug #1/Q-07 零质量路径，非新 Bug；collect_metrics 判据（mass=0→报警）已覆盖。台账 `cfg|default_config_skeleton`→done |
| Q-10 | `legacy` 与 `core_conserv` 的首个分歧步可定位到一个具体过程 | 找到首个分歧步 + 该步被改动的字段 | M3 双轨逐时步 | ✅ 已做（2026-09-12 14:16 轮，M3 双轨逐时步）：`gmd_paris_full` 下 `--set redistribution_option=legacy` vs `core_conserv` 逐时步差分 7 类 CSV：size_distribution_mass/number（3780 行）、mapping_events、coag_delta_mass/number、composition_diversity 全部**逐位相同**；conservation_audit 仅计时列 `mapping_build_time` 不同（EXT 539/540、INT 68/88 行，其余字段全同）。**反证判据（找到首个分歧步+被改字段）未满足 → 假设被推翻**：两模式无物理分歧步，与 Q-03 一致（redistribution_option 死控件，Bug #12）。**非新 Bug**，Q-10 关闭（clean）。台账 `cell:gmd_paris_full|q10_m3_legacy_vs_core_conserv`→clean |
| Q-11 | 随机 20 组合法配置全部满足守恒/非负/有限 | 任一组失败 ⇒ 命中 | M4（分钟级） | ✅ 已做（2026-09-12 07:xx 轮，seed=20260912）：`scripts/linux/fuzz_invariants.py --n 20` 随机 20 组合法配置（基座 gmd_paris_condensation，随机化 with_coag/cond/nucl、nucl_model 1-4、redistribution_method 1-5、redistribution_option 4 值、T/P/RH/dt/时长）：全部 status=ok，worst_rel_residual=0.0≤1e-6，has_nan=0，has_inf=0，final_mass/number 均有限且非负，steps 6-203。反证判据「任一组失败⇒命中」**未推翻** → 无新 Bug；台账 Q-11\|m4_fuzz\|gmd_paris_condensation\|n20\|seed20260912=clean；报告 install_logs/auto/fuzz_q11/fuzz_report.json |
| Q-12 | Bug #11 修复后 Q-01/Q-02 是否暴露新问题 | 修复后仍有一个开关"不起作用" ⇒ 新 Bug | `noop_probe.py` | ✅ 已做（2026-09-11 21:14 轮）：noop_probe gmd_paris_full 三开关（with_coag/cond/nucl）关掉后终态均改变且步数变化 → 开关真实生效，反证判据未推翻，无新 Bug；台账 noop\|gmd_paris_full\|with_coag,with_cond,with_nucl=clean |
| Q-13 | **Bug #1 复核（agent 权衡是否修）**：① 零质量骨架在当前应用中是否可达（已查：无模板用 default 基座 → 不可达）；② 当年切 teaching 基座留下的疑点（examples 物种为惰性 MD+BC，不适合冷凝验证、与 nucl_model=5 硬编码模式有出入）是否成立；③ 若需修，给出不破坏正常工况的提案 | 夹具跑出 `status=ok 且 final_total_mass == 0` ⇒ 症状仍可复现（需修）；对照夹具质量 > 0 且无其他异常 ⇒ 症状只由零初值引起 | `.venv/bin/python scripts/linux/probe_cell.py --cfg docs/checktest/zero_initial_mass_test.cfg`（对照 `..._fixed.cfg`）；判据已并入 `collect_metrics.py`（质量为 0 → 报警） | ✅ 已做（2026-09-11 21:14 轮）：test 夹具 EXT/INT mass=0 复现症状；fixed 夹具 mass=0.0005 正常 → 症状只由零初值引起；应用内模板自 c9b6310 起基座=teaching（非零），零质量路径不可达，反证判据未推翻。agent 结论：应用内无需修改，夹具对+collect_metrics 判据保留作回归资产；疑点②（teaching 物种惰性 MD+BC 不适合冷凝验证）转 Q-14 待人工确认 |
| Q-14 | `gmd_hazy_condensation` / `gmd_hazy_coag_cond` 用 teaching 基座（2 物种惰性 MD+BC）跑 GMD 验证是否仍符合论文场景 | 与手册/论文的物种与物性对不上 ⇒ 基座选择有误，需换回 baseline 或补物种 | 对照 `examples/configs/default_config.cfg` 与 baseline 物种表 + 两模板实测 | ✅ 证据已列（2026-09-12 15:19 轮，agent 只列证据）：teaching 基座（examples/configs/default_config.cfg，gmd_hazy_condensation/gmd_hazy_coag_cond 经 base=teaching 继承）仅 2 物种 Sulfate(init_gas=0.0005,emission=0)+BlackCarbon(init_gas=0,emission=0 完全惰性)，无持续冷凝源；论文 Zhu et al.2015 §3 要求恒定硫酸盐气相源 5.5µm³/cm³/12h；baseline(Greater Paris,30 物种)有真实冷凝气相 SO4/NH4/NO3。实测 gmd_hazy_condensation number=3.42B 不变→冷凝空转。反证判据「与手册/论文物种物性对不上⇒基座选择有误」被推翻(命中)：基座选择有误，需换回 baseline 或补物种。物理判断待人工 | 
| Q-15 | **Bug #7 patch 编译验证**：proposals/bug7_euler_coupled_divzero.patch（euler_coupled 循环顶部对 diam(k)<=0 .OR. d(kloc(k))<=0 做 CYCLE 保护）能否修复 method=6 非守恒 | 变异二进制（打 patch 重编译）跑 gmd_hazy_coag_cond + method=6 仍 status=failed / IEEE_DIVIDE_BY_ZERO / non conservation ⇒ patch 无效（假设被推翻） | 变异构建：cp -a 源码树→git apply --directory patch→FC=gfortran CC=gcc scons mode=safe→SCRAM_PROGRAMSCRAM=变异exe probe_cell --template gmd_hazy_coag_cond --set redistribution_method=6 | ❌ 假设被推翻（2026-09-12 16:2x 轮）：变异二进制 sha256=038d81c9…（≠stock f03b90aa…，euler_coupled.f90 已重编译，run.log 确认调用变异 exe）仍 status=failed、step0 IEEE_DIVIDE_BY_ZERO + non conservation du nombre total、1-N_new/N_old=5.4167e-4（与 stock 逐位相同）→ patch 无效。根因细化：guard 只查 diam(k)/d(kloc(k))，但除零实际来自 DQ=1-(d(kloc(k))/d(kloc(k)-1))^3 的 d(kloc(k)-1)=0（下边界 bin 直径为 0，未被 guard 覆盖）→ 需改 guard 同时检查 d(kloc(k)-1)（或 kloc(k)==1 分支的 dbound(1)）。patch 需重做，物理判断待人工 |
| Q-16 | **Bug #7 真实除零源定位**（Q-15 后续）：v1/v2/v3 guard 均无效（结果与 stock 逐位相同）⇒ 除零不在 euler_coupled.f90 的 DO k=1,ns 循环内；真实源在何处 | 找到具体文件:行 + 触发变量，且该处除零在 method=6 下确实发生（变异/插桩可复现） | 读 redist_euler.f90（EULER_COUPLED 调用前的 d_before/d_after 计算）+ isorropia/condensation 路径，定位 method=6 下首个 IEEE_DIVIDE_BY_ZERO 源 | ✅ **已答（2026-09-12 21:xx 人工复核）**：用 `-ffpe-trap=zero,invalid,overflow` 重编译（`/tmp/bug7_fpetrap/scram`，未动仓库运行时）后，首个浮点异常在 `ModuleThermodynamics.f90:264`（`log10(0)`，teaching 基座 `total_IH=0`），加保护后落在 `euler_coupled.f90:244`（`RQ(k)/Q(k)`，空 bin；`Q(k) .NE. 0D0` 写在第三个 `.AND.` 上，Fortran 不短路）。**并纠正 Q-05/Q-15 的框架**：让格子 failed 的不是除零，而是第 378-400 行的**重复交付**（累加器按 `kloc(k)` 索引、交付循环按源 bin 迭代；本相位 `kloc≡1` ⇒ 交出量 H 被加回两次，净增相对 H=5.3856838600407908e-4）。v1/v2/v3 的 guard 条件在本相位**恒假**（v2/v3 要求 `kloc(k)>1`）⇒ 逐位相同是必然，不是反证。证据：`install_logs/auto/bug7_fpetrap{,2,3,4,5}/`；修复 `proposals/bug7_double_add_v4.patch`（已按规则回退成提案，需人工落盘+Windows 侧重编译） ||
| Q-17 | **Bug #7 修复后的残留**：外混合仍有 `1-N_new/N_old=9.77e-6`（修前 5.4168e-4，降 55 倍；绝对丢 184 个粒子），内混合已精确守恒 | 修后在 `gmd_hazy_coag_cond + method=6` 下外混合 `non conservation` 完全消失 | 在 `euler_coupled.f90:378-400` 打印"边界 bin 的 hand-out 被丢弃"计数（`kloc(k)==1 且 grand==0`、`kloc(k)==ns 且 grand==1`，见第 380/391 行分支） | 若计数>0 且与残差量级吻合 ⇒ 确认为边界丢弃（设计使然 or 需回填边界 bin）；若为 0 ⇒ 另有残差源 |
| Q-18 | **teaching 基座下冷凝为何完全 no-op**（已常态化检测：`scripts/linux/template_audit.py`；产品侧处置待领域判断）：`gmd_hazy_condensation` 预设 `{with_coag:0, with_cond:1, 12h}`，实测跑满 43200s（2 步）后质量/数量/气相**逐位不变**、报告 `Mass Cond 0.000000` —— 不只是"无持续源"，连初始 5e-4 硫酸气相都不凝 | 找到抑制冷凝的字段/路径，或用 baseline 基座跑同模板时 `Mass Cond ≠ 0` | `probe_cell --template gmd_hazy_condensation` 与 `--template gmd_paris_condensation` 对照 `report.txt` 的 `Mass Cond`/`total_water`；再查 `ModuleCondensation` 的开关条件 | 前者 0、后者非 0 ⇒ 基座字段（物种/可凝性/`sulfate_computation`）抑制了冷凝，是可修缺陷；两者都 0 ⇒ 冷凝模块本身有问题 | ✅ **已解决（2026-09-12 22:3x）**：论文的恒定硫酸盐源本体就实现了，但硬编码在 `nucl_model=5` 分支（`ModuleDiscretization.f90:713-714`，`gas_emision_rate(ESO4)=2.29e-4 µg/m³/s`，注释 "specified for the validation test"），且只挂 `ESO4`（30 物种布局索引 4）⇒ teaching 基座接不到。把两个 hazy 模板改为 `base=baseline + nucl_model=5`（另去掉 4bin/n_frac 覆写，避免与 30 物种表错位）后：`Mass Cond` 由 0 → 2.919/1.388，模板体检 7/7 全绿。`|
| Q-19 | `redistribution_method=3/5` 的**粒子数暴增**（`gmd_paris_condensation + method=3` → 5.28349e12/6.15417e12，method=2 为 3.44565e10，**×153**；method=5 ×3）是设计使然还是缺陷 | 与 Zhu et al. 2015 对 euler_mass/hemen 的定义对照；若定义为"质量守恒、数量随直径重算"则可接受（记台账即可），否则按缺陷处理 | `probe_cell --template gmd_paris_condensation --set redistribution_method={2,3,4,5}` + 读 `conservation_audit.csv` 的数量列 | 数量变化有明确物理/算法解释 ⇒ 记 clean；无解释 ⇒ 新 Bug |
| Q-20 | **全关时发射记账残差**：`with_coag=with_cond=with_nucl=0` 时质量终态 = 初态+`m_emis` **逐位精确**，但数量终态比 初态+`n_emis` 少 ~1.2e-4（绝对值 ~2.5e6 个粒子） | 找到差异来源（`n_emis` 的打印口径 vs 发射积分的实现） | `probe_cell --template gmd_paris_condensation --set with_coag=0 --set with_cond=0 --set with_nucl=0`，比对 `report.txt` 的 `n_emis` 与 `timestep_summary.csv` 首末行 number | 差异是口径（如打印前做了 bin 重分配）⇒ 记 clean + 改口径；是积分/发射实现 ⇒ 缺陷 |
| Q-21 | `mapping_scheme` 配置标量是否真的送到核心（与 #12 同类的"控件没接上"） | 改成 `LEGACY` 后终端数值必须改变（或明确证明该模式下两者等价） | `probe_cell --template <t> --set mapping_scheme=LEGACY` 与默认对照，并 grep 生成的 cfg/env 与 `run.log` 的 `mapping_mode` | ✅ **已确认（2026-09-12 22:15 轮，夹具固化）**：`probe_cell gmd_paris_condensation` 默认 vs `--set mapping_scheme=LEGACY` 两臂终态**逐位相同**（EXT mass=33.0654 / INT mass=32.6176 / number=3.44653e10 / steps=42 / anomaly 124/213），两臂 `run.log` 的 `mapping_mode` 均=`COAG_TARGET_NEAREST`，生成 cfg 无 mapping 字段 ⇒ **反证判据「数值不变且 env 恒 COAG_TARGET_NEAREST」成立=死配置**，确认 **Bug #15**（与 #12 同类）。台账 `Q-21|mapping_scheme_env|app_to_core|contract`→bug；证据 `install_logs/auto/probes/q21_{default,legacy}/` |

> **2026-09-12 复核结案**：Q-15/Q-16/Q-17 属"上游缺陷 + 配置门控"（`euler_coupled.f90` 与本体逐字节一致；本体 exe 只改 cfg 第 7 行为 6 即复现）。产品侧处置 = 把 `gmd_hazy_coag_cond` 模板默认 method 6→2（已改，模板 failed→ok），因此这三条不再是产品待办；若要保留 method=6 演示，再走 `proposals/bug7_double_add_v4.patch`。Q-18 已由新的模板体检常规项覆盖，剩余为教学/物理判断。

## 6. 七项"重要但没被覆盖"的事项与处置

| # | 事项 | 处置 | 谁做 |
|---|------|------|------|
| 1 | 发布闸门被**记录**卡住（#1 疑似已消失未销账、#9 未修、每轮 WARN） | 判据改为"连续 7 轮**新增=0**"；#1 待你确认后销账（现按你的意思**保持 ❌ 不动**）；#9 提案已出（`proposals/`） | 你 + 我 |
| 2 | 25 轮过程记录只在本机（`install_logs` 不进 git 且被"只留 7 轮"清理） | 每周归档：把 `digest.md` + 当周关键 `summary.md` 复制进 `docs/linux_debugging/rounds/YYYY-Www.md` 随提交入库（可写成脚本，随每周复盘跑） | 我可以做 |
| 3 | "找 Bug 的引擎"停滞 | 本文件 §2–§5；优先把 M2（已实现）跑在 Bug #11 修复之后 | 你 + agent |
| 4 | Windows 侧零自动化 | 出一份《Windows 验收清单》并在 `validation_checklist.md` 记录结果；真正值得一键化的只有两条：① 重生成截图（§7）② 跑标准测试 8 项（§6） | 你（Windows） |
| 5 | P2 大坑（#2/#5/#7）没人碰 | 每个先出 patch 提案（#9 已示范：变异构建 + 实测证据）；#7 可先用 M3 定位首个非守恒步 | 我 + 你（物理判断） |
| 6 | 调度漂移（层级判定被模型估计错） | 层级判定写进脚本；平台固定三任务（哨兵/猎手/深轮），不再让模型自选 | 你（平台）+ 我（脚本） |
| 7 | 权限边界（agent 有 `rm -rf` 与改仓库文件的权限） | 守卫升级：`install_logs/` 之外的**删除**直接判硬失败；Runbook §1 提示词里写明"除 install_logs 外任何删除都算违规" | 我可以做 |
