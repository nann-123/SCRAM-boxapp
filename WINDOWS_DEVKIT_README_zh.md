# SCRAM BoxApp Windows 独立开发包说明

本开发包用于让学生在 Windows 上继续开发 SCRAM BoxApp。它不是普通用户安装包，而是一个可以复制、解压、建立 Python 环境、运行测试、继续修改代码并重新生成安装文件的教学开发包。

本文所有路径都以开发包根目录为起点，例如 `D:\SCRAMBoxApp-WinDevKit`。如果你把包解压到其他位置，只需要把命令中的路径理解为相对路径即可。

## 1. 开发包目录总览

```text
SCRAMBoxApp-WinDevKit\
  app\                                      GUI 和 Python 应用代码
  core\                                     SCRAM 配置、模板和 Windows 运行核心
  docs\                                     中文手册、测试报告、截图、实验结果图
  examples\                                 示例配置
  scripts\                                  启动、测试、截图、打包、依赖下载脚本
  third_party\report_dependencies\windows\  可选 LaTeX/MiKTeX 离线安装包
  README.md                                 项目原始说明
  WINDOWS_DEVKIT_README_zh.md               本说明
  WINDOWS_DEVKIT_MANIFEST.txt               本包文件清单
  pyproject.toml
  requirements.txt
```

开发包已经去掉 `.venv`、构建缓存、历史结果、临时 `RESULT/results`、`__pycache__`、`.obj/.mod` 等中间文件。学生拿到包以后应重新创建自己的 Python 虚拟环境。

## 2. GUI 代码位置

