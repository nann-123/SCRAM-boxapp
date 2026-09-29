# 内核重编译记录（Linux，2026-09-29）

> 本文件是 **`docs/0929linux.md` 这次执行的实际记录**：怎么编的、编出来什么、验证结果、踩到的坑。
> 一次性结论在 §0；要照着重做只需 §2 的命令清单。
> 改动内容与理由见 `docs/0929check.md`，排查过程见 `docs/0929test.md`。

**结论：通过。** 主判定退出码 **0**，A1–A6 六条全部 PASS；其它路径零回归（T4/T6 逐位一致）。

---

## 0. 结论速览

| 项 | 结果 |
|---|---|
| 内核版本 | **1.2**（三项独有标记全命中），含 0929 三处初始化修复 |
| 提交 | 2026-09-29 本批**压缩为单笔提交**（父提交 `53ff85840d2c477bfc656425ffe6f0fea3ffd80c`）。执行过程中间曾出现三笔：`4210f9e…`（源码与文档）、`287629f…`（本次重建产物）、`c9bffbf…`（本文件的记录稿），最终压成单笔，**这些中间哈希不再可达**；最终哈希见 `git log --oneline -1` |
| 构建模式 | `safe`（与发布核同优化级别：`-O2 -fno-fast-math -ffp-contract=off -frounding-math`） |
| 产物 | `core/executables_or_wrappers/runtime/linux/ProgramSCRAM`，822920 B，md5 `796dfbbf50bd24685b9306d376538325` |
| 主判定 | `check_init_fix_linux.py --hours 1` → 退出码 **0**，A1/A2/A3/A4/A5/A6 全 PASS |
| 第二轮（18 倍档） | `--n-frac 5` → 退出码 **0**，T3/T1 = **1.0000000000**（改动前 18.0000） |
| A5 零回归 | T4、T6 在改前/改后两版核上 `report.txt` 与 `mass_init.txt` **逐位一致** |
| Git 发布 | 产物核 md5 `796dfbbf…` 已随本批单笔提交推到 `origin/main`（执行过程中先以 `287629f` 上过一版，随后压缩为单笔） |
| 零质量记录项 | T8/T9 都跑完（退出码 0），内外混终态一致；终态统计出现 `Nub Coag = NaN` / `n_emis = Infinity`（记录项，不参与判定，见 §7） |

---

## 1. 环境

| 组件 | 版本 | 备注 |
|---|---|---|
| gfortran | GNU Fortran (Debian 12.2.0-14+deb12u1) 12.2.0 | `sudo apt install gfortran` |
| gcc | 12.2.0（同上包版本） | `sudo apt install gcc` |
| NetCDF-Fortran | 4.5.4 | `libnetcdff-dev 4.6.0+really4.5.4+ds-3`；`/usr/include/netcdf.mod` 存在 |
| SCons | 项目 `.venv/bin/scons` | `build_runtime.sh` 自动优先用它；Python 3.11.3 |

`build_runtime.sh` 的四个前置检查（gfortran / gcc / nf-config / scons）在本机全部命中，无需额外安装。

---

## 2. 命令清单（可复现）

在仓库根目录执行：

```bash
# 0) 同步
git pull

# 1) 重编译 + 安装到共享运行时
bash scripts/linux/build_runtime.sh safe

# 2) 版本自检（应为 1.2）
python scripts/check_runtime_version.py

# 3) 主判定：生成 7 个配置 → 按 case 复制独立运行目录 → 跑核 → 核对 A1–A4、A6
python scripts/check_init_fix_linux.py --hours 1

# 4) 附 A5 零回归（改前 = 53ff858，做法见 §5）
python scripts/check_init_fix_linux.py --hours 1 \
       --pre /tmp/ProgramSCRAM.pre --post /tmp/ProgramSCRAM.post

# 5) 可选第二轮：18 倍那一档（建议换输出目录，别覆盖第一轮产物）
python scripts/check_init_fix_linux.py --hours 1 --n-frac 5 \
       --pre /tmp/ProgramSCRAM.pre --post /tmp/ProgramSCRAM.post \
       --cases-dir "$PWD/install_logs/20260929_init_cases_nfrac5" \
       --runs-dir  "$PWD/install_logs/20260929_runs_nfrac5"
```

### 踩到的坑：`--cases-dir` / `--runs-dir` 必须给**绝对路径**

