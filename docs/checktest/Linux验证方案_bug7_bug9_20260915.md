# Linux 侧验证方案：Bug #7（method 6）与 Bug #9（nucl_model=5）

> 制定：2026-09-15（Windows 侧）。执行：Linux 侧（明天）。
> **本方案是给 agent 的自包含任务书**：不依赖任何对话上下文，按 §1→§4 顺序执行即可；
> 每步都有明确命令、判据与不通过时的处置。执行完把 §5 的证据清单发回。

---

## 0. 任务概述与角色

| 项 | 内容 |
|---|---|
| **要回答的问题** | ① `redistribution_method=6`（euler_coupled）打了 v5 补丁后是否真正守恒、能否保留该方案？② `nucl_model=5` 的读文件修复在 Linux 核上是否仍然成立？ |
| **判定性质** | ① 是**对照实验**（stock vs patched 两棵树），不是单臂观察。② 是**回归复核**（结果应与历史记录一致）。 |
| **需要什么** | gfortran / gcc / nf-config / scons（见 §2 前置）+ 项目 `.venv` |
| **交付** | §5 的证据清单 + 结论（保留 method 6 / 需要再改 / 撤掉 method 6 三选一） |
| **明确不做** | 不改核心算法、不动 `app/**`、不删 `install_logs/**` 既有产物、不清理仓库 |

---

## 1. 待验证的两个改动（来源与现状）

两处修复都**已经在仓库源码树里**（`core/executables_or_wrappers/runtime/windows/source/SCRAM1.1/SRC/**`），
但**都没有编译验证过**，Linux 侧产物也不是用这份源码重建的。改动清单：

### Bug #7 → 补丁 `proposals/bug7_method6_v5.patch`（3 处）

| # | 文件 | 内容 |
|---|---|---|
| 1 | `SRC/rdb/euler_coupled.f90` 交付循环 | **真因修复**：累加器 `Q_2*/N_2*` 按**目标** bin 索引，但原交付循环按**源** bin 迭代 ⇒ 共享同一 `kloc` 值的多个源把同一份 hand-out 重复交付。改为按累加器索引迭代一次。 |
| 2 | `SRC/rdb/euler_coupled.f90` 两处比值检查 | `RQ(k)/Q(k)` 改为先判 `Q(k) .NE. 0D0`（Fortran 不短路求值，原判断在第三个 `.AND.` 操作数里，求值太晚） |
| 3 | `SRC/ModuleThermodynamics.f90:264` | `total_PH = -log10(...)` 加零保护（无 IH 物种时 `total_IH=0` → `log10(0)`） |

> 注意：**不要**用 `proposals/bug7_double_add_v4.patch`。v4 还改了 3 处 `PRINT*` 文案，
> 而那几处文案正是 Python 侧失败判据的匹配串，改文案会让判据失效。v5 已经剔除了这三处。

### Bug #9 → 补丁 `proposals/bug9_nucl_model5_file_pointer.patch`（已进树）

`SRC/ModuleDiscretization.f90:129-136` 的 `if(nucl_model.ne.5)` 跳过读三行却不消费 ⇒ 文件指针错位。
已改为无条件读入。（该修复 2026-09-11 在 Linux 侧验证过一次，本次是**回归复核**。）

### 与本次验证一起生效的 Python 侧改动（Windows 侧刚改，需一并带上）

- `app/services/run_service.py`：失败判据对齐 `scripts/linux/probe_cell.py` 口径
  （不再裸匹配 `negatif`；`sans STOP` 先摘除；`non conservation` 收紧为
  `non conservation du nombre total` / `…de la masse totale`）。
  **先确认这条在 Linux 侧也在，否则 patched 侧跑得再好也会被显示成 failed。**

---

## 2. 前置：环境与构建

```bash
cd <仓库根>                          # 例如 /home/yifeihu/SCRAMBoxApp-WinDevKit
git status --porcelain | head        # 记录现状；下面要用 git worktree，工作树需干净或先 stash

for c in gfortran gcc nf-config; do command -v $c || echo "缺失: $c"; done
ls .venv/bin/scons .venv/bin/python 2>/dev/null || echo "缺 .venv（见 README 'Install on Linux'）"
```

若缺依赖（Debian/Ubuntu）：

```bash
sudo apt install gfortran gcc libnetcdff-dev scons
```

