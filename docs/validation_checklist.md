# Validation Checklist

## Windows Desktop App

- [x] GUI starts in offscreen smoke mode on Windows.
- [x] Default new experiment opens the non-zero `gmd_paris_full` Greater Paris scenario D template.
- [x] Loading `core/templates/baseline12h.cfg` preserves species `init_gas` and initial mass values in the GUI tables.
- [x] Output directory can be changed from the experiment tab and from the settings tab.
- [x] Pressure spinner uses a practical `1000 Pa` step instead of the previous `1900 Pa` range-derived step.
- [x] Internal/external comparison runs through `RunService` and writes both result branches.
- [x] Generated figures include distinguishable line styles for overlapping internal and external curves.
- [x] Plot generation writes final mass, final number, runtime, time-series, relative-difference, and external mixing-state figures.
- [x] Report generation now surfaces TeX compiler failures and missing PDF output in the GUI instead of silently failing.
- [x] Report generation has a built-in offline PDF fallback when LaTeX is absent or broken.
- [x] Optional Windows LaTeX dependency installer is provided under `dist/windows/dependencies/`.
- [x] Windows package resources can stage the bundled runtime and complete the standard comparison.
- [x] Windows installer creates a double-clickable application with Start Menu/Desktop shortcuts.

## Scientific Workflow

- [x] User-facing comparison target is internal mixing vs external mixing.
- [x] External mixing outputs include mixed fraction and mixed/unmixed mass by size.
- [x] Greater Paris scenario D is the primary standard experiment for the manual and smoke tests.
- [x] Summary CSV columns use `relative_difference_vs_external_*` for internal/external comparison.
- [x] Old nearest/legacy language is kept only where it describes lower-level historical implementation details.

## 2026-09-29/30 batch（SCRAM1.2 核 + 输入护栏 + 预览一致性）

- [x] Windows 运行时为 SCRAM1.2 构建：`scripts/check_runtime_version.py` 退出码 0（1.2 标记命中）。
- [x] Windows 版 1.2 核以 16 MB 栈保留链接（`SConstruct` 加 `-Wl,--stack,16777216`）—— 默认 2 MB 栈在 `-O2` 下初始化阶段段错误（同源码 `-O0` 可跑完）。
- [x] 运行时目录自包含：MSYS2 依赖闭包（85 个 DLL）与 `ProgramSCRAM.exe` 同目录，脱离 MSYS2 环境可直接运行。
- [x] 零质量输入（逐档质量全 0 而粒子数非 0）被 `validate()` 拦下并给出可读原因。
- [x] 论文验证模式（`nucl_model=5`）自动锁定 30 物种 baseline 布局（2 号=BC/组 4、4 号=SO4/组 1）；布局不符时 `validate()` 报错。
- [x] `(tag_init=0, tag_external=0, n_frac>1)` 未定义组合被 `validate()` 拦下（1.1 核在该组合上读未初始化内存）。
- [x] 「初值来源」可在结构编辑页切换（`tag_init`）；选 0 时逐档质量表置灰、写入器发 5 列短格式 cfg，三个内置场景产生不同终态（实测 18.7287 / 18.7743 / 18.8221）。
- [x] 载入坏配置时立即弹出问题清单（仍允许载入，便于就地修改）；运行前闸门保持：有错不启动。
- [x] 预览框显示"实际送核"的配置（头注列出被改写的项与两臂差异项），任一控件变更即时刷新。
- [x] 中文案例名/实验名不再产生非 ASCII 路径（目录名 ASCII 化 + 短哈希）。
- [x] 混合假设下拉初值按 `n_frac` 反推、可手动切换（不再静默弹回）。
- [x] `docs/baseline_scram12.json` 为 1.2 数值基线（4 模板 × 2 臂，重复性逐位一致）。
- [x] 发布包不含开发文件：打包脚本带白名单校验（发现 `undobug.md`/`BUG_TRACKING.md`/`scripts`/`source`/`*.pyc` 等即中止）。

## 2026-09-30 第二批（结果布局 v2 + 报告 + 打包）

- [x] 结果布局 v2：一个实验一个目录（`<根>/<实验名>/{case.json,figures,csv,<臂>/…}`），无 `runs/<案例>/` 套娃、无 `single/compare` 模式层、臂级无空 `figures/`。
- [x] 重跑不再丢数据：旧结果整目录搬进 `<根>/history/<实验名>_<时间戳>/`（同盘 rename，默认留 3 份，`SCRAM_CASE_HISTORY_KEEP` 可调）；界面「运行记录」以 `[历史]` 前缀列出。
- [x] 默认结果根去掉了 `internal_external_mixing` 层（`<state>/scram_boxapp_mixing/results`），旧设置值自动迁移。
- [x] 报告落在所选实验目录（`<案例>/report/<案例>_report.pdf`），不同实验各自一份；报告目录只留 tex/pdf，高清图 300 dpi 重绘到临时目录、嵌完即删。
- [x] 报告 PDF 插图按原图 1:1 嵌入（内嵌位图 2400×1350 / 截图 1600×1020），放大 3 倍轴标签清晰。
- [x] 界面提示去掉内部编号与内核黑话（19 条 zh/en 同步改写；下拉标签不再带 `tag_init=1` 之类字段名）。
- [x] `docs/screenshots/*.png` 重抓（含两本手册资产），手册 PDF 重出。
- [x] 案例目录瘦身：默认丢弃 `coag_delta_*` 调试转储（36 个案例目录合计 432 MB → 42 MB；`SCRAM_KEEP_COAG_DELTAS=1` 可留）。
- [x] 发布闸门 `run_standard_tests.py --require-core-1.2` 全绿；内核 md5 `6f7cd2e1…` 与基线锚点一致；`collect_baseline` 复采 8 行与 `docs/baseline_scram12.json` **逐位一致**、两遍重复逐位一致。
- [x] 发布测试逮到并修掉两个打包缺陷：① PyInstaller 6.x 下 `--add-data` 把 `config_schema.json` 建成了**目录**（运行时 PermissionError）；② teaching 基座 `examples/configs` 未进包（两个教学模板 FileNotFoundError）。
- [x] 打包脚本新增**发布自检**：打包完成后自动用打包版 exe 跑"载入全部 8 个模板 + 一次最快对比算例"，失败即中止打包；本次从干净环境（先删暂存运行时）跑通。
- [x] 便携 zip 解包后同样跑通自检（8 模板 + 算例 ok + 11 图）。
