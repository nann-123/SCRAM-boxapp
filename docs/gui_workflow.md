# GUI Workflow

1. 启动软件，默认进入 `gmd_paris_full` Greater Paris 场景 D。这个模板包含非零初始质量、气相浓度和排放数据，适合作为标准实验起点。
2. 顶部工具栏可以直接执行：新建实验、载入实验、保存实验、运行当前混合假设、比较 internal/external、停止、查看结果、导出报告。
3. 在 `实验设置 / Experiment Setup` 页面中选择模板、案例预设和混合假设。可选混合假设为 `INTERNAL_MIXING` 与 `EXTERNAL_MIXING`。
4. 根据实验需要调整凝并、冷凝/蒸发、成核开关，以及模拟时长、最小时间步、温度、压力、湿度和输出目录。
5. 在 `结构编辑 / Structure Editor` 页面中检查或修改 `Species`、`Size bins`、`Fraction`、`Emission`、`Initial mass` 表格。载入 cfg 后，初始气相浓度和初始质量矩阵应直接回填到表格。
6. 点击 `运行当前混合假设` 可只运行当前选择；点击 `比较 internal / external` 会连续运行两种混合假设并生成对比结果。
7. 在 `运行监控 / Run Monitor` 页面观察 wall-clock、模拟推进时间、ETA、总质量、总数浓度、平均粒径、active bins/pairs、日志和最新输出文件。
8. 在 `结果分析 / Results Analysis` 页面查看 internal/external 摘要卡片、图表、CSV 和日志。若两条曲线接近重叠，应通过颜色和线型区分。
9. 在 `报告导出 / Report` 页面勾选要纳入报告的图表并生成 PDF。普通 PDF 使用内置离线后端即可生成；若 LaTeX 编译失败，界面日志会给出原因和可选 MiKTeX 安装包位置。
