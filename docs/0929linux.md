# Linux 平台工作清单（2026-09-29）

> **本文件只写"在 Linux 机器上要做什么"**：怎么重编译、跑哪些实验、验证什么、怎么记录。
> 改动内容与理由见 `docs/0929check.md`；本次的排查过程见 `docs/0929test.md`。
> **一句话目标**：把内核改动（`source/SCRAM1.2` 三处）编译出来，用 7 个配置验证
> "论文验证模式多列初始态的初值口径"已正确、且其它路径零回归。

---

## 1. 环境依赖

- `gfortran`、`gcc`、NetCDF-Fortran：`sudo apt install gfortran gcc libnetcdff-dev`
- SCons 与 Python 依赖：用项目根的 `.venv`（`scripts/linux/build_runtime.sh` 会自动找 `.venv/bin/scons`）

## 2. 重编译

```bash
bash scripts/linux/build_runtime.sh safe     # 生产口径（与发布核同优化级别）
python scripts/check_runtime_version.py      # 自检：应是 1.2（含 SCRAM_REDISTRIBUTION_MODE 等标记）
```

- 产物：`core/executables_or_wrappers/runtime/linux/ProgramSCRAM`
- 自检若仍显示旧版且角色是 **staged**：那是 GUI 的暂存副本没刷新，
  `rm -rf ~/.local/state/scram_boxapp_mixing/runtime/linux` 后会重新暂存。
  **手跑测试不走 staged，直接用上面的路径。**
- 另有 `bash scripts/linux/build_runtime.sh debug`（`-O0 -g -fcheck=bounds -fbacktrace`）与
  `poison`（见 §7）两种模式，按需使用。

## 3. 生成测试配置

```bash
python scripts/make_init_test_cases.py                 # 默认 12 h、组成档 3 段
python scripts/make_init_test_cases.py --hours 1       # 冒烟（只验初值，时长无关）
python scripts/make_init_test_cases.py --n-frac 5      # 复现 18 倍那一档
python scripts/make_init_test_cases.py --zero-mass     # 额外生成零质量复验配置 T8/T9（见 §5 末）
```

输出目录 `install_logs/20260929_init_cases/`（可随时重生成，已被 gitignore）。

| case | 成核模型 | tag_external | 组成档 | Tag_init | 用途 |
|---|---|---|---|---|---|
| `T1_nl5_nf1` | 5 | 0 | 1 | 1 | 内混基准臂（单列） |
| `T2_nl5_ext_tagext0` | 5 | 0 | 3 | 1 | 改动前：报错停机的那条路 |
| `T3_nl5_ext_tagext1` | 5 | 1 | 3 | 1 | 改动前：初值虚高 6 倍的那条路 |
| `T4_nl1_ext_tagext1` | 1 | 1 | 3 | 1 | 回归：外混初始态路径必须逐位不变 |
| `T5_nl1_ext_tagext0_ti0` | 1 | 0 | 3 | 0 | 回归/护栏：`Tag_init=0` 时曾读未初始化质量 |
| `T6_nl1_ext_tagext0_ti1` | 1 | 0 | 3 | 1 | 回归：被改的那段**必须仍然执行** |
| `T7_nl1_nf1_ti0` | 1 | 0 | 1 | 0 | T5 的内混对照臂 |

`T1–T3` 的标量对齐官方雾霾预设（298 K / 101325 Pa / RH 0.7、仅冷凝），即"官方模板 × 三个混合臂"。

## 4. 跑实验

**前置条件（否则会假通过）**：`with_cond=1` 必须开启 —— 粒径重分配与它的一致性体检只在
凝结/新成核分支里被调用（`ProgramSCRAM.f90:124-141`、`:159-171`、`:176-187`）。
三个过程全关掉时 `T2` 不会报错，看起来"通过了"。

每个 case 单独一份运行目录（核心会写 `INIT/`、`RESULT/`，并重写 `INIT/fractions.txt`）：

```bash
ROOT="$PWD"
RT="$ROOT/core/executables_or_wrappers/runtime/linux"
CASES="$ROOT/install_logs/20260929_init_cases"
OUT="$ROOT/install_logs/20260929_runs"

for c in T1_nl5_nf1 T2_nl5_ext_tagext0 T3_nl5_ext_tagext1 T4_nl1_ext_tagext1 \
         T5_nl1_ext_tagext0_ti0 T6_nl1_ext_tagext0_ti1 T7_nl1_nf1_ti0; do
  rm -rf "$OUT/$c"; mkdir -p "$OUT/$c"; cp -r "$RT"/. "$OUT/$c"/
  ( cd "$OUT/$c" && mkdir -p RESULT && "$RT/ProgramSCRAM" "$CASES/$c.cfg" > run.log 2>&1
    echo "$c exit=$?" )
done
```

