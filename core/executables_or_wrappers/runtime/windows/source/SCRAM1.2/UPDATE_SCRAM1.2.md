# SCRAM1.2 更新说明

更新日期：2026-09-18。服务器：zju60。模型路径：`/home/wangfangyuan/SCRAM1.2`。

从 `/home/wangfangyuan/SCRAM1.1` 完整复制后更新，原模型保持不变。参考源为公开发布包 `cesm-scram-optics-20260915-r2`，CAM科学源码 `e6ef92321df7362812aed55bc5461f14ba6dd081`。

## 当前正式迁移范围

1. 动态凝并产物再分配，不读取预计算再分配系数；按实际导数阶段的子步累计限制数/物种质量净损失。凝并守恒各物种质量，每次事件减少一个颗粒。
2. moving-center dual-pivot 粒径重分布，数和质量采用各自的权重，同时检查总数与各物种质量守恒。水随颗粒迁移，但不参与干体积几何；避免通过强制修正粒径重新生成数浓度。
3. 单颗粒凝结传质改用 Kn=6D/(v d) 和全区间连续 Fuchs–Sutugin 公式；Kelvin指数上限500，非正分母返回系数1。
4. 凝结湿密度采用 `总湿质量浓度/(数浓度×单颗粒湿体积)`，以1e9从 μg/μm³ 转为 kg/m³。初始化完整局部数组，保护无效粒径、零颗粒数、零凝结汇和零时间步。有机物Kelvin修正也使用局部湿密度，但不替换原有有机物分配机制。
5. 默认gfortran编译，补入显式Fortran模块顺序和源依赖，避免并行或增量编译遗留错误接口。

恢复并保留独立盒模型的原物种定义、热力学、有机物闭合、气体宿主、组成网格、数值阈值和凝并核刷新流程。没有默认引入五档VBS，也没有强制关闭ISORROPIA。过度迁移的CESM配置、宿主接口、实验代码及备份已删除。当前目录仅保留独立盒模型及其有效验证代码。

本版不宣称与整个CESM耦合模型科学机制/输出完全等价；目的是迁移独立适用的核心改进。化学方案、入口状态处理和有效密度策略存在明确差异，不能用单个例程一致替代整体机制验证。

## 默认运行

在模型目录使用原INIT配置，例如：

```bash
cd /home/wangfangyuan/SCRAM1.2
./ProgramSCRAM INIT/cfg_megapole_01072009.cfg
```

默认动态nearest凝并、moving-center重分布；可显式设置 `SCRAM_COEFF_REPARTITION_MODE=nearest` 和 `SCRAM_REDISTRIBUTION_MODE=moving_center_dualpivot`。旧的数值重分布编号保持含义，现代算法覆盖编号>=2的尺寸再分布。历史weighted/cache及legacy试验代码保留，但不等于严格旧版复现；复现SCRAM1.1请使用原目录。

## 编译与验证

```bash
scons -c
FC=gfortran scons -j4 mode=safe
python3 tests/run_portable_validation12.py
python3 tests/run_validation.py --seconds 43200
```

调试编译使用 `mode=debug`。正式程序采用safe（O2且禁用fast-math）。验证在独立validation子目录运行，不覆盖原输入或旧版结果。

当前范围修正后的验证记录：

- `validation/SCOPE_BUILD_DEBUG.log`、`validation/SCOPE_BUILD_SAFE.log`：编译日志。
- `validation/SCOPE_CORE_DEBUG.log`、`validation/SCOPE_CORE_SAFE.log`：201个传质/Kelvin/重分布原始例程对照场景，以及4个独立硫酸凝结边界/解析预算场景。
- `validation/SCOPE_BOX_DEBUG.log`、`validation/SCOPE_BOX_SAFE.log`：100组重分布、6组凝并守恒/正性测试，及原external/internal/cond_only配置的12小时运行。
- `validation/SCOPE_REVIEW_RECEIPT.json`：最终编译、测试及原始模型哈希核对结果。

这些测试验证局部算法、守恒/非负性和既有个例可运行性，不代表所有环境条件或长期科学性能已经验证。Kn公式和密度修正会改变凝结结果，不能把当前输出当成SCRAM1.1逐位复现。

## 目录清理（2026-09-18）

已删除过度迁移备份、实验目录、临时上传目录、旧实验测试和失效编译文件；不再保留CESM配置入口。保留三个数值对照参考文件仅供测试，不参与模型编译。原有输入、科学数据和历史结果未作删除。

清理后的重新验证：safe完整重编译、311个核心测试、3个原INIT配置各600秒运行全部通过；日志为 `validation/CLEAN_BUILD_SAFE.log`、`CLEAN_CORE_SAFE.log`、`CLEAN_BOX_SAFE.log`，当前验收记录为 `validation/CLEAN_RECEIPT.json`。上述SCOPE记录仅为清理前独立模型的历史验证。原SCRAM1.1的79个源码/输入哈希再次核对无变化。
