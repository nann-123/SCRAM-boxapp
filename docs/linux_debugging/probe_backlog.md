# 探测任务池（Probe Backlog）

> 目的：**让 agent 发现新 Bug，而不是反复重跑同样的测试**。
> 背景：`docs/BUG_TRACKING.md` 里的 9 条 Bug 是人工探索发现的，不是跑测试跑出来的。
> 只做"跑标准测试 + 比对基线"的循环，天然发现不了它们——因为标准测试只覆盖参数空间里的
> **2 个格子**，而阈值内的一切（包括当前基线里已有的 1810 条 anomaly 标记）都被当成"正常"。
>
> 配套脚本：`scripts/linux/probe_cell.py`（跑一个格子并采集发现信号）、`scripts/linux/probe_suggest.py`（生成候选探测）。
> 关联文档：执行规范 `docs/linux_debugging/brief.md`；日常操作与调度 `docs/linux_debugging/runbook.md`；
> 总入口见仓库 `README.md` 的 "Development and debugging" 一节。

---

## 1. 为什么必须"探测"而不是"复测"

| 事实 | 数据 |
|---|---|
| 标准测试覆盖的参数格子 | `gmd_paris_full × core_conserv`（2 侧）+ 快速测试 `gmd_paris_coagulation`（2 侧） |
| 参数空间（第 3 节矩阵） | 7 模板 × 4 RDB 核心模式 × 2 混合假设 = **56 侧** |
| 基线里已知的"异常"数量 | anomaly 标记 1810 条（external 1232 / internal 578），属既有现象 |
| 结论 | 复测只能证明"已知格子没变坏"；**未覆盖的 52 侧才是 Bug 的藏身处** |

## 2. 九类探测器（从你自己的 10 条 Bug 反推出来的方法）

| # | 探测类 | 来源 Bug | 要看的信号 | 执行方式 |
|---|---|---|---|---|
| P1 | 守恒与有限性 | #4、#7 | 相对残差、`has_nan`/`has_inf`、日志 `IEEE_*` | `probe_cell.py` 自动采集 |
| P2 | 沉默失败（该活动却是 0） | #2 | `coag_event_rate_sum`、`mapping_calls_step`、`active_bins`、`active_pairs` 在开启凝并时是否为 0 | 读 `conservation_audit.csv` / `timestep_summary.csv` |
| P3 | 配置传递链三方一致 | #3 | 界面设定值 = 生成的 cfg 值 = `run.log` 实际值（时长、开关、密度模式） | 读 generated cfg + `run.log` 对照 |
| P4 | 退出码与日志交叉 | #8 | `status=ok` 但日志含 `non conservation`/`STOP`/`NaN` | `probe_cell.py` 自动采集 |
| P5 | 双实现差分 | #5 | 同一输入下 `legacy` 与 `core_conserv`（或 Prototype 与 Legacy）行为应一致；不一致即偏差来源 | 同格跑两遍 `--set redistribution_option=...`，比数值 |
| P6 | 双入口产物一致 | #6 | CLI 标准测试产物 vs GUI 单次运行产物（figures/csv 清单与数值）应等价 | 分别跑一次再比对清单 |
| P7 | 文档/声称 vs 实际 | #1、#4、模板差异表 | 模板声称的物种数/bin 数与实际 cfg；README 提到的命令是否存在；报告是否真生成 | 静态核对 + 首轮运行 |
| P8 | 配置最小化差分 | #9 | 从失败配置逐行/逐段删除，定位触发条件（如 56 行崩、53 行正常） | agent 手写变体，用 `probe_cell.py --set` 或直接改 cfg |
| P9 | **资产完整性** | #10 | 被文档引用的资产（截图、手册图、示例 CSV）是否可读、是否晚于其描述的代码 | **已可执行**：`python scripts/linux/check_assets.py [--render]`——覆盖三个资产目录，含过期、字体自检、引用完整、影像密度，以及**与新鲜渲染的对比**（后者抓到了启发式漏掉的图）；已接入 `auto_round.sh` 每轮（Phase 2.5 生成检查用截图 + Phase 3.5 检查）。首次运行即发现 #10（实际波及 24 张资产） |

**每轮至少执行 1 条 P1–P8 中的探测**，并在 `BUG_TRACKING.md` 记录结论。

## 3. 覆盖矩阵（agent 的取活地图）