脚本的 `run_case()` 用 `subprocess.run([str(exe), …], cwd=run_dir)` 启动核心，而 `exe = run_dir / "ProgramSCRAM"`。
若 `run_dir` 是相对路径，`str(exe)` 就是相对路径，再叠加 `cwd=run_dir` 后找不到文件：

```
FileNotFoundError: [Errno 2] No such file or directory:
'install_logs/20260929_runs_nfrac5/T1_nl5_nf1/ProgramSCRAM'
```

脚本默认值来自脚本自身位置、天然是绝对路径，所以只跑默认目录不会遇到；一旦自定义输出目录就要写 `$PWD/...`。

---

## 3. 重编译与版本自检

```bash
bash scripts/linux/build_runtime.sh safe     # 退出码 0，[Linking] ProgramSCRAM → 安装到 runtime/linux/
```

```
== 内核版本自检（判据：SCRAM1.2 独有字符串标记）==
  [OK ] staged (app 实际执行)      md5=a60700a97db1cc6f21d97fccbeb372f0
         标记命中：SCRAM_REDISTRIBUTION_MODE=2  MOVING_CENTER_DUALPIVOT=8  orphan mass=1
  [OK ] shared (仓库共享运行时)     md5=796dfbbf50bd24685b9306d376538325
         标记命中：SCRAM_REDISTRIBUTION_MODE=2  MOVING_CENTER_DUALPIVOT=8  orphan mass=1
  => 判定 1.2，与源码树一致，退出码 0
```

- **不需要**删 `~/.local/state/scram_boxapp_mixing/runtime/linux`（判据要求"仍显示旧版且角色是 staged"才删，本机不满足）。
- 但注意：版本自检只看 1.2 的字符串标记，**不能**区分"含不含 0929 修复"——详见 §9 第 2 条。
- **构建可复现**：同一份源码在本机两次构建 md5 完全相同；改动前源码（`53ff858`）构建出的 md5 `a60700a9…` 与 9 月 20 日暂存副本的 md5 一致。因此 §5 的"改前/改后"两版核可以放心用 md5 互相辨认。

---

## 4. 主判定：7 个 case 的初始总质量

生成器默认 12 h，冒烟用 `--hours 1`（初值口径与时长无关）。下表为实测（`RESULT/report.txt` 的 `initial total mass`，17 位有效数字）：

| case | 初始总质量 | 退出码 | 改动前参照 |
|---|---|---|---|
| `T1_nl5_nf1` | `37.679073599845388` | 0 | `37.679073599845388`（内混基准臂） |
| `T2_nl5_ext_tagext0` | `37.679073599845388` | 0 | `228.81807486240999`（叠加了配置逐档质量） |
| `T3_nl5_ext_tagext1` | `37.679073599845388` | 0 | `226.07444159907240`（= 6 × T1） |
| `T4_nl1_ext_tagext1` | `21.583170063260344` | 0 | `21.583170063260344`（应不变） |
| `T5_nl1_ext_tagext0_ti0` | `18.728707753710463` | 0 | `14.464046851670814`（比 T7 少 4.26466） |
| `T6_nl1_ext_tagext0_ti1` | `21.583170063260344` | 0 | `21.583170063260344`（应不变） |
| `T7_nl1_nf1_ti0` | `18.728707753710463` | 0 | `18.728707753710463`（T5 的对照臂） |

7 个 case 的退出码**全部为 0**（脚本按设计只把 `T2`/`T3` 的退出码纳入 A4 判据，其余为观察记录）。

### A1–A6 逐条

| # | 判定 | 实测 detail |
|---|---|---|
| **A1** | PASS | T1 = T2 = T3 = `37.679073599845388`，最大相对差 **0**。改动前的 6.0000 倍与 T2 停机都消失 |
| **A2** | PASS | T2、T3 对 T1 逐粒径档比较，7 档全部一致（最大相对差 0） |
| **A3** | PASS | 物种 2（黑碳）与物种 4（硫酸盐）三臂均为 `18.839536799922694`，恰为总量的 1/2（比值 0.500000） |
| **A4** | PASS | 7 份 `run.log` 中 `SCRAM1.2:`/`ERROR STOP`/`orphan`/`nonfinite`/`NaN`/段错误等模式 **0 命中**；T2、T3 退出码 0 |
| **A5** | PASS | T4、T6 在改前/改后两版核上逐位一致（见 §5） |
| **A6** | PASS | T5 = T7 = `18.728707753710463`，差 **0**（改动前 T5 少 4.26466） |