## 5. 验证什么（断言清单）

| # | 断言 | 取数命令（在 case 目录内） | 期望 |
|---|---|---|---|
| **A1** | 三个臂的初始总质量相等 | `grep 'initial total mass' RESULT/report.txt` | T1 = T2 = T3，比 **1.0000**（改动前 T3 是 6.0000 倍、T2 停机） |
| **A2** | 每档总质量逐档相等 | `awk '{print NR, $NF}' RESULT/mass_init.txt` | T1 = T2 = T3，逐档一致 |
| **A3** | 逐物种：黑碳（物种号 2）与硫酸盐（物种号 4）的质量三臂相等，且各占总量一半 | `awk 'NF==5 && $1 ~ /^[0-9]+$/ {print $1, $3}' RESULT/report.txt \| head -5` | 各 0.5 倍总量（改动前黑碳是 5.5 倍） |
| **A4** | 所有参与判定的 case 无错误停机；除 `T7` 外退出码均为 0 | 脚本自动扫描各 case 的 `run.log`（`result.json` 的 `assertions[A4]`） | 无命中、退出码 0 |
| **A5** | 回归：`T4`、`T6` 与改动前构建**逐位一致** | 见 §6 | 差异 ≤ 1e-15 相对 |
| **A6** | `T5` 与对照臂 `T7` 初始总质量一致（修复前 T5 少 **4.2647**：第 5 族质量被块④ 的未初始化值覆盖） | 同 A1 | 一致（差 ≤ 1e-12；修复前差 -4.26466） |

> A1–A3、A6 都是**相对判据**：不依赖绝对基线，也不依赖模拟时长（初值口径与时长无关）。
> 若需要绝对量参照：30 物种布局 + 12 h 雾霾内混臂的历史记录是 `37.679073599845388`；
> 布局或物性表不同就不要比这个数，改以内混臂实测值为基准。

**改动前实测参照**（用未改动的旧核跑同一批配置得到，可用于人工对照；异常高/低正是因为要修的三处）：

| case | 初始总质量 | 说明 |
|---|---|---|
| `T1_nl5_nf1` | `37.679073599845388` | 内混基准臂 |
| `T2_nl5_ext_tagext0` | `228.81807486240999` | 叠加了配置文件的逐档质量（问题 2） |
| `T3_nl5_ext_tagext1` | `226.07444159907240` | = **6 ×** T1；其中黑碳 `207.2349 = 11 ×` 半份（问题 1） |
| `T4_nl1_ext_tagext1` | `21.583170063260344` | = 配置文件里 30 个物种的总量，应保持不变 |
| `T5_nl1_ext_tagext0_ti0` | `14.464046851670814` | 比 T7 少 `4.26466`（第 5 族被覆盖） |
| `T6_nl1_ext_tagext0_ti1` | `21.583170063260344` | 应保持不变 |
| `T7_nl1_nf1_ti0` | `18.728707753710463` | T5 的对照臂 |

> **取数要注意 `report.txt` 里有两张同类物种表**：`N_groups=…` 之后是**初始态**（每行 5 个数字字段），
> `Total run time:` 之后是**终态**（每行只有 4 个）。所以不要用 `awk '$1==2||$1==4'` 这种宽松选择器——
> 它会把终态表里第 1 列恰好是 2 或 4 的其它行也算进来；用上面 A3 的 `NF==5` 形式（判定脚本用的就是这个规则）。

**自动判定**：本节断言已做成可执行脚本，不必手工比对：

```bash
python scripts/check_init_fix_linux.py                    # 生成配置 → 跑 → 判定（退出码 0 = 全过）
python scripts/check_init_fix_linux.py --no-run           # 只判读已有 install_logs/20260929_runs/
python scripts/check_init_fix_linux.py --pre /tmp/ProgramSCRAM.pre --post /tmp/ProgramSCRAM.post   # 连 A5
```

逐条结果与实测数字写进 `install_logs/20260929_runs/result.json`，可直接作为回报材料。
自定义输出目录时 `--cases-dir` / `--runs-dir` 给绝对路径或相对路径都可以（脚本内部会解析成绝对路径；
相对路径曾因核心子进程的 `cwd` 叠加而找不到可执行文件，已修）。

**关于 `T7` 的提醒**：在旧核上 `T7`（`Tag_init=0` 单列）跑到初始化后**异常退出**（无 Fortran 报错、日志停在 init 阶段），且"只开冷凝"的变体会把自适应步长塌缩到几乎走不动（1 h 跑不完）；在 1.2 修复版上实测**退出码 0、正常跑完**。它的**初值**写在 `RESULT/report.txt` 里、与后续是否跑完无关，所以 A6 照常可用；但请把 `T7` 的退出码当作观察记录，**不要**当成失败判据（脚本把 `T7` 排除在 A4 的退出码判据之外，日志仍会扫描）。建议 `T7`/零质量项都用 `--hours 1` 或更短。