**建两棵独立的构建树**（避免 stock/patched 互相覆盖；`build_runtime.sh` 会把产物装到
`core/executables_or_wrappers/runtime/linux`，两棵树各自只影响自己的 worktree）：

```bash
# stock（未打补丁）
git worktree add /tmp/scram_stock HEAD

# patched（v5）
git worktree add /tmp/scram_patched HEAD
cd /tmp/scram_patched
git apply --ignore-whitespace <仓库根>/proposals/bug7_method6_v5.patch
git diff --stat          # 应显示 2 files changed（euler_coupled.f90 + ModuleThermodynamics.f90）
```

> ⚠️ `git apply` **必须带 `--ignore-whitespace`**：本仓库 `core.autocrlf=true` 且工作树行尾混杂，
> 不带该参数会报 `patch does not apply`（已实测）。

两棵树各自构建（每棵都要有自己的 `.venv` 或让 `SCONS` 可解析；见 `build_runtime.sh` 顶部检查）：

```bash
cd /tmp/scram_stock   && bash scripts/linux/build_runtime.sh safe
cd /tmp/scram_patched && bash scripts/linux/build_runtime.sh safe
```

记录两个二进制的指纹，作为"确实换过 exe"的证据：

```bash
sha256sum /tmp/scram_stock/core/executables_or_wrappers/runtime/linux/*/ProgramSCRAM* \
          /tmp/scram_patched/core/executables_or_wrappers/runtime/linux/*/ProgramSCRAM*
```

**预期**：两者 sha256 **不同**。若相同 ⇒ patch 没生效或没重编译，**停止后续步骤并报告**。

---

## 3. 实验一：Bug #7（method 6）四臂对照

### 3.1 臂设计

| 臂 | 树 | 配置 | 期望结果 |
|---|---|---|---|
| A1 | stock | `gmd_hazy_coag_cond` + `redistribution_method=2` | ✅ 跑通（对照 A 组：确认仪器/环境正常） |
| A2 | stock | 同上 + `redistribution_method=6` | ❌ **失败**（活 STOP，`non conservation du nombre total`） |
| B1 | patched | 同上 + `redistribution_method=2` | ✅ 跑通；且与 A1 **逐位相同**（补丁不该影响 method 2） |
| B2 | patched | 同上 + `redistribution_method=6` | ✅ **跑满 12h、无活 STOP、守恒** ← 本次要验证的核心 |

### 3.2 跑法

用既有的 `probe_cell.py`（它按模板生成 cfg、调用核、落证据）：

```bash
cd /tmp/scram_stock
.venv/bin/python scripts/linux/probe_cell.py \
    --template gmd_hazy_coag_cond --case coag_cond \
    --set redistribution_method=6 --out /tmp/scram_stock/probe_A2
```

四个臂照此各跑一次（A1/A2 在 stock 树，B1/B2 在 patched 树；`--set redistribution_method=2` 或 `6`）。
**每臂把 cfg 与 run.log 都留档**（`--out` 指定目录）。

### 3.3 判据（B2 必须全过）

1. **跑满步数**：`performance_summary.csv` 的 `status=ok`，且模拟时间达到 12h（43200s）；
2. **零活 STOP**：`run.log` 里带 STOP 的两处守恒检查**一次都没触发**——
   ```
   grep -c "non conservation du nombre total" <B2>/logs/run.log     # 期望 0
   grep -c "non conservation de la masse totale" <B2>/logs/run.log  # 期望 0
   ```
   > 注意：`run.log` 里还可能打印逐 bin 的 `non conservation de la masse ds algo!!` /
   > `…du nombre ds algo!!`，那是**信息性打印**（后面没有 STOP），**不算失败**。别用裸关键字判。
3. **守恒到机器精度**：从 `csv/conservation_audit.csv` 逐时刻算
   `|1 - total_mass_after/total_mass_before|` 与 `|1 - total_number_after/total_number_before|`，
   在**交付之后**的判据点上应为 0（或 ≤ 1e-12）。注意该文件同时含"交付前"的中间量，
   要按 `timestep` 对到交付后的那一列（必要时直接读终态：终态总量应与 `N_ancien` 一致）。
4. **反证（阴性对照有效）**：A2 必须**失败**。若 A2 也通过 ⇒ 判据没有判别力，
   本次实验**结论无效**，需先修判据再重跑。

### 3.4 附加：浮点路径（可选但建议）

用 `-ffpe-trap` 构建 patched 树，确认 v5 之外是否还有无保护浮点
（v4 提案提到 `ModuleThermodynamics.f90` 的 `aec_drv` 处未修）：

