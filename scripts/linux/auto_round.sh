#!/usr/bin/env bash
#
# 分层轮次运行器：按调度频率选择深度，并用内容签名跳过"什么都没变"的轮次。
#
#   bash scripts/linux/auto_round.sh [quick|standard|deep] [safe|debug] [--force]
#
#   quick     轻量哨兵（建议每 15–30 分钟）：只跑 Windows 口径守卫 + 生成候选探测清单
#   standard  常规回归（建议每小时）：守卫 + 增量构建 + 快速测试 + 指标对比
#   deep      深度轮次（建议每晚）：再叠加完整标准测试 + 端到端流水线 + 候选探测清单
#
# 签名 = commit + 核心二进制 md5 + 产品面（app/core/scripts）工作区哈希。签名未变且非 deep 时跳过本轮
# （这是防止"机械重复跑同样的测试"的机制；--force 可强制跑）。
#
# 产出：install_logs/auto/<YYYYmmdd-HHMM>/（见各 Phase）与滚动的 install_logs/auto/digest.md
# 退出码：0 = PASS，1 = WARN，2 = FAIL。

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TIER="standard"
MODE="safe"
FORCE=0
FORCE_SHOTS=0
for arg in "$@"; do
  case "$arg" in
    quick|standard|deep) TIER="$arg" ;;
    safe|debug) MODE="$arg" ;;
    --force) FORCE=1 ;;
    --shots) FORCE_SHOTS=1 ;;
    *) echo "usage: auto_round.sh [quick|standard|deep] [safe|debug] [--force] [--shots]" >&2; exit 2 ;;
  esac
done

STAMP="$(date +%Y%m%d-%H%M%S)"   # 含秒，避免同分钟内两层轮次相撞
ROUND="$ROOT/install_logs/auto/$STAMP"
mkdir -p "$ROUND"
PY="$ROOT/.venv/bin/python"
EXE="$ROOT/core/executables_or_wrappers/runtime/linux/ProgramSCRAM"

# --- 轮次签名：无变化则跳过（deep 除外）-------------------------------------
# 签名第三段只看「产品面」改动（app/ core/ scripts/）。docs/ 与 proposals/ 不计入：
# 否则 agent 自己 git add 文档就会让轮次"变新"——白跑构建、还丢掉与上一轮的基线对比（2026-09-12 复核 §0.4-2）。
SIG="$(git rev-parse --short HEAD)-$(md5sum "$EXE" 2>/dev/null | cut -c1-8)-$(git status --porcelain -- app core scripts | md5sum | cut -c1-8)"
LAST="$(cat "$ROOT/install_logs/auto/.last_signature" 2>/dev/null || echo none)"
if [ "$SIG" = "$LAST" ] && [ "$FORCE" -eq 0 ] && [ "$TIER" != "deep" ]; then
  rmdir "$ROUND" 2>/dev/null
  echo "无变化（签名 $SIG 与上轮相同）→ 跳过 $TIER 轮次；如需强制：--force"
  exit 0
fi

echo "== 轮次：$ROUND（tier=$TIER, mode=$MODE）=="

# --- Phase 0: 起点快照 -------------------------------------------------------
{
  echo "round: $STAMP"; echo "tier: $TIER"; echo "build mode: $MODE"
  echo "signature: $SIG"; echo "started: $(date -Is)"; echo
  echo "--- git log -1 ---"; git log --oneline -1
  echo; echo "--- git status --short ---"; git status --short
  echo; echo "--- git diff --cached --stat ---"; git diff --cached --stat
  echo; echo "--- origin/main..HEAD ---"; git log --oneline origin/main..HEAD 2>/dev/null || true
} > "$ROUND/git.txt" 2>&1

# --- Phase 0.5: Windows 口径守卫（所有层都跑）--------------------------------
bash "$ROOT/scripts/linux/check_windows_parity.sh" > "$ROUND/windows_parity.txt" 2>&1
PARITY=$?
echo "-- 守卫退出码=$PARITY"

