# Linux Agent 操作手册（下达指令 · 次日复盘）

> 配套文档：执行规范见 `docs/linux_debugging/brief.md`（agent 的"法律"），本文件是
> "怎么用"（人类的操作手册）。所有命令都在仓库根目录
> `/home/yifeihu/SCRAMBoxApp-WinDevKit` 下执行。

---

## 1. 给 agent 的指令（可直接粘贴）

```text
你是 SCRAM BoxApp 的 Linux 调试 agent。工作目录：/home/yifeihu/SCRAMBoxApp-WinDevKit

【第一步】按顺序读这五份文件，它们是你的全部依据：
  1) docs/linux_debugging/brief.md   —— 执行规范：验收基线、每轮流程、禁止事项、已知坑
  2) docs/linux_debugging/hunt_plan.md —— **发现驱动方案（2026-09-11 新增）**：假设队列、四个机制、反停滞规则、七项处置
  3) docs/linux_debugging/probe_backlog.md             —— 探测任务池：覆盖矩阵、九类探测器、取活规则、台账
  4) docs/BUG_TRACKING.md              —— 本次要推进的未决 Bug 队列与证据要求
  5) docs/validation_checklist.md      —— 发布验收项（Windows 专有项不得由你勾选）

【每轮流程】
  1. 跑一轮回归：bash scripts/linux/auto_round.sh <quick|standard|deep>
     （quick=哨兵秒级；standard=增量构建+快速测试+指标；deep=再叠加完整标准测试与流水线。
      签名未变时 quick/standard 会自动跳过；等价于 brief 的 §4）
     **层级按规则定，不要自己估**：读 install_logs/auto/digest.md，找最后一行 deep →
     距今 ≥20 小时跑 deep，否则跑 standard。（2026-09-11 曾误判：距上次 deep 仅 12 小时又跑 deep，
     结果 540 步的深轮与 2 步的快速版基线对比，凭空 5 条假警报。）

  2. 【必须有】从**队列**取 1 项来做（不允许只重复跑标准测试，也不允许重复已登记的格子）：
     - 队列在 `docs/linux_debugging/hunt_plan.md` §5（Q-xx）。每条必须写清四件事：
       **假设 / 什么结果算推翻 / 一条最小实验 / 验证或推翻各意味着什么**——
       写不出"反证判据"的条目不许做（这是过去 25 轮空转的根因）。
     - 候选来源四层：L1 矩阵空格（**已探满，仅在新模板或代码变更时重开**）/ L2 已知 Bug 相邻变体 /
       L3 源码线索（STOP、nucl_model 分支、极小阈值、无保护除法、静默 except）/ L4 失败反推；
       **连续 3 轮无新发现必须升级一层**（probe_backlog §7）。
     - 两个首选机制（2026-09-11 新增，性价比最高）：
       · 空转检测：`.venv/bin/python scripts/linux/noop_probe.py --template <模板>`
         —— 判据"关掉过程开关后终态必须改变"，不变即该路径未生效（Bug #2/#5 那一类）；
       · 夹具复核：`.venv/bin/python scripts/linux/probe_cell.py --cfg docs/checktest/<夹具>.cfg`
         —— 跑原始 cfg（如 Bug #1 的 zero_initial_mass_{test,fixed}.cfg、Bug #9 的 nucl_model5_*.cfg）。
     - 执行/登记：`.venv/bin/python scripts/linux/probe_cell.py --template … [--set 字段=值]`；
       登记 `probe_suggest.py --mark '<id>' --status done|bug|clean --note '…'`
       （台账 `docs/linux_debugging/probe_ledger.json`，会阻止同一格被重复建议）。
     - 结论必须回流：更新 hunt_plan §5 该条的状态；若是新的源码线索，写进 probe_suggest 的 CODE_SOURCES。
     - 反停滞：**连续 8 轮"新增=0"且队列为空 → 在 digest 写"探测饱和"，转 release gate，不再空跑**。
     - 新 Bug 一经确认，立即转成回归资产：docs/checktest/<bug>_test.cfg（可复现）
       + <bug>_fixed.cfg（对照）+ BUG_TRACKING 新增一行 + 判据并入 metrics 脚本。

  3. 打开本轮 install_logs/auto/latest/summary.md，把其中 TODO 段补齐：
     - 未决 Bug 复现结论（BUG_TRACKING 里 ❌ 的条目：编号/仍复现或已消失/证据）
     - 指标异常项逐条解释
     - 待人工确认事项

  4. 核心算法（SRC/*.f90）的问题只产出 patch 到 proposals/，不要直接改

【三条触发规则（照 devkit §6/§7/§8，别弄混）】
  · §6 标准测试：每次改代码后都要做 → 每轮都跑（auto_round 已内置）
  · §7 截图/手册资产：只有改了 GUI（布局/按钮/文字/结果页）才需要 → auto_round 用
    git 时间戳判断（app/ 是否晚于 docs/screenshots/），未触发就跳过；生成一律写 --out 到
    轮次目录，**不要手动改 docs/screenshots/ 与 docs/*_assets/（那是发布资产，需在 Windows 生成）**
  · §8/§13 打包与开发包：只在发布时做，**Linux 侧不做、也不要尝试**
  · 每轮读 summary.md 的「资产完整性（P9）」段：有告警就按 BUG_TRACKING 字段登记并推进
    （当前已知：T1 加固截图脚本、T4 为手册资产补生成脚本；T2 需 Windows，只跟踪状态）

【硬约束】
  · 只 git add，不 commit、不 push、不 git reset --hard（人工每天统一提交一次，别攒成很多小提交）
  · **不删除 install_logs/ 之外的任何文件**（2026-09-11 起守卫会判硬失败）；体积纪律只清 install_logs/auto/
  · 不修改 core/executables_or_wrappers/runtime/windows/** 与两个 Windows 打包脚本
    （scripts/package_app_windows.ps1、scripts/make_windows_devkit.ps1）
  · 每轮结束必须跑 bash scripts/linux/check_windows_parity.sh；硬失败（exit 1）则本轮判 fail
  · 截图只能用 --out 写到 install_logs/，不得覆盖 docs/screenshots/
  · 不许放宽阈值、跳过 smoke 项或删改基线数值来"让测试通过"

【交付】
  填完 summary.md，并回报不超过 10 行：本轮结论 / 关键数值与基线差异 / Bug 状态变化 /
  需要我确认的事项。另须写明：**本轮队列项 ID 与"反证判据是否被推翻"**、台账登记情况；
  读 digest 时："WARN（仅已知项）"= 只有已登记老问题，"（有新增）"才需要你解释。
```