GUI 是用 Python 和 PySide6 写的，主要代码在 `app\`。

```text
app\main.py
```

GUI 程序入口。开发模式运行时最终会进入这里。

```text
app\views\main_window.py
```

主窗口代码，包含界面布局、按钮、标签页、表格、运行状态、结果页、帮助页等。多数界面按钮和控件行为都从这里开始查。

```text
app\i18n\zh_CN.json
app\i18n\en_US.json
```

中英文界面文字。修改界面显示文字时优先改这里，而不是把中文直接写死在 Python 代码里。

```text
app\resources\settings.json
```

默认界面设置。

```text
app\config_binding\config_model.py
```

SCRAM `.cfg` 配置文件的解析、校验、序列化和写回逻辑。新增配置字段、修改表格与 `.cfg` 的对应关系时重点看这里。

```text
app\services\template_service.py
```

实验模板读取和模板列表管理。

```text
app\services\run_service.py
```

模型运行核心调度。它负责找到 Windows 版 `ProgramSCRAM.exe`，把配置写入运行目录，调用 SCRAM 命令行程序，收集 internal mixing 与 external mixing 的输出，并写出汇总 CSV。

```text
app\services\plot_service.py
```

结果图生成逻辑，例如总数浓度、总质量、internal/external 相对差异图等。

```text
app\services\report_service.py
```

PDF 报告生成逻辑。软件优先尝试 LaTeX 后端；如果没有 LaTeX 或编译失败，会使用内置离线 PDF 后端。

```text
app\services\deployment_paths.py
```

平台路径管理。这里定义 Windows 用户配置目录、结果目录、缓存目录、运行时目录，以及如何按平台选择 `runtime\windows`。

## 3. SCRAM 核心代码位置

SCRAM 算法核心和 Windows 可执行程序都在：

```text
core\executables_or_wrappers\runtime\windows\
```

关键文件如下：

```text
core\executables_or_wrappers\runtime\windows\ProgramSCRAM.exe
```

Windows 版 SCRAM 命令行模拟核心。它不是 GUI，不能作为普通程序双击使用；GUI 会在后台调用它。

```text
core\executables_or_wrappers\runtime\windows\*.dll
```

`ProgramSCRAM.exe` 运行所需的 Fortran、NetCDF、HDF、压缩库和 C 运行库 DLL。移动开发包时必须保持这些 DLL 与 `ProgramSCRAM.exe` 在同一运行时目录中。

```text
core\executables_or_wrappers\runtime\windows\coef_s5_f3_b7.nc
```

SCRAM 使用的 NetCDF 系数数据文件。

```text
core\executables_or_wrappers\runtime\windows\INIT\
```

SCRAM 初始化文件目录，例如气溶胶初始浓度、排放、分数等数据。

```text
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\
```

SCRAM 原始核心源码。进阶学生如果要研究或重编底层算法，从这里开始。

常看的源码位置：

```text
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\SRC\ProgramSCRAM.f90
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\SRC\ModuleCoagulation.f90
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\SRC\ModuleCondensation.f90
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\SRC\ModuleRedistribution.f90
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\SRC\ModuleResultoutput.f90
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\SRC\rdb\
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\COEFF_REPARTITION\
```

其中 `ModuleCoagulation.f90` 主要涉及凝并过程，`ModuleCondensation.f90` 主要涉及凝结过程，`ModuleRedistribution.f90` 和 `SRC\rdb\` 与粒径分布重分配有关，`ModuleResultoutput.f90` 与输出结果有关。

## 4. 平台相关代码位置

本开发包只抽取 Windows 相关运行时和脚本。跨平台逻辑仍保留在 GUI 代码里，但包内重点是 Windows。

Windows 启动脚本：

```text
scripts\run_app_windows.bat
scripts\launch_app.py
```

`run_app_windows.bat` 是开发模式启动入口；`launch_app.py` 会检查平台运行时、准备 Python 环境并启动 GUI。

Windows 打包脚本：

```text
scripts\package_app_windows.bat
scripts\package_app_windows.ps1
```

它们会用 PyInstaller 生成 `SCRAM BoxApp.exe`，再生成便携 zip 和安装包。

Windows 报告依赖脚本：

```text
scripts\fetch_report_dependencies_windows.ps1
third_party\report_dependencies\windows\
```

用于准备可选 MiKTeX 离线安装包。普通 PDF 报告不强制依赖 LaTeX，因为软件已有内置 PDF 后端。

平台路径选择逻辑：

```text
app\services\deployment_paths.py
app\services\run_service.py
```

`deployment_paths.py` 负责判断当前平台是 `windows`、`linux` 还是 `mac`；`run_service.py` 根据这个结果寻找：

```text
core\executables_or_wrappers\runtime\windows\ProgramSCRAM.exe
```

## 5. 第一次配置开发环境

建议把开发包解压到英文路径，例如：

```text
D:\SCRAMBoxApp-WinDevKit
```

打开 PowerShell，进入开发包根目录：

```powershell
cd D:\SCRAMBoxApp-WinDevKit
```

在**项目根目录**创建虚拟环境（这是标准位置，方便后续打包和 CESM 耦合）：

```powershell
py -3.12 -m venv .venv
```

如果没有 `py -3.12`，使用：

```powershell
python -m venv .venv
```

安装 Python 依赖：

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

> **说明**：启动脚本 `launch_app.py` 查找 Python 的顺序为：
> 1. `SCRAM_PYTHON` 环境变量（如果设置了）
> 2. 项目根目录的 `.venv`（推荐位置）
> 3. `core\executables_or_wrappers\runtime\windows\.venv`（旧版兼容）
> 4. 都没找到则在根目录自动创建
>
> 因此只要按上面步骤在根目录创建 `.venv`，直接运行启动脚本即可，**无需额外设置环境变量**。

启动 GUI：

```powershell
scripts\run_app_windows.bat
```

如果 GUI 能打开，说明 Python 环境、PySide6、SCRAM Windows 运行核心都已经基本可用。

## 6. 运行标准测试

每次修改代码后，至少运行一次标准测试：

```powershell
.\.venv\Scripts\python scripts\run_standard_tests.py --template gmd_paris_full --case gmd_paris_full --output-root install_logs\standard_tests
```

测试会检查：

- Python 包能否导入。
- GUI 能否在离屏模式下创建窗口并载入模板。
- `ProgramSCRAM.exe` 是否存在且能被调用。
- internal mixing 与 external mixing 两套假设是否都能完成运行。
- 是否生成 `performance_summary.csv`。
- 是否生成 `final_state_summary.csv`。
- 是否生成关键 PNG 结果图。
- PDF 报告是否能生成；没有 LaTeX 时会走内置离线 PDF 后端。

测试输出在：

```text
install_logs\standard_tests\
```

测试成功时终端会看到类似：

```text
import_smoke: ok
gui_smoke: ok
runtime_smoke: ok
standard_tests: ok
```

如果只想快速测试模型运行和绘图，不测试报告，可加：

```powershell
.\.venv\Scripts\python scripts\run_standard_tests.py --template gmd_paris_coagulation --case coag_only --output-root install_logs\quick_test --skip-report
```

## 7. 生成手册截图

如果修改了 GUI 布局、按钮、文字或结果页，应重新生成截图：

```powershell
.\.venv\Scripts\python scripts\capture_screenshots.py
```

截图会写入：

```text
docs\screenshots\
```

用户手册和教学手册中的截图资产主要在：

```text
docs\user_manual_zh_assets\
docs\undergrad_lab_assets\
```

## 8. 生成普通用户软件和安装包

开发完成后，在开发包根目录运行：

```powershell
scripts\package_app_windows.bat
```

等价的 PowerShell 命令是：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\package_app_windows.ps1
```

