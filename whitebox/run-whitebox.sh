#!/usr/bin/env bash
# 白盒实验的服务器端一键运行:体检 -> 自检 -> Tier A 正对照 -> Tier B 效应筛查。
#
#   ./run-whitebox.sh                  # 全流程
#   ./run-whitebox.sh --only selftest  # 只跑某一阶段
#   ./run-whitebox.sh --dry-run        # 只打印会做什么
#   RUN_ID=20260819-1200 ./run-whitebox.sh    # 接着那次跑
#
# 阶段之间是硬门槛,不是建议。自检不过就停 —— 坏掉的干预照样产出数字,
# 只是没有意义,而那种数字比报错难发现得多。
#
# 环境变量:
#   WB_DEV_MODEL    开发用小模型   (默认 ../models/Qwen3-1.7B)
#   WB_MAIN_MODEL   下结论用的模型 (默认 ../models/Qwen3-8B)
#   WB_LIMIT        Tier B 题数上限 (默认 120)
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$BASE/.." && pwd)"

DEV_MODEL=${WB_DEV_MODEL:-$REPO/models/Qwen3-1.7B}
MAIN_MODEL=${WB_MAIN_MODEL:-$REPO/models/Qwen3-8B}
LIMIT=${WB_LIMIT:-120}

RUN_ID=${RUN_ID:-$(date '+%Y%m%d-%H%M%S')}
OUT=$BASE/results/$RUN_ID
LOGS=$OUT/logs
mkdir -p "$LOGS"

ONLY=""; DRYRUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only)    ONLY="${2:-}"; shift ;;
    --dry-run) DRYRUN=1 ;;
    *) echo "用法: $0 [--only check|selftest|tierA|tierB] [--dry-run]" >&2; exit 1 ;;
  esac
  shift
done

want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }

STAGE=0
stage() {
  local name=$1; shift
  want "$name" || return 0
  STAGE=$((STAGE+1))
  local log=$LOGS/$name.log
  echo
  echo "--------------------------------------------------------------"
  echo "[$STAGE] $name        $(date '+%F %T')"
  echo "        日志: $log"
  echo "--------------------------------------------------------------"
  if [ $DRYRUN -eq 1 ]; then echo "        (dry-run) $*"; return 0; fi
  "$@" 2>&1 | tee "$log"
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo
    echo "[$STAGE] FAIL  $name (exit $rc)"
    return "$rc"
  fi
  echo "[$STAGE] DONE  $name"
  return 0
}

echo "=============================================================="
echo " 白盒实验"
echo "   run id     : $RUN_ID   ->  results/$RUN_ID/"
echo "   开发模型   : $DEV_MODEL"
echo "   主模型     : $MAIN_MODEL"
echo "   Tier B 题数: $LIMIT"
echo "   开始       : $(date '+%F %T')"
echo "=============================================================="

# 显存:总量够(48GB),但 vLLM 默认预留 90%,所以仍然先 stop。
if command -v nvidia-smi >/dev/null 2>&1; then
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  if [ "${USED:-0}" -gt 4000 ] 2>/dev/null && [ $DRYRUN -eq 0 ]; then
    echo
    echo "[!] 显存已占用 ${USED}MiB —— 多半是 vLLM 在跑。"
    echo "    跑 8B 白盒之前: $REPO/run-server.sh stop"
    echo "    只跑 1.7B 的话可以共存,继续。"
  fi
fi

{
  echo "run_id     : $RUN_ID"
  echo "started    : $(date '+%F %T %z')"
  echo "git_commit : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "git_dirty  : $(git -C "$REPO" status --porcelain 2>/dev/null | wc -l) files modified"
  echo "dev_model  : $DEV_MODEL"
  echo "main_model : $MAIN_MODEL"
  echo "limit      : $LIMIT"
  echo "host       : $(hostname 2>/dev/null || echo '?')"
} > "$OUT/run-info.txt"

cd "$BASE"

# --- 1. 体检 ---------------------------------------------------------------
stage check bash "$BASE/setup-whitebox.sh" || exit 1