## 2. agent 去哪里读任务

| 文件 | 它提供什么 | agent 的使用方式 |
|---|---|---|
| `docs/linux_debugging/brief.md` | 执行规范（流程、基线、禁止事项、坑） | 每轮遵守；§5 定优先级 |
| `docs/linux_debugging/hunt_plan.md` | **发现驱动方案（2026-09-11）**：假设队列 Q-xx、四个机制（空转/差分/模糊/队列）、反停滞规则 | 每轮从 §5 队列取 1 项，做完回流状态 |
| `docs/linux_debugging/probe_backlog.md` | **探测任务池**：覆盖矩阵（28 格）、九类探测器、取活规则、台账 | 每轮挑 1–2 个未探格子执行并登记 |
| `docs/BUG_TRACKING.md` | 未决 Bug 队列（当前 #1 转自动复核、#9/#11 已修；P2 待定：#2、#5、#7），每条含位置/触发条件/证据/修复方向 | 逐条复现与推进 |
| `docs/checktest/*.cfg` | Bug 夹具（惯例：`*_test.cfg` 可复现 + `*_fixed.cfg` 对照） | 复现与回归 |
| `docs/validation_checklist.md` | 发布验收项 | 只读；仅出提案，不勾选 Windows 项 |
| `WINDOWS_DEVKIT_README_zh.md` §6 | 标准测试的两条命令与 8 项检查 | 原样执行 |
| `README.md`、`docs/gui_workflow.md` | 用户可见流程与产品边界 | 复现 GUI 流程时对照 |
| `docs/SCRAM_BoxApp_本科教学实验手册.md`、`docs/SCRAM_BoxApp_中文用户操作手册.md` | 数值与图形基线 | 对比时引用 |

## 3. 执行什么 / 修改什么