轴：模板 × RDB 核心模式（`redistribution_option`）。每格需跑 internal + external 两侧。

| 模板 \ 核心模式 | legacy | core_conserv | core_nogrow | core_smallgrow |
|---|---|---|---|---|
| tutorial_minimal | ☐ | ☐ | ☐ | ☐ |
| gmd_hazy_condensation | ☐ | ☐ | ☐ | ☐ |
| gmd_hazy_coag_cond | ☐ | ✅ 已探（复现 Bug #7） | ☐ | ☐ |
| gmd_paris_emission_only | ✅ 已探（干净，数值命中手册场景 A） | ☐ | ☐ | ☐ |
| gmd_paris_coagulation | ☐ | ✅ 标准测试快速版 | ☐ | ☐ |
| gmd_paris_condensation | ☐ | ☐ | ☐ | ☐ |
| gmd_paris_full | ☐ | ✅ 标准测试完整版 | ☐ | ☐ |

图例：✅ 已探并留证 ／ ☐ 未探（待取活）。

扩展轴（矩阵跑完后按需加入）：`redistribution_method`（2 = Moving Diameter，6 = euler_coupled，见 Bug #7）、`nucl_model`（5 为硬编码验证模式，见 Bug #9）、过程开关组合、时长（0.25h / 0.5h / 12h）。

**取活规则**：每轮从矩阵里挑 **1–2 个空格子**，优先挑"与已知 Bug 相邻"的格子（例如 #7 涉及 `redistribution_method=6`，就把含冷凝 + 重分配的格子先跑掉）。

## 4. 每轮取证流程

```bash
# 1) 挑一个空格子（示例：condensation + core_nogrow）
.venv/bin/python scripts/linux/probe_cell.py --template gmd_paris_condensation \
    --case gmd_paris_condensation --set redistribution_option=core_nogrow

# 2) 读输出：status / wallclock / steps / mass / number / anomaly / 残差 / 日志关键字
#    产出在 install_logs/auto/probes/<格名>/probe.json
```

然后把结论按 BUG_TRACKING 的字段写进第 5 节台账：**位置、触发条件、表现、影响面、证据、修复方向、测试配置**。

**新 Bug 一经确认，立即转成回归资产**（否则只能靠反复探测）：

1. `docs/checktest/<bug>_test.cfg`（可复现）；
2. 修复后的 `docs/checktest/<bug>_fixed.cfg`（对照）；
3. `docs/BUG_TRACKING.md` 新增一行（严重性/类别/状态/证据）；
4. 若可脚本化，追加到 `scripts/linux/collect_metrics.py` 的判据里，使其成为常驻守护。

## 5. 反"假发现"门槛（不满足就不算发现）

- **必须给出最小复现**：能用 `probe_cell.py` 或一份 `docs/checktest/*.cfg` 复现；
- **必须区分"已知现象"与"新增异常"**：与基线（`install_logs/auto/latest/baseline.json`）比对，
  例如 anomaly 1810 条是基线既有，不是新 Bug；
- **必须给物理或逻辑依据**：为什么这个数值/行为是错的（守恒、量纲、单调性、与文档声称不符）；
- **不允许把"测试通过"当成"没有 Bug"**：未覆盖的格子只能说"未探"，不能写"已验证正确"。

## 7. 让"发现"不枯竭：四层来源 + 自动建议器

矩阵格子跑完后不能停。探测来源按四层递进，每层都能自己产生新假设：

| 层 | 来源 | 怎么产生 | 工具 |
|---|---|---|---|
| L1 | 覆盖矩阵空格子 | 模板 × 核心模式（28 格，见 §3） | `probe_suggest.py` 的 matrix 部分 |
| L2 | 与已知 Bug 相邻的变体 | 改触发参数（#7：method 6→2；#9：逐值扫 nucl_model；#2/#5：零质量/不均匀分布） | `probe_cell.py --set 字段=值` |
| L3 | **源码线索（自我发现的核心）** | 扫描源码可疑模式：`STOP` 语句（当前 **23 处**）、`nucl_model` 分支（**9 处**）、`TINYM` 类极小阈值（**17 处**）、无保护除法、Python 侧 `except` 静默分支 | `probe_suggest.py` 的 code 部分 |
| L4 | 失败反推 | 从 anomaly 分布、残差最大的时间步、双实现差分不一致处反推可疑代码路径 | agent 读 CSV + 源码，写新规则进 `CODE_SOURCES` |