该脚本会自动完成 venv 检查、依赖安装、运行时复制、PyInstaller 打包和安装包生成。

> **前提**：需先完成第 5 节的环境配置（项目根目录已有 `.venv` 且依赖已安装）。

成功后得到：

```text
dist\windows\SCRAM BoxApp\SCRAM BoxApp.exe
dist\windows\SCRAMBoxApp-windows-x64.zip
dist\windows\SCRAMBoxApp-Setup-windows-x64.exe
```

给普通用户使用时，优先分发：

```text
dist\windows\SCRAMBoxApp-Setup-windows-x64.exe
```

它会安装到：

```text
%LOCALAPPDATA%\Programs\SCRAM BoxApp
```

并创建桌面快捷方式和开始菜单快捷方式。

如果只想生成便携 zip，不生成安装包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\package_app_windows.ps1 -SkipInstaller
```

## 9. 关于 SCRAM 核心重新编译

普通 GUI 开发不需要重新编译 SCRAM 核心，因为本包已经包含可运行的：

```text
core\executables_or_wrappers\runtime\windows\ProgramSCRAM.exe
```

如果学生要修改 Fortran/C/C++ 核心算法，才需要重编。源码位置是：

```text
core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\
```

重新编译通常需要额外安装：

- MinGW-w64 或 MSYS2。
- `gfortran`。
- C/C++ 编译器。
- NetCDF C 和 NetCDF Fortran 开发库。
- HDF5 开发库。
- 与当前 `ProgramSCRAM.exe` 对应的运行时 DLL。

当前开发包没有把完整 Windows Fortran 编译链封装成一键脚本；教学开发建议先把 GUI、模板、结果分析和报告作为主要开发内容。若确实要重编核心，建议教师先统一准备 MSYS2/MinGW-w64 环境，再把新生成的 `ProgramSCRAM.exe` 和所需 DLL 覆盖到：

```text
core\executables_or_wrappers\runtime\windows\
```

覆盖后必须重新运行标准测试。

## 10. 模板和实验配置位置

内置模板在：

```text
core\templates\
```

默认配置在：

```text
core\defaults\default_config.cfg
```

配置结构说明在：

```text
core\schema\config_schema.json
docs\config_mapping_spec.md
```

如果新增本科实验题目，建议流程是：

1. 复制一个现有模板。
2. 改模板中的过程开关、初始质量、排放或环境参数。
3. 用 GUI 载入模板，确认表格显示正常。
4. 运行 internal/external mixing 对比。
5. 检查输出 CSV 和图像是否符合物理预期。
6. 把新的结果截图或图像写入教学手册。

## 11. 结果输出位置

GUI 运行时结果写入「设置」页指定的输出目录：

```text
{输出目录}/single/{实验名称}_{案例预设}/      ←「运行」单个假设
{输出目录}/compare/{实验名称}_{案例预设}/     ←「比较」两种假设
```

案例预设不匹配时仅用实验名称，不加预设后缀。每次运行自动保存 `experiment_config.cfg` 到输出目录，方便事后追溯参数。

标准测试（CLI）结果强制写入 `install_logs/`，由 `--output-root` 参数指定，防止误删用户数据。

打包后的普通用户软件会把用户结果写到 Windows 用户数据目录下，核心路径由下面文件决定：

```text
app\services\deployment_paths.py
```

常见结果文件：

```text
performance_summary.csv
final_state_summary.csv
figures\runtime_comparison.png
figures\final_mass_comparison.png
figures\final_number_comparison.png
figures\*_relative_mass_vs_external.png
figures\*_relative_number_vs_external.png
```

`final_state_summary.csv` 需要同一个实验同时完成 internal mixing 与 external mixing，才能进行最终状态对比。

## 12. 报告和 LaTeX 依赖

软件可以不装 LaTeX 直接生成 PDF，因为有内置离线 PDF 后端。

如果希望使用 LaTeX 后端，可安装包内的 MiKTeX：

```text
third_party\report_dependencies\windows\basic-miktex-25.12-x64.exe
```

安装说明见：

```text
third_party\report_dependencies\windows\README_REPORT_DEPENDENCIES_zh.md
docs\report_dependencies_windows.md
```

如果 LaTeX 后端失败，报告模块会自动退回内置 PDF 后端。对应代码在：

```text
app\services\report_service.py
```

## 13. 重新生成本开发包

如果教师或助教在完整项目中继续修改后，需要重新抽取 Windows 开发包，运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_windows_devkit.ps1
```