| 范围 | 允许 | 说明 |
|---|---|---|
| 运行 | `scripts/linux/auto_round.sh`、`scripts/linux/build_runtime.sh [debug]`、`scripts/run_standard_tests.py`、`scripts/run_pipeline.py`、`scripts/linux/collect_metrics.py`、`scripts/linux/check_windows_parity.sh` | 全部为只读代码 + 写 `install_logs/` |
| 直接修改并 `git add` | `docs/checktest/*.cfg`（新夹具）、`docs/BUG_TRACKING.md`（状态与证据）、`install_logs/auto/**`（报告与产物，已被 gitignore） | 这是 agent 的常规产出 |
| 只出提案（`proposals/`，人工审核后应用） | `SRC/*.f90` 等核心算法改动、`pyproject.toml` 版本号、`validation_checklist.md` 勾选 | 涉及物理/发布判断 |
| 绝对禁止 | `core/executables_or_wrappers/runtime/windows/**`、两个 Windows 打包脚本、`git commit/push/reset --hard`、覆盖 `docs/screenshots/` | 见 brief §8/§9 |

## 4. 预计得到什么

每轮一个目录（`bash scripts/linux/auto_round.sh` 自动创建）：

```text
install_logs/auto/<YYYYmmdd-HHMM>/
  git.txt              本轮起点：commit、工作区状态、改动清单
  windows_parity.txt   Windows 口径守卫输出（硬失败会导致本轮 fail）
  build.log            核心构建日志（含 md5，应与上一轮一致）
  standard_tests/      标准测试全部产物 + standard_tests.log（五项 smoke）
  quick_test/          快速版产物 + quick_test.log
  pipeline/            端到端流水线产物 + pipeline.log
  metrics.log          指标采集与对比（含手册参考偏差）
  baseline.json        本轮关键数值，供下一轮对比
  summary.md           人读报告：数值已自动填好，TODO 段由 agent 补结论
```

`install_logs/auto/latest` 始终指向最近一轮，方便直接打开。

## 5. 第二天怎么复盘（5 条命令）

```bash
cd /home/yifeihu/SCRAMBoxApp-WinDevKit
ls -t install_logs/auto/ | head -5          # ① 昨晚跑了几轮
bash scripts/linux/check_windows_parity.sh        # ② 先看 Windows 口径有没有被碰
git status --short                          # ③ agent 暂存/新增了什么
git diff --cached --stat                    # ④ 概览；细看用 git diff --cached
cat install_logs/auto/latest/summary.md     # ⑤ 读结论、数值、待确认项
```

处理对照表：

| 你看到的 | 你的动作 |
|---|---|
| summary 为 PASS，且只动了 `install_logs/`（gitignore，不进 git） | 无需动作 |
| 有 `docs/checktest/*.cfg`、`docs/BUG_TRACKING.md` 等被 `git add` | `git diff --cached` 审阅；满意则自己 commit（粒度你定），不满意 `git restore --staged <path>` + `git checkout -- <path>` |
| 守卫输出 **HARD FAIL** | 按 `windows_parity.txt` 指出的项回退（通常是 Windows 运行时或源码分支被动） |
| `proposals/` 里有 patch | `git apply --check` 试应用，人工判断物理合理性后再决定是否 `git apply` |
| summary 为 FAIL / 有 HARD 行 | 看 `metrics.log` 的 HARD 行 + `standard_tests.log`；本轮结论不可用于发布判断 |
| 数值与基线偏差被标记 WARN | 结合 `baseline.json` 与上一轮 `latest/baseline.json` 判断是环境波动还是真回归 |

## 6. 定时调度怎么设计（三层 + 签名跳过）

| 层 | 建议频率 | 做什么 | 目的 |
|---|---|---|---|
| `quick` | 每 15–30 分钟 | 只跑 Windows 口径守卫 + 生成候选探测清单；**不构建、不跑测试** | 哨兵：发现工作区/口径被改坏 |
| `standard` | 每小时 | 守卫 + 增量构建 + 快速标准测试 + 指标对比（§7 触发时另生成截图对比） | 日常回归 |
| `deep` | 每晚 | 再叠加完整标准测试 + 端到端流水线 + 结果图另存；agent 再执行 1–3 条探测并补写报告 | 出验收结论、供次日复盘 |

```bash
bash scripts/linux/auto_round.sh quick               # 哨兵层（秒级）
bash scripts/linux/auto_round.sh standard            # 常规回归层
bash scripts/linux/auto_round.sh deep                # 深度层（建议每晚）
bash scripts/linux/auto_round.sh standard --force    # 无视签名强制重跑
```

**签名跳过（防机械重复的核心）**：签名 = `commit + 核心二进制 md5 + 工作区状态哈希`。
签名与上一轮相同时，`quick`/`standard` 直接跳过并只追加一行 digest；`deep` 不受限制（它要出结论）。
所以"代码没变"时不会反复跑同样的测试，只有内容变化才触发重跑。

