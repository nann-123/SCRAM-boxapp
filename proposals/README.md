# 提案

> 本目录存放对**核心源码**（`core/executables_or_wrappers/runtime/windows/source/SCRAM1.1/SRC/**`）
> 的修改提案。核心改动必须经人工审阅 + 重编译后才进发行件。

| 提案 | 文件 | 状态 | 需要重编译 |
|---|---|---|---|
| Bug #9 nucl_model=5 文件指针 | `bug9_nucl_model5_file_pointer.patch` | **已进源码树**（2026-09-11），Linux 核已验证；Windows 发行核待重编 | 是 |
| Bug #7 method 6 数量不守恒 | `bug7_method6_v5.patch` | **2026-09-15 已进源码树，未编译验证** | 是 |
| Bug #7 历史版本 v1/v2/v3 | `bug7_euler_coupled_divzero*.patch` | 已作废（guard 打在不可达相位，逐位无变化） | — |
| Bug #7 历史版本 v4 | `bug7_double_add_v4.patch` | 已被 v5 取代（v4 含 3 处**只改打印文案**的改动，会与 Python 侧判据冲突） | — |
| Bug #12 RDB 核心模式死控件 | `bug12_rdb_core_mode_dead.patch` | 待人工 | 是 |

---

# Bug #7 / method 6：v5（2026-09-15）

> 补丁文件：`proposals/bug7_method6_v5.patch`（`git apply --ignore-whitespace` 可干净套用；
> 不带该参数会因本仓库 CRLF/LF 混杂而失败）

## 一、根因（v4 已定位，本次复核逐行确认）

`SRC/rdb/euler_coupled.f90` 的两个阶段维度不一致：

1. **阶段一**按**源** bin k 遍历，把每个源要交出的量写进累加器
   `Q_1_esp / N_1_esp / Q_2evap_esp / Q_2cond_esp`，而这四个数组**按目标** bin 编号索引
   （写的是 `Q_2cond_esp(kloc(k), jesp)`）。
2. **阶段二**（原 378-400 行）把累加器交付给邻居，却是**按源** bin k 迭代的。

⇒ 同一个累加器格被重复读取，重复次数 = 共享同一个 `kloc` 值的源个数。
插桩证据（v4 文件头"证据 2"）：第二次守恒检查 `N_nouveau` = 第一次 + 2H ⇒ 净多交付一次。

## 二、v5 改了什么（3 处，均为必要）

| # | 文件 | 改动 | 性质 |
|---|---|---|---|
| 1 | `SRC/rdb/euler_coupled.f90:386-401` | 交付循环改为**按累加器索引迭代一次**：`Q_2evap_esp(k)` → 交给 `k-1`；`Q_2cond_esp(k)` → 交给 `k+1` | **7a，真因修复** |
| 2 | `SRC/rdb/euler_coupled.f90:244/256` | `RQ(k)/Q(k)`、`RN(k)/N(k)` 改为先判 `Q(k) .NE. 0D0` 再算比值（Fortran 不短路求值，原判断在第三个 `.AND.` 操作数里，求值太晚） | 7b，健壮性 |
| 3 | `SRC/ModuleThermodynamics.f90:264` | `total_PH = -log10(...)` 加 `total_IH > 0 .AND. total_water > 0` 保护，否则取 0 | 7c，健壮性 |

**v5 相对 v4 的唯一差别**：v5 **不**改任何 `PRINT*` 文案。
v4 把三处信息性打印改成了 `INFO(algo, sans STOP) …` / `INFO redistribution: …`，但
`app/services/run_service.py:557-563` 的致命判据是按裸字符串 `"non conservation"` / `"STOP"` /
`"negatif"` 匹配的 —— 改文案等于让 `euler_coupled` 的每个格子继续被判 failed。
**判据要改就在 Python 侧改**（对齐 `scripts/linux/probe_cell.py` 已有的 `sans STOP` 豁免口径），
不该让核心的日志文案绑住判据。

## 三、验证状态（如实记录）

| 项目 | 状态 |
|---|---|
| 补丁与源码树一致（反向可套用） | ✅ 已验证 |
| 补丁对未修的源码可干净套用 | ✅ 已验证（`--ignore-whitespace`） |
| DO/ENDDO、IF/ENDIF 配平；无 >132 列的行；改动处无 tab | ✅ 静态检查通过 |
| **编译** | ❌ **未做**。本机无 gfortran/gcc/cmake/make/ninja，无 WSL，`NETCDF_ROOT`/`CONDA_PREFIX` 未设 |
| **端到端运行**（跑满 12h、守恒判据） | ❌ **未做**（依赖上一条） |

验收判据（编译后执行）：
1. `stock`（未修）与 `patched`（v5）两棵树各跑 `gmd_hazy_coag_cond + redistribution_method=6` 一个完整 12h；
2. patched 侧：跑满步数、**带 STOP 的两处守恒检查（`:424`/`:433`）计数为 0**、
   数量与质量守恒到 `EPS_machine`；
3. 对照 stock 侧同配置应触发 `non conservation du nombre total` 并 STOP；
4. 顺带用 `-ffpe-trap=zero,invalid,overflow` 构建确认 7c 的其余浮点路径（提案 v4 提到 `aec_drv` 那处未修）。

## 四、编译前置（本机缺口）