# --- 2. 自检:硬门槛 --------------------------------------------------------
# 这一步测的不是假设,是代码有没有做它声称的事。九项里任何一项失败,后面所有
# 数字都不可信 —— 而且是"看起来正常但没有意义"那种不可信。
if ! stage selftest python "$BASE/selftest.py" --model "$DEV_MODEL"; then
  echo
  echo "自检未通过。不要继续 —— 坏掉的干预照样出数字。"
  echo "常见原因见 README.md 的「已知的坑」:"
  echo "  第 3 项失败 -> 补丁挂在了每个 decode step 上,不是只挂 prefill"
  echo "  第 5 项失败 -> 注意力用了 sdpa/flash,自定义 4D mask 被忽略"
  exit 1
fi

# --- 3. Tier A 正对照 ------------------------------------------------------
# 这里没有大效应 = 流水线坏了,不是假设错了。skill 在这批题上是必需的:
# 单位是编出来的,不查表无从得知。
stage tierA python "$BASE/e0_effect.py" \
  --model "$DEV_MODEL" \
  --tasks "$BASE/tasks/tier_a/tasks.jsonl" \
  --skill "$BASE/tasks/tier_a/SKILL.zorb-units.md" \
  --mode mc --run-id "$RUN_ID/tierA-dev"
TIERA_RC=$?

if [ $DRYRUN -eq 0 ] && [ $TIERA_RC -eq 0 ] && want tierA; then
  echo
  echo "  [!] Tier A 是正对照:准确率应当从 ~0.25(随机)大幅上升。"
  echo "      如果没有,先怀疑流水线,不要怀疑假设 —— 这批题不查表答不出来。"
fi

# --- 4. Tier B 效应筛查 ----------------------------------------------------
# 真实问题所在。两份 skill 内容互斥(只有数值 / 只有方法),对照本身就是 E2 的
# 预注册预测。--filter-known 把模型本来就答对的题剔掉:它们没有作用空间,
# 只会稀释效应量。
for sk in pchem-constants pchem-procedure; do
  want tierB || break
  stage "tierB-$sk" python "$BASE/e0_effect.py" \
    --model "$MAIN_MODEL" \
    --tasks "$BASE/tasks/tier_b/tasks.jsonl" \
    --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
    --mode num --limit "$LIMIT" \
    --run-id "$RUN_ID/tierB-$sk" \
    --filter-known "$BASE/tasks/tier_b/tasks.filtered.$sk.jsonl"
done

echo
echo "=============================================================="
echo " 结束: $(date '+%F %T')"
echo " 产物: results/$RUN_ID/"
echo
if [ $DRYRUN -eq 0 ]; then
  for f in "$OUT"/*/summary.json; do
    [ -f "$f" ] || continue
    echo " $(basename "$(dirname "$f")"):"
    python - "$f" <<'PY' 2>/dev/null || cat "$f"
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"   n={s['n']}  acc {s['acc_no_skill']:.3f} -> {s['acc_with_skill']:.3f}"
      f"  ({s['delta_acc_pp']:+.1f}pp, CI95 "
      f"[{s['delta_acc_ci95_pp'][0]:+.1f},{s['delta_acc_ci95_pp'][1]:+.1f}])")
print(f"   logprob {s['mean_logprob_no_skill']:.3f} -> "
      f"{s['mean_logprob_with_skill']:.3f}  ({s['delta_logprob']:+.3f})")
PY
  done
fi
cat <<EOF

 注意:本脚本跑的全是**行为层**测量(准确率、logprob),不产生任何层间数据。
       层间实验是 e2_patch.py,它没有放进本脚本 —— 因为它的前提是这一对
       (任务, skill) 已经过了门槛。恢复率是以行为差值为分母的比值,分母是
       噪声时那个比值不是"小",是没有定义。所以先看上面的数,再决定跑不跑。

 接着做什么:
   - 门槛过了 -> 跑 E2:
       python e2_patch.py --model $DEV_MODEL \\
         --tasks tasks/tier_a/tasks.jsonl \\
         --skill tasks/tier_a/SKILL.zorb-units.md \\
         --mode mc --limit 40 --run-id $RUN_ID/e2-tierA
     Tier B 用上面 --filter-known 产出的 tasks.filtered.*.jsonl。
   - 门槛没过 -> 换任务/skill 对;连续四对 < 10pp 就转向"瓶颈在哪一层"
                 (../HANDOFF-whitebox.md 第 6 节第 3 步)
EOF
echo "=============================================================="