> 取数说明：`report.txt` 里有**两张**同类物种表（表头在 `N_groups=…` 之后的是**初始态**，`Total run time:` 之后的是**终态**）。
> 初始态每行 5 个数字字段（含 `gas_emision_rate`），终态行只有 4 个；判定脚本按"整行 5 个数字字段"筛选，因此取到的是**初始态**——这正是 A1–A3、A6 想要的量。
> 人工核对时不要用 `awk '$1==2||$1==4'` 这种宽松选择器，它会同时命中终态表里第 1 列恰好是 2 或 4 的其它行。

---

## 5. A5 零回归：改前/改后两版核怎么比

改动只涉及一个源文件；`SConstruct` 的 diff 仅新增 opt-in 的 `mode=poison`，`safe` 的优化参数逐字未变，所以只需换回那一个 `.f90`：

```bash
SRC=core/executables_or_wrappers/runtime/windows/source/SCRAM1.2/SRC/ModuleDiscretization.f90
PRE=53ff858     # 本轮改动前的最后一次提交 = 4210f9e 的父提交

cp "$SRC" /tmp/ModuleDiscretization.f90.fixed   # 存好改后版
git show "$PRE:$SRC" > "$SRC"                   # 临时换回改动前
bash scripts/linux/build_runtime.sh safe
cp core/executables_or_wrappers/runtime/linux/ProgramSCRAM /tmp/ProgramSCRAM.pre

cp /tmp/ModuleDiscretization.f90.fixed "$SRC"   # 换回改后版
bash scripts/linux/build_runtime.sh safe
cp core/executables_or_wrappers/runtime/linux/ProgramSCRAM /tmp/ProgramSCRAM.post

# 校验已逐位还原（本次实测两边一致，且 git status 对源码树为空）
sha256sum "$SRC"    # 6cfedc4df4c521d49cfa3ef1184dcc8bebe93482ca056444a586cf7dff51caea
```

| 二进制 | 来源 | md5 |
|---|---|---|
| `/tmp/ProgramSCRAM.pre` | `53ff858` 的 `ModuleDiscretization.f90` | `a60700a97db1cc6f21d97fccbeb372f0` |
| `/tmp/ProgramSCRAM.post` | `4210f9e`（= 当前 HEAD） | `796dfbbf50bd24685b9306d376538325` |
| `runtime/linux/ProgramSCRAM` | 同上，最终留存的就是它 | `796dfbbf50bd24685b9306d376538325` |

结果：`T4_nl1_ext_tagext1` 与 `T6_nl1_ext_tagext0_ti1` 在两版核上 `total_mass` 均为 `21.583170063260344`，`mass_init.txt` 逐档列表完全相等 ⇒ 被改的那段代码确实**没有**走到这两条路上。

> 细节：`result.json` 里 `T4__pre`/`T4__post`/`T6__pre`/`T6__post` 的 `exit_code` 是 `null`——脚本的 `run_case()` 只在主流程里回填退出码，A5 的追加跑没有采集。不影响 A5 判据（只比数值），需要退出码时可看对应运行目录的 `run.log`。

---

## 6. 第二轮：18 倍那一档（`--n-frac 5`）

| 项 | 实测 |
|---|---|
| 退出码 | 0（A1–A6 同样全 PASS） |
| T1 = T2 = T3 | `37.679073599845388` |
| **T3/T1** | **1.0000000000**（改动前 18.0000） |
| 黑碳 / 硫酸盐 | `18.839536799922694` / `18.839536799922694` = 总量的一半 |

`nl=1` 的四个 case（T4–T7）在两档（`n-frac` 3 与 5）下总量完全相同——它们的初值来自配置文件的逐档质量，不随组成档段数变化，符合预期。

---

## 7. 零质量记录项（T8/T9，可选，不参与判定）

`docs/0929linux.md` §5 末的可选记录项，用来把台账"零质量 + 凝并空转、内外混终态粒子数差 4 个数量级"（旧核记录）
换成一条 1.2 核下的记录 —— 因为 `BUG_TRACKING.md` 的 #2/#5/#13 三项正挂着"待 1.2 复验"。

命令（独立输出目录，避免覆盖主判定产物）：