输出为：

```text
dist\win-devkit\SCRAMBoxApp-WinDevKit\
dist\win-devkit\SCRAMBoxApp-WinDevKit.zip
```

如果想生成不带 MiKTeX 安装包的小体积开发包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_windows_devkit.ps1 -SkipReportDependencies
```

## 14. 常见问题

GUI 闪退：不要直接双击 `.py` 文件。用 PowerShell 运行 `scripts\run_app_windows.bat`，看终端错误信息。

中文乱码：优先打开 `WINDOWS_DEVKIT_README_zh.md`。这个文件在生成时写为 UTF-8 BOM，旧版 Windows 记事本也应能正确识别。

找不到 Python：安装 Python 3.10+，或者设置：

```powershell
$env:SCRAM_PYTHON = "D:\你的路径\.venv\Scripts\python.exe"
```

找不到 SCRAM 核心：检查：

```text
core\executables_or_wrappers\runtime\windows\ProgramSCRAM.exe
```

结果图没有生成：先确认标准测试是否通过，再检查 `install_logs\...\stdout.log`、`stderr.log` 或 GUI 运行监视器。

打包失败并提示找不到 C# 编译器：安装 Visual Studio Build Tools 或 .NET Framework Developer Pack；也可以先用 `-SkipInstaller` 只生成便携 zip。

打包后双击 `ProgramSCRAM.exe` 没反应：这是正常的。普通用户应该运行 `SCRAM BoxApp.exe` 或安装包创建的快捷方式。

## 15. 建议分工

GUI 方向学生：主要看 `app\views\main_window.py`、`app\i18n\`、`app\services\settings_service.py`。

模型运行方向学生：主要看 `app\services\run_service.py`、`app\services\template_service.py`、`core\templates\`、`core\defaults\`。

结果分析方向学生：主要看 `app\services\plot_service.py`、`app\services\report_service.py`。

底层算法方向学生：主要看 `core\executables_or_wrappers\runtime\windows\source\SCRAM1.1\`。

打包发布方向学生：主要看 `scripts\package_app_windows.ps1`、`scripts\make_windows_devkit.ps1`、`third_party\report_dependencies\windows\`。