# --- Phase 0.7: 候选探测清单（所有层都生成，交给 agent 选）-------------------
"$PY" scripts/linux/probe_suggest.py --limit 8 > "$ROUND/next_probes.md" 2>&1
echo "-- 候选探测已写入 next_probes.md"

# --- quick 层到此为止 --------------------------------------------------------
if [ "$TIER" = "quick" ]; then
  cp -f "$ROOT/install_logs/auto/latest/baseline.json" "$ROUND/baseline.json" 2>/dev/null || true
  ln -sfn "$STAMP" "$ROOT/install_logs/auto/latest"
  printf -- "- %s | quick | 哨兵通过 | 守卫=%s\n" "$STAMP" "$PARITY" >> "$ROOT/install_logs/auto/digest.md"
  echo "== quick 轮次结束（未跑构建与测试）=="
  exit 0
fi

# --- Phase 1: 构建 -----------------------------------------------------------
bash "$ROOT/scripts/linux/build_runtime.sh" "$MODE" > "$ROUND/build.log" 2>&1
BUILD=$?
MD5="$(md5sum "$EXE" 2>/dev/null | awk '{print $1}')"
echo "-- 构建退出码=$BUILD  md5=$MD5"

# --- Phase 2: 标准测试 -------------------------------------------------------
"$PY" scripts/run_standard_tests.py \
    --template gmd_paris_coagulation --case coag_only \
    --output-root "$ROUND/quick_test" --skip-report > "$ROUND/quick_test.log" 2>&1
echo "-- 快速测试退出码=$?"

if [ "$TIER" = "deep" ]; then
  "$PY" scripts/run_standard_tests.py \
      --template gmd_paris_full --case gmd_paris_full \
      --output-root "$ROUND/standard_tests" > "$ROUND/standard_tests.log" 2>&1
  echo "-- 完整标准测试退出码=$?"
else
  # standard 层也要有可供指标采集的产物：复用快速测试结果目录
  mkdir -p "$ROUND/standard_tests"
  cp -r "$ROUND/quick_test/." "$ROUND/standard_tests/" 2>/dev/null || true
  cp -f "$ROUND/quick_test.log" "$ROUND/standard_tests.log" 2>/dev/null || true
fi

