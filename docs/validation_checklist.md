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