```bash
python scripts/check_init_fix_linux.py --hours 1 --zero-mass \
       --cases-dir "$PWD/install_logs/20260929_init_cases_zeromass" \
       --runs-dir  "$PWD/install_logs/20260929_runs_zeromass"
```

配置口径：`Tag_init=1`、逐档质量全 0、逐档粒子数非 0、`tagrho=0`（`tagrho=1` 时全零质量会在平均密度里除零得到 NaN，属另一个问题）。
实测行为（**跑完 / 报 orphan / 报 nonfinite 都算有效结论**）：

| 项 | `T8_zero_mass_int` | `T9_zero_mass_ext` |
|---|---|---|
| 退出码 | 0（跑完 1 h） | 0 |
| 初始总质量 | 0（与配置一致） | 0 |
| 核内不变量体检 | 未报 orphan / nonfinite | 同左 |
| 终态控制台统计 | `Nub Coag = NaN`、`n_emis = Infinity`（`Mass Cond`、`m_emis` 有限） | 同左 |
| 终态物种表 / 逐档文件 | 有限数 | 有限数 |
| 终态质量总和 / 粒子数总和 | `6.9940237542788379` / `584333081077912.75` | **与左列逐位相同** |

结论：**内混与外混两臂的终态一致**，旧核"内外混终态粒子数差 4 个数量级"的现象**未复现**；1.2 既不拒绝也不报错，
代价是终态统计里出现 NaN/Infinity。注意零质量输入下排放仍在注入质量（`m_emis = 2.8989`），所以终态总量不为 0。
明细：`install_logs/20260929_runs_zeromass/result.json`（脚本里 A7 为记录项，`ok` 恒为 true）。

---

## 8. 产物与路径

| 内容 | 路径 |
|---|---|
| 判定明细（主） | `install_logs/20260929_runs/result.json`（含 A1–A6；同目录 `result_primary_before_a5.json` 是未附 A5 时的第一轮结果） |
| 判定明细（第二轮） | `install_logs/20260929_runs_nfrac5/result.json` |
| 判定明细（零质量记录项） | `install_logs/20260929_runs_zeromass/result.json` |
| 逐 case 记录 | `install_logs/20260929_runs/<case>/{run.log, RESULT/report.txt, RESULT/mass_init.txt, RESULT/number_init.txt}` |
| 配置矩阵 | `install_logs/20260929_init_cases/*.cfg`（第二轮 `…_nfrac5/`），可用 `make_init_test_cases.py` 随时重生成 |
| 产物核 | `core/executables_or_wrappers/runtime/linux/ProgramSCRAM` |

可复现性旁证：**同为 `n-frac 3` 的两轮（§2 的第 3 步与第 4 步，各自跑了全部 7 个 case）数字逐位相同**；
另外第二轮（`n-frac 5`）中 `nl=1` 的四个 case 与第一轮也完全相同（原因见 §6），`nl=5` 三臂的总量亦相同。

---

## 9. 观察项（不参与判定，供台账）

1. **`T7` 本次没有异常退出**：退出码 0，正常跑完。`docs/0929linux.md` 记录的是"旧核上初始化后异常退出"，本机在 1.2 修复版上看不到该现象。它的 Nub Nucl/Coag 仍是 ±1.38e14 的巨量近抵消，但同样量级也出现在 T4/T5/T6，而 T4/T6 与改前**逐位一致** ⇒ 属 `baseline12h.cfg` 这条 `nl=1` 全过程的既有行为，与本次三处改动无关。
2. **GUI 暂存副本仍是改动前的构建**：`~/.local/state/scram_boxapp_mixing/runtime/linux/ProgramSCRAM` 的 md5 是 `a60700a9…`，与 §5 编出的 **pre** 二进制完全相同（mtime 仍为 9-20 16:14）。版本自检看不出这一层——1.2 的字符串标记在 0929 修复之前就已存在，所以它对 staged 也报 `1.2`。按 `docs/0929linux.md` §2 的条件（"仍显示旧版且角色是 staged"）本次**未删除**；构建脚本说明 GUI 检测到共享运行时变化会自动重新暂存。若需强制刷新：`rm -rf ~/.local/state/scram_boxapp_mixing/runtime/linux`。
3. `T1`–`T3` 是"官方雾霾模板 × 三个混合臂"（298 K / 101325 Pa / RH 0.7、仅冷凝）⇒ `Mass Cond` 非零、`Nub Nucl/Coag` 为 0，与配置一致。

