# Config Mapping Spec

The GUI does not expose the SCRAM cfg file as one long form. It reorganizes the same semantics into workflow cards and structured tables while preserving parser/serializer compatibility.

## Workflow Cards

- `Experiment and Scheme`
  - experiment name
  - template / preset
  - case preset
  - mixing assumption: `INTERNAL_MIXING` or `EXTERNAL_MIXING`
- `Process Toggles and Mixing Notes`
  - coagulation toggle
  - condensation / evaporation toggle
  - nucleation toggle
  - internal/external mixing explanation
- `Runtime and Output`
  - simulation time
  - minimum timestep (dead control — greyed out; the core reads `dtmin` but never uses it)
  - output directory
- `Environment and Initial State`
  - temperature
  - pressure
  - humidity
  - initial scenario
  - initial external-mixing placement flag
  - density mode
  - fixed density
- `Advanced Controls`
  - coefficient file
  - sulfate computation
  - nucleation model
  - groups / solver / thermodynamic / grid / composition fields

## Conditional Visibility

- `INTERNAL_MIXING`
  - shows the note explaining the single-average-composition assumption per size section
- `EXTERNAL_MIXING`
  - shows the note explaining the size-composition grid and mixed/unmixed particle diagnostics
- `with_cond = 0`
  - hides condensation-specific controls
- `with_nucl = 0`
  - hides nucleation model controls
- `tag_external = 0`
  - hides external-initial-state advanced fields

## Structured Tables

### Species Table

Columns:

- `species_id`
- `species_name`
- `group_id`
- `init_gas`
- `emission`
- `notes`

### Size Bins Table

Columns:

- `bin_id`
- `lower_bound`
- `upper_bound`
- `representative_diameter`
- `initial_number`
- `notes`

### Fraction Table

Columns:

- `fraction_id`
- `lower_bound`
- `upper_bound`
- `notes`

### Emission Table

- one row per species
- one column per size bin plus an actions column with add/remove controls
- serialized back to SCRAM emission rows for compatibility

### Initial Mass Table

- one row per species
- one column per size bin
- cells map to `species_records[*].bin_values`

## Dimension-Driven Regeneration

The following scalar fields drive table size:

- `n_species`
- `n_sizebin`
- `n_frac`

Changing these values and clicking `Generate Structure` rebuilds the table skeleton while preserving compatible values where possible.

## Serialization and Deserialization

- parsing reads the current SCRAM config semantics
- serialization rebuilds the config body from the current table dimensions
- species comments are mapped into `species_name` and `notes`
- cfg loading must render parsed values directly into the GUI tables before any table-derived collection occurs

## Validation Rules

- `n_species` must match species table row count
- `n_sizebin` must match the size-bin table, emission table width, and initial mass table width
- diameter bounds must be strictly increasing and have length `n_sizebin + 1`
- fraction bounds must be strictly increasing, start at `0`, end at `1`, and have length `n_frac + 1`
- mixing assumption must be `INTERNAL_MIXING` or `EXTERNAL_MIXING`


## 2026-09-29 GUI changes (keep this spec in sync)

- **Mixing assumption** is no longer locked: the combo's initial value is inferred from the loaded cfg (`n_frac == 1`
  → `INTERNAL_MIXING`, else `EXTERNAL_MIXING`) and may be changed freely. Compare runs always run both arms and
  ignore this combo.
- **Config preview now shows what is actually sent to the core**: `_render_preview_text()` runs the same
  `RunService.transform_config` pipeline as `prepare_run` and prepends a header with the rewritten keys and the
  two-arm diff keys.
- **`nucl_model`** is a two-option combo (1 = ternary nucleation, 5 = paper validation mode). Selecting 5 switches
  and locks the species table to the 30-species baseline layout (slot 2 = BC/group 4, slot 4 = SO4/group 1).
- **`tag_init`** gained a control: `Initial values from` (1 = per-bin masses in the cfg, 0 = built-in scenario
  distributions). With 0 the per-bin mass table is greyed out and the serializer emits the 5-column short species
  rows (species total mass = sum of per-bin masses).
