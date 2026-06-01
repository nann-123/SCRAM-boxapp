# SCRAM BoxApp 报告依赖包

SCRAM BoxApp 现在包含一个内置离线 PDF 后端。普通用户只要点击“生成报告”，即使电脑没有安装 LaTeX，也可以生成 `internal_external_mixing_report.pdf`。

本目录中的 MiKTeX 安装包只用于需要 `.tex` 源文件精细排版或需要 LaTeX 后端的用户。

## 文件

- `basic-miktex-25.12-x64.exe`
  - 官方来源：MiKTeX Windows x64 basic installer
  - SHA-256：`14B42DD9F4B4A7813A8BFD69C8F99316C2888CC4EE26F631F397E163D85D6C62`

## 安装方法

1. 关闭 SCRAM BoxApp。
2. 双击 `basic-miktex-25.12-x64.exe`。
3. 建议选择“为当前用户安装”或默认安装方式。
4. 安装过程中允许 MiKTeX 自动安装缺失宏包。
5. 安装完成后重新打开 SCRAM BoxApp。
6. 回到“报告导出”页，重新点击“生成报告”。

## 仍然失败时

- 先确认普通 PDF 是否已生成。若已生成，说明内置离线后端正常，LaTeX 后端只是可选能力。
- 若 LaTeX 编译失败，打开报告日志中显示的 `xelatex_pass_*.log` 或 `tectonic.log`。
- 在 MiKTeX Console 中执行“Updates”和“Refresh file name database”后重试。