**自动建议器**（每轮自动跑，产出写入轮次目录 `next_probes.md`）：

```bash
.venv/bin/python scripts/linux/probe_suggest.py            # 候选清单：假设/依据/实验设计/判定标准
.venv/bin/python scripts/linux/probe_suggest.py --matrix   # 只看覆盖矩阵状态
.venv/bin/python scripts/linux/probe_suggest.py --mark 'cell:gmd_paris_full|legacy' --status clean --note '数值一致'
```

台账 `docs/linux_debugging/probe_ledger.json` 是**机器可读**的（`cells` + `hypotheses`），建议器会自动排除做过的条目
——这就是"不机械重复"的机制：同样的格子不会被建议第二次，除非显式 `--force` 重探。

**反停滞规则**：

- 连续 3 轮无新发现 → 强制升级一层（L1 → L2 → L3 → L4）；
- L3 扫不出新线索（候选被清空）→ 扩充 `CODE_SOURCES` 模式库（例如加入 `write(*,*)`、
  单位换算常数、数组越界嫌疑、`implicit none` 缺失的文件）；
- 四层都无可做 → 在 `digest.md` 里明确写"**探测饱和**"，转入 brief §7 的 release gate 流程，
  而不是继续空跑同样的测试。

## 8. 台账（逐轮追加）

| 轮次 | 格子 | 探测器 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-09-10 | `gmd_paris_full × core_conserv` | P1/P4 | 干净（标准测试 8 项通过） | `install_logs/auto/20260910-1821/` |
| 2026-09-10 | `gmd_paris_coagulation × core_conserv` | P1/P4 | 干净（快速版通过） | 同上 `quick_test/` |
| 2026-09-10 | `gmd_hazy_coag_cond × core_conserv` | P1/P4 | **复现 Bug #7**（已知）：两侧 status=failed，日志 `non conservation` + `IEEE_DIVIDE_BY_ZERO`/`IEEE_INVALID`；anomaly 各 5 条 | `install_logs/auto/probes/gmd_hazy_coag_cond__gmd_hazy_coag_cond/probe.json` |
| 2026-09-10 | `gmd_paris_emission_only × legacy` | P1/P5 | 干净；数值 24.4820 / 3.4465e10 精确命中教学手册场景 A | `install_logs/auto/probes/gmd_paris_emission_only__...__redistribution_option-legacy/probe.json` |

**下一轮建议取活**：`gmd_paris_condensation × core_nogrow`、`gmd_paris_full × legacy`
（与 Bug #5 的双轨不一致直接相关），以及 `gmd_hazy_coag_cond × core_conserv` 把
`redistribution_method` 从 6 改成 2 验证 Bug #7 的临时规避方案是否真的有效。

## 9. 待 agent 执行的任务（不在探测矩阵内）

| ID | 任务 | 依据 | 验收 |
|---|---|---|---|
| T1 | 加固 `scripts/capture_screenshots.py`：生成前检查字体可用性（不满足直接失败并提示装字体）、`setFont` 改为带回退链（Windows: Microsoft YaHei UI → SimSun；Linux: Noto Sans CJK SC）、生成后自检（渲染已知文本，宽度等于缺字宽度即判方框） | Bug #10 修复方向 ①–③ | `python scripts/linux/check_assets.py` 不再报"字体/密度"告警；`--out` 生成的图文字可读 |
| T2 | 在有字体的 **Windows** 上按 devkit §7 重生成 `docs/screenshots/` 九张图，并替换手册引用 | Bug #10 修复方向 ④；Linux 字体与 Windows 不同，发布资产必须在 Windows 生成 | 目视 `main_zh.png` / `main_en.png` 文字正常；`check_assets.py` 无"过期/密度"告警 |
| T3 | 把 `check_assets.py` 发现的资产问题按 BUG_TRACKING 字段登记，并在修复后把判据保留在检查里（防回归） | 本文件 §4 取证流程 | 台账有记录；修复后 `check_assets.py` 转为 ok |
| T4 | 为手册资产补生成/同步脚本（`docs/user_manual_zh_assets/`、`docs/undergrad_lab_assets/` 目前靠人工拷贝），**在 §7 触发时**生成对比图 | Bug #10 修复方向 ⑤ | 触发时能产出与手册目录对应的新图；差异由人确认后再替换 |