**累计摘要**：`install_logs/auto/digest.md` 每轮追加一行（时间 / 层 / 结论 / 守卫 / 构建），
早上先看这一个文件。**读数约定（2026-09-11 起）**：

- 结论栏带标注：`WARN（仅已知项）`= 只有已登记的已知问题（如 Bug #10 截图待 Windows 重生成）；
  `WARN（有新增）`= 本轮出现了新告警——**只需关注后者**。
- 资产检查退码：`0`=干净 `3`=仅已知项 `1`=有新增 `2`=硬失败。
- 指标对比只做**同案例**比较（案例名不一致时 `metrics.log` 会打印 `INFO …未做「与上一轮 ≤1%」判定`，
  不再静默跳过，也不会拿别的案例当基线报假警）。
- deep 轮的基线另存一份 `install_logs/auto/deep_baseline.json`，不受"只留最近 7 轮"清理影响，
  供下一轮 deep 做同层级自比。

**agent 平台侧怎么配**（在平台里，不在仓库里）：

1. 用平台定时能力建三个任务，分别指向上面三条命令；
2. 每轮之后要求它：读 `install_logs/auto/<最新>/next_probes.md` → 挑 1–3 条执行 →
   `probe_suggest.py --mark` 登记 → 补写 `summary.md` 的 TODO 段；
3. 某轮 FAIL 时**保留现场**（不要清理该轮目录），把 `metrics.log` 的 HARD 行原样贴进摘要。

**你只需要在这三处介入**：

| 频率 | 动作 |
|---|---|
| 每天 | 看 `digest.md` + `install_logs/auto/latest/summary.md`（约 5 分钟） |
| 每周 | 审 `docs/linux_debugging/probe_ledger.json` 的结论：哪些升格进 `BUG_TRACKING.md`、哪些要改文档或模板 |
| 发布前 | 按 brief §7 的 release gate；Windows 侧验证与打包在 Windows 上完成 |

**反停滞**：连续 3 轮无新发现时，agent 必须按 `docs/linux_debugging/probe_backlog.md` §7 升级探测层
（L1 矩阵 → L2 变体 → L3 源码线索 → L4 失败反推）；四层都无可做时写明"**探测饱和**"并转入
release gate，不允许继续空跑同样的测试。

## 7. 一页速查

| 想做的事 | 命令 |
|---|---|
| 跑一层轮次（哨兵/回归/深度） | `bash scripts/linux/auto_round.sh quick｜standard｜deep` |
| 深度调试核心（带边界检查） | `bash scripts/linux/auto_round.sh deep debug` |
| 强制重跑（忽略签名） | `bash scripts/linux/auto_round.sh standard --force` |
| 检查 Windows 口径 | `bash scripts/linux/check_windows_parity.sh` |
| **探测一个格子**（发现新 Bug） | `.venv/bin/python scripts/linux/probe_cell.py --template <模板> --case <预设> [--set 字段=值]` |
| **空转检测**（开关是否真生效） | `.venv/bin/python scripts/linux/noop_probe.py --template <模板>` |
| **跑一个夹具 cfg**（Bug #1/#9 这类） | `.venv/bin/python scripts/linux/probe_cell.py --cfg docs/checktest/<夹具>.cfg` |
| 看假设队列 / 发现方案 | `docs/linux_debugging/hunt_plan.md`（§5 队列 Q-xx，做完改状态） |
| **生成候选探测**（自我发现） | `.venv/bin/python scripts/linux/probe_suggest.py [--matrix] [--limit 8]` |
| 登记探测结论 | `.venv/bin/python scripts/linux/probe_suggest.py --mark '<id>' --status done\|bug\|clean --note '…'` |
| 重建并安装 Linux 核心 | `bash scripts/linux/build_runtime.sh` |
| 单独跑标准测试 | `.venv/bin/python scripts/run_standard_tests.py --template gmd_paris_full --case gmd_paris_full --output-root install_logs/standard_tests` |
| 生成检查用截图 | `.venv/bin/python scripts/capture_screenshots.py --out install_logs/shots` |
| 采集/对比指标 | `.venv/bin/python scripts/linux/collect_metrics.py --round-dir install_logs/auto/<时间戳>` |
| 启动 GUI | `.venv/bin/python scripts/launch_app.py` |
