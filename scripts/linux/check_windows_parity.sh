#!/usr/bin/env bash
#
# Windows 口径守卫 —— 确保 Linux 侧的调试不会悄悄改变 Windows 发布口径。
#
#   bash scripts/linux/check_windows_parity.sh
#
# 背景：调试在 Linux、打包发布在 Windows。Linux 侧的工作不得改动 Windows 运行时产物、
# 不得破坏源码里的 Windows 分支、不得进入 Windows 打包白名单、不得让 Linux 生成的
# 截图/文档资产冒充发布资产。
#
# 硬失败（exit 1）：Windows 运行时被改动、源码 Windows 分支丢失、Linux 文件混入
#                    Windows 打包白名单或运行时目录。
# 警告（exit 0）：版本号/验收清单/截图资产有改动 —— 需要人工确认后再进发布。

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
HARD=0
WARN=0
fail() { printf 'HARD FAIL  %s\n' "$*"; HARD=1; }
warn() { printf 'WARN       %s\n' "$*"; WARN=1; }
ok()   { printf 'ok         %s\n' "$*"; }

WIN_RUNTIME="core/executables_or_wrappers/runtime/windows"
SRC_DIR="$WIN_RUNTIME/source/SCRAM1.1/SRC"
DEVKIT_PS="scripts/make_windows_devkit.ps1"
PACKAGE_PS="scripts/package_app_windows.ps1"

echo "== 1. Windows 运行时产物未被改动 =="
WIN_CHANGED="$(git status --porcelain -- "$WIN_RUNTIME" 2>/dev/null | awk '{print $NF}')"
if [ -z "$WIN_CHANGED" ]; then
  ok "runtime/windows 与提交一致"
else
  # 只允许文档（README）变更；exe/DLL/源码等内容一律硬失败
  NON_DOC="$(printf '%s\n' "$WIN_CHANGED" | grep -vE '(\.md|README)$' || true)"
  if [ -n "$NON_DOC" ]; then
    fail "$WIN_RUNTIME 下有非文档改动（exe/DLL/源码不能由 Linux 侧改动；仅 *.md 与 README 可改）："
    printf '%s\n' "$NON_DOC" | sed 's/^/             /'
  else
    warn "runtime/windows 下仅文档变更（允许，但需人工确认）："
    printf '%s\n' "$WIN_CHANGED" | sed 's/^/             /'
  fi
fi

echo "== 2. 源码中的 Windows 分支仍然存在 =="
F90="$SRC_DIR/ModuleCoeffRepartitionBoxmodel.f90"
if grep -q 'cmd /c if not exist' "$F90" 2>/dev/null; then
  ok "coeff_make_dir 的 Windows 命令分支保留"
else
  fail "coeff_make_dir 的 Windows 分支丢失（Windows 端将无法创建输出目录）"
fi
if grep -q "get_environment_variable" "$F90" 2>/dev/null; then
  ok "平台判断（环境变量探测）仍在"
else
  warn "未检出平台判断；请确认 Windows 分支仍会被走到"
fi

echo "== 3. Windows 打包白名单未混入 Linux 文件 =="
for f in build_runtime.sh check_windows_parity.sh; do
  if grep -q -- "$f" "$DEVKIT_PS" "$PACKAGE_PS" 2>/dev/null; then
    fail "Windows 打包脚本引用了 Linux 专有文件：$f"
  fi
done
if grep -qE 'runtime[\\/]linux' "$DEVKIT_PS" "$PACKAGE_PS" 2>/dev/null; then
  fail "Windows 打包脚本引用了 runtime/linux 目录"
else
  ok "Windows 打包脚本只取 runtime\\windows，未引用 Linux 运行时"
fi

echo "== 4. 本轮改动范围审查 =="
CHANGED="$(git status --porcelain | awk '{print $NF}')"
if [ -z "$CHANGED" ]; then
  ok "工作区干净"
else
  printf '%s\n' "$CHANGED" | sed 's/^/             /'
  # 允许 Linux 侧自由改动的路径
  ALLOWED='^(install_logs/|dist/|docs/(checktest|linux_debugging/|BUG_TRACKING\.md)|scripts/linux/|core/executables_or_wrappers/runtime/linux/)'
  OUTSIDE="$(printf '%s\n' "$CHANGED" | grep -vE "$ALLOWED" || true)"
  if [ -n "$OUTSIDE" ]; then
    warn "以下改动在 Linux 侧「允许集合」之外，需人工确认是否影响 Windows 发布口径："
    printf '%s\n' "$OUTSIDE" | sed 's/^/             /'
  fi
fi

echo "== 5. 发布元数据是否被 Linux 单方面推进 =="
if ! git diff --quiet HEAD -- pyproject.toml 2>/dev/null; then
  warn "pyproject.toml 有改动（版本号只能作为提案，需 Windows 侧验证后才可发布）"
fi
if ! git diff --quiet HEAD -- docs/validation_checklist.md 2>/dev/null; then
  warn "validation_checklist.md 有改动：Windows 专有项不得在 Linux 上勾选"
fi
if ! git diff --quiet HEAD -- docs/screenshots 2>/dev/null; then
  warn "docs/screenshots 有改动：Linux 字体渲染与 Windows 不同，发布用截图应在 Windows 重生成"
fi

echo
if [ "$HARD" -ne 0 ]; then
  echo "结论：FAIL —— 存在破坏 Windows 发布口径的改动，本轮不得通过。"
  exit 1
fi
if [ "$WARN" -ne 0 ]; then
  echo "结论：WARN —— 未破坏 Windows 口径，但有事项需人工确认（见上）。"
  exit 0
fi
echo "结论：PASS —— Windows 发布口径未受影响。"