- **Input guards** in `ConfigModel.validate()`: zero-mass input (U-06a), `nucl_model=5` layout mismatch (U-07),
  and the undefined `(tag_init=0, tag_external=0, n_frac>1)` combination (1.1 core reads uninitialized memory there).
  Loading a bad cfg now warns immediately; running is still blocked until it is fixed.
- **`mapping_scheme`** is wired through to `SCRAM_COEFF_REPARTITION_MODE` (it was silently forced to
  `COAG_TARGET_NEAREST` before).
- **Paths** handed to the core are ASCII-only (`RunService.ascii_name`), and `SCRAM_RESULTS_DIR` is always absolute
  (the 1.2 core reads it; a relative value made the result collector read misaligned outputs).

## 内核槽位是编译期常量（2026-09-30 实测补记）

`INC/pointer.inc` 把物种索引钉死为编译期常量：
`EMD=1, EBC=2, ENa=3, ESO4=4, ENH4=5, ENO3=6, ECl=7`。
两个直接后果（均为实测）：

1. **硫酸冷凝只认第 4 槽**（`ModuleCondensation.f90` 的 `SULFDYN` 全程用 `ESO4`）：
   物种数 < 4、或硫酸盐不在第 4 槽时，`Mass Cond` 恒为 0（浓度 ×1000 亦无效）。
2. **无机热力学（isorropia，含吸水）需要 SO4(4) 与 NH4(5) 同时在场**：
   只有 SO4 而无 NH4 时 `total_water` ≈ 0（实测 8e-11），吸湿/热力学不工作。

据此，`examples/configs/default_config.cfg`（teaching 基座）改为**5 槽位、3 个零质量占位**：
`1=MD(0)、2=BC(有质量)、3=Na(0)、4=SO4(有质量)、5=NH4(0)` —— 教学基座保持"**BC+SO4 两物质**"的
设计（干质量合计 1.4797e-3），槽位排列与内核常量一致。改后实测：气溶胶吸水/热力学复活
（`total_water` 由 ≈0（8e-11）变为 2.0e-3）；硫酸盐气相（5e-4）可被颗粒吸收（12 h 干质量 +19%）。
注意 **`Mass Cond` 计数器 ≠ 冷凝是否发生**：两物质教学基座（NH4 槽清零）实测 SULFDYN 仍执行
（`SCRAM_DEBUG=1` 时 run.log 出现 `CONDENSATION SULFDYN executed`）、硫酸盐仍被吸收
（12 h 干质量 +19%，且 `with_cond=0` 时干质量逐位零增长作对照），但 `Mass Cond` 计数恒为 0 ——
该计数器主要在 `ModuleBulkequibrium`（无机热力学）末尾按平衡物种累加 `dq`（:173 / :332），
无 NH4 时（若体系只有 SO4 一个无机物种）无机平衡无净转移 ⇒ 无读数。

**2026-09-30 追加实测（30 物种 gmd_paris_full，只把 NH4 清零，其余同模板同预设）**：
- `Mass Cond` **仍非零：8.387210 → 4.281374**（并非归零）；
- `Nub Coag` 由 −1.4868e14 变为 **−2.9349e10（约 1/5000）**；步数 743 → 318；
- 干质量增长 +52.3% → +36.3%；混合度终态 0.5728 → 0.5739（几乎不变）。

**`Mass Cond` 记账完整性 vs 物种集（2026-09-30 矩阵实验，同基座 12 h、冷凝开）**：

| 有质量物种(内核槽) | 物种数 | Mass Cond | 干质量变化 |
|---|---|---|---|
| BC+SO4（2、4） | 2 | 0.000000 | +19%（硫酸盐吸收**未计入**） |
| BC+Na+SO4 | 4 | 0.000000 | +18.7% |
| BC+Na+SO4+NH4 | 5 | **+1.13e-4** | +22.3%（NH4 让铵盐体系可算 → 计数点火） |
| BC+Na+SO4+NO3（无 NH4） | 6 | **−2.0e-4** | +2.3% |
| BC+Na+SO4+NH4+NO3 | 6 | **−4.95e-4** | **−11.1%**（半挥发组分净蒸发） |
| 30 物种（原生 / NH4 清零） | 30 | +8.387 / +4.281 | +52.3% / +36.3%（收支闭合 0.05%） |