- 需要：`gfortran` + `gcc` + `scons` + netCDF-Fortran（`nf-config` 可用）。
- Windows 路线：MSYS2 的 `mingw-w64-x86_64-gcc-fortran` + `mingw-w64-x86_64-netcdf-fortran`。
- `SConstruct` 已写明取 `FC`（默认 `gfortran-15`）与 `NETCDF_ROOT`/`CONDA_PREFIX`。
- conda 路线当前被 **Anaconda ToS 未接受**拦住（`conda tos accept --channel https://repo.anaconda.com/pkgs/main` 等），
  属基础设施操作，需人工决定后再做。

## 五、套用后必须同步的动作

1. **Python 判据对齐**（先做）：`app/services/run_service.py` 的 `_FATAL_LOG_PATTERNS` 去掉裸 `"STOP"`/`"negatif"`，
   或与 `probe_cell.py` 用同一份判据；否则修复效果无法从日志判读。
2. `docs/BUG_TRACKING.md` #7 条目改为 7a/7b/7c/7d 四条分别销账。
3. Windows 发行核重编译 + 删用户态暂存运行时 + 重跑 devkit §6 标准测试。

---

# 提案：修复 Bug #9 — nucl_model=5 配置文件指针错位

> 生成方式：把源码树复制到 `/tmp` 打补丁后**实际编译并运行过**（不碰仓库源码与二进制）。
> 补丁文件：`proposals/bug9_nucl_model5_file_pointer.patch`（`git apply` 可干净套用）

## 一、改了什么

`core/executables_or_wrappers/runtime/windows/source/SCRAM1.1/SRC/ModuleDiscretization.f90`
原第 129-134 行：

```fortran
    if(nucl_model.ne.5) then
      read(10,*) (init_bin_number(k),k=1,N_sizebin)
      do s=1,min(N_species,2)
	      read(10,*) (init_bin_emission(k,s),k=1,N_sizebin)
      enddo
    endif
```

改为**无条件读入这三行**（等价于给 `nucl_model=5` 补上原缺失的 dummy read）。理由：

- app 侧的配置写出器 `app/config_binding/config_model.py:157-166` **无条件**写 `init_bin_number` 与两行
  `init_bin_emission`——也就是说 GUI 与标准测试产生的每一份 cfg 都带这三行；
  `nucl_model=5` 时旧代码跳过却不消费它们 → 文件指针停在原地 → 后续 `diameter` 读取读到这些数据 → 崩溃。
- `nucl_model=5` 的初始化走该文件后面指定的硬编码分支（第 562 行起，用 `mass_init/2` 分给 SO4/BC），
  不消费 `init_bin_number`/`init_bin_emission`，因此补读**不改变数值**（见下方证据：终态初始总质量逐位相同）。

## 二、实测证据（2026-09-11，本机 gfortran 12.2）

| # | 二进制 | 配置 | 结果 |
|---|--------|------|------|
| 1 | 仓库现役（未打补丁） | `docs/checktest/nucl_model5_test.cfg`（标准 56 行） | ❌ 崩溃：`Bad integer for item 1 in list input`，退出码 2 —— **Bug #9 复现** |
| 2 | 打补丁的变异构建 | 同上 | ✅ 跑完，退出码 0；`inital total mass 226.07444159907240` |
| 3 | 仓库现役 | `docs/checktest/nucl_model5_fixed.cfg`（手工删行 53 行） | ✅ 跑完；同一数值 `226.07444159907240` |
| 4 | 打补丁的变异构建 | 手工删行 53 行 | ❌ 崩溃：`Bad real number in item 2 in list input`（该行本不该存在 → 旧绕过法作废） |

场景 2 与场景 3 的数值**逐位相同**，且与台账记录的 2026-07-27 验证结果（初始总质量 226.07 µg/m³）一致
→ 补丁既修好了解析，也没有改变物理结果。

## 三、套用步骤

```bash
cd /home/yifeihu/SCRAMBoxApp-WinDevKit
git apply --check proposals/bug9_nucl_model5_file_pointer.patch   # 只检查
git apply        proposals/bug9_nucl_model5_file_pointer.patch   # 落地（人工审阅后）
bash scripts/linux/build_runtime.sh                               # 重编译 Linux 核心（源码改动必须重编译）
```

验收：`docs/checktest/nucl_model5_test.cfg` 能跑完且 `initial total mass ≈ 226.07`；
`scripts/linux/noop_probe.py` 不受影响。

## 四、套用后必须同步的动作（人工）

1. **夹具口径反转**：标准 56 行版本成为"可运行"版本；`nucl_model5_fixed.cfg`（手工删行）作废，
   建议保留为负对照（补丁后应报错）并在文件头注明。
2. **BUG_TRACKING #9 证据行更新**：现行报错文本是 `Bad integer for item 1`，与 7 月记录的
   `Bad real number in item 8` 不同（配置或读取路径有过小改动），登记时应写现行证据。
3. **Windows 侧**：改动位于 `SRC/`（无平台分支），Windows 发布核需重编译后重新走一遍 devkit §6 标准测试。
4. **Bug #11 先行或并行**：`noop_probe.py` 要能验证"开关真实起作用"，需要先修 Bug #11
   （Case Preset 覆盖开关），否则这类反证式探测无法给出可信结论。

## 五、未做的验证（如实记录）

- 只跑了 `nucl_model5_test.cfg` 单次端到端（退出码 0、初始总质量一致）；
  **未**逐项比对运行耗时与终态输出（7 月记录为 24.03 s / 30 物种）。
- 未在 Windows 上编译验证（本机只有 Linux 工具链）。
- 未覆盖 `N_sizebin` 特别大导致这三行数据跨行的极端配置（列表读取会自行续行，补丁与旧码行为一致）。