---

## 10. 约束与洁净度

- 未修改任何源码、配置、判据；未调参、未改容差。
- 收尾时 `git status` 被跟踪的改动只有一项：`M core/executables_or_wrappers/runtime/linux/ProgramSCRAM`（本次重建的产物，属预期）；
  源码树 `git diff HEAD` 为空。该产物已单独提交为 `287629f`（`tmp:` 前缀，待压成单笔）并推到 `origin/main`，推送后工作区即回到干净。
- §5 临时换回改前源码后，已用 sha256 与 `git status` 双重确认逐位还原。
- 没有在 `core/executables_or_wrappers/runtime/linux/` 里直接跑核心（判定脚本逐个 `copytree` 到 `install_logs/…/<case>/` 再跑）。
- 未触碰 `runtime/windows/**`。
- 未构建 `mode=poison`（`docs/0929linux.md` §7 为可选诊断，本次不需要）。

---

## 11. 后续（Windows 侧）

按 `docs/0929linux.md` §9：

1. Windows 侧重编译发布核（步骤见 `docs/windows_devkit_readme_zh.md` §9），用 `ProgramSCRAM.exe` 覆盖 `runtime/windows/`。
2. `python scripts/check_runtime_version.py`（期望 1.2）与 `python scripts/run_standard_tests.py` 收口。
3. **1.2 生效后 1.1 时代的数值基线全部作废，需要重采。**

---

## 12. 交叉核对（Windows 侧补记，2026-09-29）

在 Windows 开发机上对本记录的物证做了独立核对：**全部对得上**，两项口径写清如下。

| 核对项 | 结果 |
|---|---|
| 提交号 | 核对当时 HEAD = `4210f9e27a18da66f93cd98991fe442d4cbe7774`、父提交 `53ff85840d2c477bfc656425ffe6f0fea3ffd80c` ✅ 与 `git rev-parse` 一致（其后本批压缩为单笔提交，见 §0） |
| §5 源码 sha256 | ✅ 一致，但该值**依赖行尾**：仓库 blob（LF 存储）= `6cfedc4d…`；Windows 工作区检出为 CRLF，同一文件为 `daafba6a…`。这类校验建议用 `git hash-object <file>`（与行尾无关）。已用它反证：**Linux 侧工作文件与提交的 blob 逐字节相同**，§5 的"逐位还原"成立 |
| §3 版本自检 | ✅ 判据与结论一致（staged 仍是改前构建、shared 是 `796dfbbf…`）；"字符串标记分不出含不含 0929 修复"这一提醒准确 |
| §8 产物 md5 | ✅ 核对时本机 `runtime/linux/ProgramSCRAM` 仍是 `a60700a9…`（改前版），说明该产物当时只存在于 Linux 机器的工作区；现已随本批单笔提交进入仓库 |

### 还差一步才算完全落地

1. ~~把重建的二进制提交上去~~ —— **已完成**：本批单笔提交已含 md5 `796dfbbf…` 的 Linux 核。
2. **让 GUI 用上新核**：暂存副本（`~/.local/state/scram_boxapp_mixing/runtime/linux/ProgramSCRAM`）若仍是改前的
   `a60700a9…`，按 §9 第 2 条的说明由 GUI 自动重新暂存；不确定时直接
   `rm -rf ~/.local/state/scram_boxapp_mixing/runtime/linux`，启动后确认该文件 md5 变成 `796dfbbf…`。

### 顺带修掉的三处（与判定无关）

- `docs/0929linux.md` §5 的 A3 取数命令原写作 `awk '$1==2||$1==4'`，正是本文 §4 指出会被终态表误命中的选择器 ——
  已改为 `NF==5 && $1 ~ /^[0-9]+$/`，并把"两张物种表"的提醒写进该文档。
- 判定脚本的 `run_case()` 已把 `--cases-dir/--runs-dir/--runtime-dir` 统一解析为绝对路径 ⇒ 本文 §2 的
  `$PWD/...` 绕法不再必要（仍可用）。
- A4 已收紧为"扫描全部参与判定 case 的 `run.log` + 除 `T7` 外退出码均为 0"；本次实测本就全 0、日志无命中，
  故 §4 的判定结论不变。