⇒ `Mass Cond` = **净"气↔粒"转移质量**（正=净冷凝，负=净蒸发），但其记账**只在无机物种集完整时才闭合**；
少物种/退化布局下它只覆盖平衡块那一部分（纯硫酸盐吸收不计）——"质量涨了、计数为 0"即源于此；
**退化布局下符号也可能与总干质量变化相反**（BC+Na+SO4+NO3 无 NH4：干质量 +2.3%、计数 −2.0e-4）
⇒ 退化布局中该计数的**幅度与符号都不可信**，判据必须换用干质量/混合度。
物种数 7–29 的中间档未逐点测（趋势由"无机体系是否可算"决定，可按需补测）。

**两个容易混淆的"Mass Cond = 0"（2026-09-30 澄清）**：
① `with_cond=0`（如 coag_only 预设）：`SULFDYN` 的调用被 `tag_cond==1` 门控（`ModuleAdaptstep.f90:69-78`），
   **冷凝根本没发生** ⇒ 计数 0 是正确读数（佐证：干质量 12 h 逐位不变）；
② `with_cond=1` 但布局退化（两物质教学基座）：**冷凝在跑、质量在转移**（`SCRAM_DEBUG` 标记命中、
   干质量 +19%、with_cond=0 时零增长作对照），但计数路径（平衡块 `dq` + `Ros2_solver` 的 G1..G2）
   未覆盖该转移 ⇒ 计数 0。精确路径待内核加桩确认（属改内核，需批准；30 物种布局不受影响，收支闭合 0.05%）。

**`Mass Cond` 的语义（2026-09-30 账目验证）**：它就是"**冷凝（气→粒转移）的质量累计**"——
累加三处：`ModuleBulkequibrium.f90:173/:332`（无机平衡块按 `dq=q_ext−q_ext_old`）、
`ModuleAdaptstep.f90:717-723`（`Ros2_solver` 按 `tmp=q2−prev_q2`，遍历 `G1..G2 = 物种 4..7`）。
常量出处：`ModuleInitialization.f90:204-205`（`G1=ESO4, G2=ECl`；该文件 latin-1，grep 需 `-a`），
同处 `nesp_isorropia = 5` 是**硬编码**的无机平衡物种数（:212）。
**账目闭合实测**：Δ干质量 ≈ `Mass Cond` + `m_emis`（原生 8.387210+2.898872=11.286082 vs 实测 11.291264，差 0.05%；
NH4 清零 4.281374+2.898872=7.180246 vs 7.226016，差 0.6%；两次 `m_emis` 完全相同 ⇒ 排放不受 NH4 影响）。
⇒ 30 物种布局下 **`Mass Cond` 可以当"冷凝质量"判据**；两物质教学布局下因 `nesp_isorropia=5` 的硬编码
（缺 NO3/Cl）走不通该路径，计数为 0（判据改用干质量/混合度）。

⇒ **决定性因素是无机物种集的完整度，不是"有没有 NH4"**：30 物种布局即使清空 NH4，仍有 Na/NO3/Cl/SO4
参与等衡 ⇒ 计数器有读数；两物质教学布局只有 SO4 ⇒ 平衡退化 ⇒ 计数为 0。
用 `Mass Cond` 作"冷凝判据"时先确认该布局的无机离子集足够（30 物种 baseline ✓；两物质教学布局 ✗）。
另记（**已排查，2026-09-30**）：清空 NH4 后 `Nub Coag` 相差三个数量级**不是计数器缺陷**——
`Nub Coag` = 凝并造成的粒子数变化的时间积分（`ModuleAdaptstep.f90:441` 逐档逐子步累加 `tmp=dtetr*(dn1dt+dn2dt)`）。
清空 NH4 同时去掉了**氨** ⇒ 三元成核停止（`Nub Nucl` 1.4865e14 → 0）、排放期超细爆发消失
（粒子数峰值 9.7e12 → 3.6e10）⇒ 凝并通量（∝N²）随之掉约四个数量级（实测 5e3，与 270² 同量级）。
连带：干质量增长 +52.3% → +36.3%、步数 743 → 318。
