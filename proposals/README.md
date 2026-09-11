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