# --- Phase 3: 端到端流水线（仅 deep）-----------------------------------------
if [ "$TIER" = "deep" ]; then
  "$PY" scripts/run_pipeline.py > "$ROUND/pipeline.log" 2>&1
  echo "-- 流水线退出码=$?"
  # 把最新结果图另存一份，便于与 docs/*_assets 的手册图对比（手册图目前靠人工拷贝）
  # 注意实际布局是 results/<实验名>/figures；旧写法 results/*/*/figures 深度不匹配，会静默取空
  RESULTS="$(ls -dt "$HOME"/.local/state/scram_boxapp_mixing/results/*/figures \
                      "$HOME"/.local/state/scram_boxapp_mixing/results/*/*/figures 2>/dev/null | head -1)"
  if [ -n "$RESULTS" ]; then
    mkdir -p "$ROUND/figures" && cp -f "$RESULTS"/*.png "$ROUND/figures/" 2>/dev/null
    echo "-- 已另存结果图 $(ls -1 "$ROUND/figures" 2>/dev/null | wc -l) 张到 figures/（供与 docs/*_assets 对比）"
  fi
fi

# --- Phase 2.5: 截图（仅当 GUI 改动晚于截图时，按 devkit §7）------------------
# §7：只有改了 GUI 布局/按钮/文字/结果页才需要重生成截图。这里用 git 时间戳复现该判据；
# 生成的是**检查用**副本（写到轮次目录），发布资产仍需在 Windows 上生成。
SHOTS=99  # 99 = 未触发
APP_T="$(git log -1 --format=%ct -- app/ 2>/dev/null || echo 0)"
SHOT_T="$(git log -1 --format=%ct -- docs/screenshots/ 2>/dev/null || echo 0)"
if [ "$FORCE_SHOTS" = "1" ] || { [ "${APP_T:-0}" -gt 0 ] && [ "${SHOT_T:-0}" -gt 0 ] && [ "$APP_T" -gt "$SHOT_T" ]; }; then
  "$PY" scripts/capture_screenshots.py --out "$ROUND/screenshots" > "$ROUND/screenshots.log" 2>&1
  SHOTS=$?
  echo "-- §7 触发（GUI 改动晚于截图）：已生成检查用截图，退出码=$SHOTS（写在轮次目录，不覆盖发布资产）"
else
  echo "-- §7 未触发：GUI 自上次截图生成以来未改动，本轮不生成截图（要强制用 --shots）"
fi

# --- Phase 3.5: 资产完整性（P9）---------------------------------------------
"$PY" scripts/linux/check_assets.py > "$ROUND/asset_check.log" 2>&1
ASSETS=$?
echo "-- 资产检查退出码=$ASSETS（0=干净 3=仅已知项 1=有新增告警 2=硬失败，见 asset_check.log）"

# --- Phase 4: 指标采集与对比 -------------------------------------------------
# deep 轮额外与「最近一次 deep 轮的基线」对比：同层级、同案例才可比，否则只打印 INFO 不告警
if [ "$TIER" = "deep" ]; then
  "$PY" scripts/linux/collect_metrics.py --round-dir "$ROUND" \
      --deep-baseline "$ROOT/install_logs/auto/deep_baseline.json" > "$ROUND/metrics.log" 2>&1
else
  "$PY" scripts/linux/collect_metrics.py --round-dir "$ROUND" > "$ROUND/metrics.log" 2>&1
fi
METRICS=$?
sed 's/^/   /' "$ROUND/metrics.log" | tail -12

# --- Phase 7: 报告骨架 + digest + latest 指针 --------------------------------
{
  echo "# 轮次报告 $STAMP（tier=$TIER）"
  echo
  echo "- 构建模式：$MODE　签名：$SIG"
  echo "- §7 截图触发：$([ "$SHOTS" = 99 ] && echo 否 || echo 是（生成码 $SHOTS）)"
  echo "- 核心 md5：$MD5"
  echo "- 守卫退出码：$PARITY　构建退出码：$BUILD　指标结论码：$METRICS　资产检查码：$ASSETS（0/3/1/2＝干净/仅已知项/有新增/硬失败）"
  echo
  echo "## 指标"; echo; echo '```text'; cat "$ROUND/metrics.log"; echo '```'
  echo; echo "## 资产完整性（P9）"; echo; echo '```text'; cat "$ROUND/asset_check.log"; echo '```'
  echo; echo "## 标准测试"; echo; echo '```text'
  grep -E "_smoke|standard_tests" "$ROUND"/*test*.log 2>/dev/null | head -12
  echo '```'
  echo; echo "## 候选探测（本轮建议取活）"; echo
  head -30 "$ROUND/next_probes.md" 2>/dev/null
  echo
  echo "## TODO（agent 填写）"
  echo
  echo "- [ ] 本轮取活的探测（1–3 条）：ID / 结果 / 是否新 Bug"
  echo "- [ ] 未决 Bug 复现结论（编号 / 仍复现或已消失 / 证据）"
  echo "- [ ] 指标异常项逐条解释"
  echo "- [ ] 待人工确认事项"
  echo
  echo "## 待人工确认"
  echo
  echo "（agent 在此列出，或写“无”）"
} > "$ROUND/summary.md"

VERDICT="PASS"; NEW_ISSUE=""
[ "$METRICS" -eq 1 ] && { VERDICT="WARN"; NEW_ISSUE="有新增"; }
[ "$METRICS" -eq 2 ] && VERDICT="FAIL"
[ "$ASSETS" -eq 1 ] && { VERDICT="WARN"; NEW_ISSUE="有新增"; }
[ "$ASSETS" -eq 2 ] && VERDICT="FAIL"
# 资产检查码 3 = 只有已登记的已知项（如 Bug #10：发布截图待 Windows 重生成）：仍记 WARN，
# 但标注「仅已知项」——否则同一个老问题每轮都报，会把结论栏淹没到看不出本轮有没有新问题
if [ "$ASSETS" -eq 3 ] && [ "$VERDICT" = "PASS" ]; then VERDICT="WARN"; NEW_ISSUE="仅已知项"; fi
[ "$SHOTS" -ne 99 ] && [ "$SHOTS" -ne 0 ] && VERDICT="WARN"
[ "$BUILD" -ne 0 ] && VERDICT="FAIL"
[ "$PARITY" -ge 2 ] && VERDICT="FAIL"
printf -- "- %s | %s | %s%s | 守卫=%s 构建=%s 资产=%s | 详见 auto/%s/summary.md\n" \
  "$STAMP" "$TIER" "$VERDICT" "${NEW_ISSUE:+（$NEW_ISSUE）}" "$PARITY" "$BUILD" "$ASSETS" "$STAMP" >> "$ROOT/install_logs/auto/digest.md"
ln -sfn "$STAMP" "$ROOT/install_logs/auto/latest"

# 成功（或仅警告）时记录签名，避免下轮重复同样的工作
if [ "$VERDICT" != "FAIL" ]; then echo "$SIG" > "$ROOT/install_logs/auto/.last_signature"; fi

# --- Phase 8: 体积纪律（平台工作区有配额）------------------------------------
KEEP_ROUNDS="${KEEP_ROUNDS:-7}"
# ① 逐时步 CSV 很大，但指标已提取进 baseline.json，故每轮结束后删掉 runs/（保留 CSV 汇总与图）
rm -rf "$ROUND/standard_tests/runs" "$ROUND/quick_test/runs" 2>/dev/null
# ①b deep 轮基线单独留一份：否则轮次目录被 ② 清理后，下一轮 deep 就失去"同层级可比"的基准
if [ "$TIER" = "deep" ] && [ -f "$ROUND/baseline.json" ]; then
  cp -f "$ROUND/baseline.json" "$ROOT/install_logs/auto/deep_baseline.json"
fi
# ② 只保留最近 KEEP_ROUNDS 轮（按目录名排序，latest 是符号链接不参与）
PRUNED="$(find "$ROOT/install_logs/auto" -maxdepth 1 -type d -name '20*' 2>/dev/null | sort -r \
  | tail -n +$((KEEP_ROUNDS + 1)))"
if [ -n "$PRUNED" ]; then
  printf '%s\n' "$PRUNED" | xargs -r rm -rf
  # 被清理的轮次在 digest 里就地标注，避免"详见 auto/<ts>/summary.md"变成死链
  for d in $PRUNED; do
    ts="$(basename "$d")"
    sed -i "s|详见 auto/$ts/summary.md|详见 auto/$ts/summary.md（已按体积纪律清理）|g" \
      "$ROOT/install_logs/auto/digest.md"
  done
fi
ROUNDS_LEFT="$(find "$ROOT/install_logs/auto" -maxdepth 1 -type d -name '20*' 2>/dev/null | wc -l)"
AUTO_SIZE="$(du -sh "$ROOT/install_logs/auto" 2>/dev/null | cut -f1)"
echo "-- 体积纪律：保留最近 $KEEP_ROUNDS 轮（现存 $ROUNDS_LEFT 轮，auto/ 共 $AUTO_SIZE）"

echo "-- 报告：$ROUND/summary.md；累计摘要：install_logs/auto/digest.md"
echo "== 轮次结束（$VERDICT）=="
[ "$VERDICT" = "FAIL" ] && exit 2
[ "$VERDICT" = "WARN" ] && exit 1
exit 0