**可选记录项（不设通过判据）**：用 `--zero-mass` 生成的 `T8_zero_mass_int` / `T9_zero_mass_ext`
（`Tag_init=1`、逐档质量全 0、逐档粒子数非 0、`tagrho=0`）跑一遍，**只记录实测行为**：
跑完 / 报 `orphan mass/number before remap` / 报 `nonfinite` 都算有效结论。目的只有一个 ——
台账里"零质量 + 凝并空转、内外混终态粒子数差 4 个数量级"的复现记录是**旧核**上做的，
需要一条 1.2 核下的记录来确认它已随新核消失（1.2 的设计是"拒绝静默使用异常格"，所以报错也是合格结论）。

> **已执行（2026-09-29）**：`T8`/`T9` 两臂都跑完、退出码 0，内外混**终态质量与粒子数逐位一致**；
> 旧核"差 4 个数量级"未复现。唯一异常是终态控制台统计出现 `Nub Coag = NaN` / `n_emis = Infinity`。
> 记录见 `docs/rebuild.md` §7 与台账 2026-09-29 节；"零质量是否算合法输入"仍属模型未定义域。

## 6. 零回归基线（A5 怎么做）

```bash
SRC=core/executables_or_wrappers/runtime/windows/source/SCRAM1.2/SRC/ModuleDiscretization.f90
PRE=53ff858    # 本轮改动前的最后一次提交；若历史被改写，换成"<本轮提交>^"

cp "$SRC" /tmp/ModuleDiscretization.f90.fixed     # 存好改后版
git show "$PRE:$SRC" > "$SRC"                     # 临时换回改动前
bash scripts/linux/build_runtime.sh safe
cp core/executables_or_wrappers/runtime/linux/ProgramSCRAM /tmp/ProgramSCRAM.pre

cp /tmp/ModuleDiscretization.f90.fixed "$SRC"     # 换回改后版
bash scripts/linux/build_runtime.sh safe
cp core/executables_or_wrappers/runtime/linux/ProgramSCRAM /tmp/ProgramSCRAM.post
```

用两份二进制各跑一遍 `T4`、`T6`（以及任一 `gmd_paris_*` 标准案例），比对
`RESULT/report.txt` 与 `RESULT/mass_init.txt`：**必须逐位相同**（这两条路都不经过被改的分支）。

## 7. 可选诊断：未初始化内存（`mode=poison`）

```bash
bash scripts/linux/build_runtime.sh poison    # 与 safe 同优化级别 + -finit-real=snan
```

用中毒构建跑 `T2 / T5 / T6 / T7`，两种结果的含义：

- **与非中毒构建逐位一致** ⇒ 相关未初始化读已被封死（对"清零兜底"最强的验证）。
- **报 `nonfinite remap input` 或 `orphan`** ⇒ 核内**还有别的**未初始化实数被读到，不属于本次三处改动；
  请留下该 case 的 `run.log` 与配置，按同样格式记录。

> `-finit-real=snan` 只初始化**实数**未初始化变量；整型由 `-finit-integer=0` 处理（safe/debug 都带）。
> 若本机 gfortran 不接受 `snan`，把 `SConstruct` 里 `poison_flags` 的 `-snan` 换成 `-finit-real=nan`。

## 8. 记录与回报

每个 case 至少保留：`run.log`、`RESULT/report.txt`、`RESULT/mass_init.txt`、`RESULT/number_init.txt`，
以及所用配置（`install_logs/20260929_init_cases/<case>.cfg`）。回报时按 §5 的表逐条给"通过/不通过 + 实测数字"，
不通过时附 `run.log` 的关键片段。

## 9. 通过之后

- Linux 侧任务到此结束：把结论与留存的日志回报即可。
  **2026-09-29 已执行并通过**（A1–A6 全 PASS、判定退出码 0；`--n-frac 5` 亦通过；产物核已随提交 `287629f` 发布）——
  执行记录与实测数字见 `docs/rebuild.md`，判定明细 `install_logs/20260929_runs/result.json`。
- 其后由 Windows 侧重编译发布核（步骤见 `docs/windows_devkit_readme_zh.md` §9），
  并用 `scripts/check_runtime_version.py`（期望 1.2）与 `scripts/run_standard_tests.py` 收口。
- 注意：1.2 生效后 1.1 时代的数值基线全部作废，需要重采。