```bash
cd /tmp/scram_patched && bash scripts/linux/build_runtime.sh debug   # debug 模式带 -fcheck=bounds -fbacktrace
# 若要 -ffpe-trap，需在 SConstruct 的 flags 里临时加 -ffpe-trap=zero,invalid,overflow（只在这棵树里改）
```
若触发陷阱，记录 backtrace 与行号即可，**不要**在本次任务里顺手改核心。

---

## 4. 实验二：Bug #9（nucl_model=5）回归复核

```bash
cd /tmp/scram_patched        # #9 的修复已在两棵树的 HEAD 里，用哪棵都行
.venv/bin/python scripts/linux/probe_cell.py \
    --cfg docs/checktest/nucl_model5_test.cfg --case nucl_model5_test \
    --out /tmp/nucl5_ok
.venv/bin/python scripts/linux/probe_cell.py \
    --cfg docs/checktest/nucl_model5_fixed.cfg --case nucl_model5_fixed \
    --out /tmp/nucl5_negctl
```

判据：

| 臂 | 配置 | 期望 |
|---|---|---|
| 正例 | `nucl_model5_test.cfg`（标准 56 行） | ✅ 跑通；`inital total mass`（原文拼写如此）= **226.07444159907240** |
| 负对照 | `nucl_model5_fixed.cfg`（手工删行 53 行） | ❌ 报错 `Bad real number in item 2 in list input`（该行本不该删） |

数值与历史记录（2026-09-11 Linux、2026-07-27 台账，均为 226.07）**一致**即通过。

---

## 5. 交付证据清单（发回 Windows 侧）

请把下列内容整理成一份简短报告（贴路径 + 关键数值，不要贴大段日志）：

1. **环境**：`gfortran --version`、`nf-config --version`、两棵树 `git rev-parse HEAD` 与 patch 后 `git diff --stat`；
2. **二进制指纹**：stock / patched 两个 `ProgramSCRAM` 的 sha256（必须不同）；
3. **实验一四臂表**：每臂的 `status` / 步数 / 模拟时长 / 活 STOP 计数 / 终态 mass 与 number；
4. **B2 的守恒数据**：交付后判据点的最大相对残差（数量、质量各一个数）；
5. **B1 vs A1 的逐位对比**：终态 mass/number 是否逐位相同（补丁不应影响 method 2）；
6. **实验二两臂结果**：正例的初始总质量数值、负对照的报错文本；
7. **结论建议**：method 6 是「保留（已验证）」/「仍需修改（附失败点）」/「建议撤掉」三选一，并给一句话依据；
8. **任何与预期不符的地方**（包括判据本身不动、跑不通、数值对不上）——如实记录，不要为了"通过"而调参数。

### 不通过时的处置（明确，避免自由发挥）

| 症状 | 先查什么 | 不要做什么 |
|---|---|---|
| B2 仍触发活 STOP | 补丁是否真的进了构建树（比对 `.f90` 与 `git diff`；确认 exe 指纹变化）；残差是**结构性**还是**边界丢弃**（`kloc==1`/`==ns` 分支按作者回复属"有意为之"，残余相对丢失 `9.77e-6` 量级可接受） | 不要改核心算法 |
| A2 也通过（判据无判别力） | 判据是否读了正确的列（交付后 vs 交付前）；`status` 来源是否为核对之后的返回码 | 不要宣布 method 6 已修好 |
| B1 ≠ A1 | 补丁是否误伤了非 method 6 路径 | 不要把差异归因于"编译差异"就放过 |
| 构建失败 | 依赖、`SCONS`/`.venv`、`--ignore-whitespace` | 不要为了编过去而删源码 |

---

## 6. 附：本次验证为什么必须是对照而不是单臂

`euler_coupled.f90` 里的守恒检查是**带 STOP 的程序内断言**，但日志里同时存在**三处不带 STOP 的同名文案**。
如果只跑 patched 一臂、按裸关键字 "non conservation" 判定，就会得出"仍然失败"的错误结论
（2026-09-13 的 Q-27 假阳性就是这么来的）。所以本方案要求：

- **阴性对照 A2 必须失败** —— 证明判据能测出真问题；
- **阳性对照 A1/B1 必须逐位相同** —— 证明补丁没有副作用；
- **判据只看带 STOP 的两处**，逐 bin 打印属信息性。
