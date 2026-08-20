#!/usr/bin/env bash
# 白盒实验流水线：按顺序把多个实验跑完,每个阶段一份日志,最后汇总成一页。
#
#   ./run-whitebox.sh --list            # 有哪些阶段,各自回答什么问题
#   ./run-whitebox.sh --phase a         # 第一梯：知识型 skill + 单步（1.7B,分钟级）
#   ./run-whitebox.sh --phase b         # 第二梯：真实任务（8B,小时级）
#   ./run-whitebox.sh --only e2-tierA   # 只跑一个阶段
#   ./run-whitebox.sh --from e6-tierA   # 从某个阶段往后
#   ./run-whitebox.sh --dry-run         # 只打印会跑什么
#
# 服务器上没有 tmux,长跑用 nohup：
#   nohup ./run-whitebox.sh --phase b > logs/wb-$(date +%m%d).log 2>&1 &
#   tail -f logs/wb-*.log
#
# 配置：复制 whitebox.conf.example 成 whitebox.conf 改路径即可,脚本会自动读。
# 也可以用环境变量覆盖,或 --config 指定别的文件。conf 不进 git（和 env.sh 一样,
# 它是这台机器的部署状态,不是源码）。
#
# 断点续跑是默认行为：某个阶段的 summary.json 已经在了就跳过,除非 --force。
# 所以中断之后直接重跑同一个 RUN_ID 就行：RUN_ID=xxx ./run-whitebox.sh --phase a
#
# 阶段之间的门槛不是建议：自检不过就停。坏掉的干预照样产出数字,只是没有意义,
# 而那种数字比报错难发现得多。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$BASE/.." && pwd)"

CONFIG="${WB_CONFIG:-$BASE/whitebox.conf}"
ARGS=("$@")
for i in "${!ARGS[@]}"; do
  if [ "${ARGS[$i]}" = "--config" ]; then CONFIG="${ARGS[$((i+1))]:-$CONFIG}"; fi
done
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"

PY=${WB_PYTHON:-python}
DEV_MODEL=${WB_DEV_MODEL:-$REPO/models/Qwen3-1.7B}
MAIN_MODEL=${WB_MAIN_MODEL:-$REPO/models/Qwen3-8B}
DEVICE=${WB_DEVICE:-cuda}
TIERB_N=${WB_TIERB_LIMIT:-120}
E2_N=${WB_E2_LIMIT:-40}
E1_N=${WB_E1_LIMIT:-40}
TAIL_K=${WB_TAIL_K:-4}
LAYER_STEP_B=${WB_TIERB_LAYER_STEP:-2}
GROUP_B=${WB_TIERB_GROUP:-4}

RUN_ID=${RUN_ID:-$(date '+%Y%m%d-%H%M%S')}
OUT=$BASE/results/$RUN_ID
LOGS=$OUT/logs
STATUS=$OUT/status.tsv

# 阶段表：名字 | 梯队 | 这一步回答什么问题
# 梯队 0 = 不花算力的门槛,a = Tier A 合成任务（开发模型）,b = Tier B 真实任务
STAGES=(
  "check|0|环境与冻结校验：任务集、skill、渲染器有没有被动过"
  "selftest|0|干预机制自检：补丁和敲除有没有做它们声称的事（硬门槛）"
  "e7-metrics|0|几何指标自检：余弦/有效维数/探针在已知数据上给不给出已知答案"
  "e0-tierA|a|有没有值得解释的效应？不过门槛,后面全是在解释噪声"
  "errors-tierA|a|skill 消掉的是哪一类错？格式 / 选错表 / 读错行"
  "e7-tierA|a|注入之后表示层出现了什么 pattern？一个共享方向还是逐题内容"
  "e6-tierA|a|模型真的在读那张表吗？改掉一个换算因子,答案跟谁走"
  "e6-tierA-near|a|近似匹配的错值是不是更容易锚住模型（H5 上下文干扰）"
  "e2-tierA|a|效应能不能压进一个向量？能=H2 选择,不能=H1 检索"
  "e2-tierA-k4|a|换成补 K 个位置还压不进吗？区分「压不进」和「一个位置装不下」"
  "e1-tierA|a|哪些层在读 skill？早层=读一次,中后层持续=反复回看"
  "e0-tierB-const|b|真实任务上,只给常数的 skill 有没有效应"
  "e0-tierB-proc|b|真实任务上,只给方法的 skill 有没有效应"
  "e7-tierB|b|两份内容互斥的 skill,在表示层是同一个方向还是两个方向"
  "e2-tierB-const|b|预注册预测：example 型 skill 应当压不进向量"
  "e2-tierB-proc|b|预注册预测：principle 型 skill 应当压得进向量"
  "e1-tierB-const|b|检索型 skill 的注意力依赖是不是持续到中后层"
  "e1-tierB-proc|b|流程型 skill 是不是只在早层被读一次"
)

PHASE=""; ONLY=""; FROM=""; SKIP=""; DRYRUN=0; FORCE=0; LIST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --list)    LIST=1 ;;
    --phase)   PHASE="${2:-}"; shift ;;
    --only)    ONLY="${2:-}"; shift ;;
    --from)    FROM="${2:-}"; shift ;;
    --skip)    SKIP="${SKIP} ${2:-}"; shift ;;
    --config)  shift ;;
    --dry-run) DRYRUN=1 ;;
    --force)   FORCE=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "未知参数: $1（--help 看用法）" >&2; exit 1 ;;
  esac
  shift
done

name_of()  { echo "${1%%|*}"; }
phase_of() { local r=${1#*|}; echo "${r%%|*}"; }
what_of()  { echo "${1##*|}"; }

if [ $LIST -eq 1 ]; then
  echo "阶段（按顺序）:"
  for s in "${STAGES[@]}"; do
    printf "  [%s] %-16s %s\n" "$(phase_of "$s")" "$(name_of "$s")" "$(what_of "$s")"
  done
  cat <<'EOF'

梯队 0 不花算力,每次都跑。
梯队 a 是知识型 skill + 单步 —— 单位是编出来的,不查表答不出来,所以效应是构造
       保证的。它的作用是让「没测到」只能有一个解释：代码坏了。
梯队 b 是真实任务（SciBench 物理化学）+ 两份内容互斥的 skill。结论在这里出。
EOF
  exit 0
fi

gate_ok() {   # gate_ok <summary.json> —— e0 的门槛过没过
  [ -f "$1" ] || return 1
  "$PY" - "$1" <<'PY'
import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))
acc = s["delta_acc_pp"] >= 15 and s["delta_acc_ci95_pp"][0] > 5
lp = s["delta_acc_pp"] >= 5 and s["delta_logprob_ci95"][0] > 0
sys.exit(0 if (acc or lp) else 1)
PY
}

mkdir -p "$LOGS"
[ -f "$STATUS" ] || printf "stage\tstatus\tseconds\tstarted\n" > "$STATUS"

record() { printf "%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$(date '+%F %T')" >> "$STATUS"; }

STAGE_N=0
run_stage() {
  local name=$1 what=$2; shift 2
  STAGE_N=$((STAGE_N+1))
  local log=$LOGS/$name.log
  local done_marker=$OUT/$name/summary.json
  echo
  echo "--------------------------------------------------------------"
  echo "[$STAGE_N] $name    $(date '+%F %T')"
  echo "     问题: $what"
  echo "     日志: ${log#"$BASE"/}"
  echo "--------------------------------------------------------------"
  if [ $DRYRUN -eq 1 ]; then echo "     (dry-run) $*"; record "$name" dry 0; return 0; fi
  if [ $FORCE -eq 0 ] && [ -f "$done_marker" ]; then
    echo "     已经跑过（$name/summary.json 在）,跳过。要重跑加 --force"
    record "$name" cached 0; return 0
  fi
  local t0 t1 rc
  t0=$(date +%s)
  "$@" 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  t1=$(date +%s)
  if [ "$rc" -ne 0 ]; then
    echo "[$STAGE_N] FAIL  $name (exit $rc, $((t1-t0))s)"
    record "$name" "fail:$rc" "$((t1-t0))"
    return "$rc"
  fi
  echo "[$STAGE_N] DONE  $name  ($((t1-t0))s)"
  record "$name" ok "$((t1-t0))"
  return 0
}

should_run() {   # should_run <stage-entry>
  local n p
  n=$(name_of "$1"); p=$(phase_of "$1")
  case " $SKIP " in *" $n "*) return 1 ;; esac
  if [ -n "$ONLY" ]; then [ "$ONLY" = "$n" ]; return $?; fi
  if [ -n "$FROM" ]; then
    if [ "${STARTED:-0}" != "1" ]; then
      if [ "$n" = "$FROM" ]; then STARTED=1; else return 1; fi
    fi
  fi
  if [ -n "$PHASE" ] && [ "$PHASE" != "all" ] && [ "$p" != "0" ] \
     && [ "$p" != "$PHASE" ]; then return 1; fi
  return 0
}

echo "=============================================================="
echo " 白盒实验流水线"
echo "   run id     : $RUN_ID   ->  results/$RUN_ID/"
echo "   配置       : ${CONFIG#"$REPO"/}$([ -f "$CONFIG" ] || echo ' (没有,用默认值)')"
echo "   开发模型   : $DEV_MODEL"
echo "   主模型     : $MAIN_MODEL"
echo "   梯队       : ${PHASE:-all}${ONLY:+   只跑 $ONLY}${FROM:+   从 $FROM 起}"
echo "   开始       : $(date '+%F %T')"
echo "=============================================================="

if command -v nvidia-smi >/dev/null 2>&1 && [ $DRYRUN -eq 0 ]; then
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  if [ "${USED:-0}" -gt 4000 ] 2>/dev/null; then
    echo
    echo "[!] 显存已占用 ${USED}MiB —— 多半是 vLLM。跑 8B 之前先: $REPO/run-server.sh stop"
    echo "    只跑 1.7B（梯队 a）可以共存。"
  fi
fi

{
  echo "run_id     : $RUN_ID"
  echo "started    : $(date '+%F %T %z')"
  echo "git_commit : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "git_dirty  : $(git -C "$REPO" status --porcelain 2>/dev/null | wc -l) files modified"
  echo "dev_model  : $DEV_MODEL"
  echo "main_model : $MAIN_MODEL"
  echo "host       : $(hostname 2>/dev/null || echo '?')"
} > "$OUT/run-info.txt"

cd "$BASE" || exit 1
A_TASKS=$BASE/tasks/tier_a/tasks.jsonl
A_SKILL=$BASE/tasks/tier_a/SKILL.zorb-units.md
B_TASKS=$BASE/tasks/tier_b/tasks.jsonl

for entry in "${STAGES[@]}"; do
  nm=$(name_of "$entry"); wh=$(what_of "$entry")
  should_run "$entry" || continue
  case "$nm" in

  check)
    run_stage "$nm" "$wh" bash "$BASE/setup-whitebox.sh" || exit 1 ;;

  selftest)
    # 这一步测的不是假设,是代码。任何一项失败,后面所有数字都是"看起来正常
    # 但没有意义"那一种。
    if ! run_stage "$nm" "$wh" "$PY" "$BASE/selftest.py" \
         --model "$DEV_MODEL" --device "$DEVICE"; then
      echo
      echo "自检未通过,停。常见原因见 README「已知的坑」："
      echo "  第 3 项 -> 补丁挂在了每个 decode step 上,不是只挂 prefill"
      echo "  第 5 项 -> 注意力用了 sdpa/flash,自定义 4D mask 被静默忽略"
      echo "  第 6b 项 -> span 只覆盖到文档开头,敲除会挡不到内容"
      exit 1
    fi ;;

  e7-metrics)
    run_stage "$nm" "$wh" "$PY" "$BASE/e7_repr.py" --selftest || exit 1 ;;

  e0-tierA)
    run_stage "$nm" "$wh" "$PY" "$BASE/e0_effect.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" \
      --mode mc --run-id "$RUN_ID/$nm"
    if [ $DRYRUN -eq 0 ] && ! gate_ok "$OUT/$nm/summary.json"; then
      echo
      echo "[!] Tier A 是**正对照**：这批题不查表答不出来,所以没有大效应"
      echo "    只有一个解释 —— 流水线坏了,不是假设错了。后面的层间实验先别看。"
    fi ;;

  errors-tierA)
    mkdir -p "$OUT/$nm"
    run_stage "$nm" "$wh" "$PY" "$BASE/errors.py" \
      --per-item "$OUT/e0-tierA/per_item.jsonl" --tasks "$A_TASKS" \
      --out "$OUT/$nm/errors.json" ;;

  e7-tierA)
    run_stage "$nm" "$wh" "$PY" "$BASE/e7_repr.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode mc --probe family \
      --run-id "$RUN_ID/$nm" ;;

  e6-tierA)
    run_stage "$nm" "$wh" "$PY" "$BASE/e6_counterfactual.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --flavour far --run-id "$RUN_ID/$nm" ;;

  e6-tierA-near)
    run_stage "$nm" "$wh" "$PY" "$BASE/e6_counterfactual.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --flavour near --run-id "$RUN_ID/$nm" ;;

  e2-tierA)
    run_stage "$nm" "$wh" "$PY" "$BASE/e2_patch.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode mc --limit "$E2_N" \
      --run-id "$RUN_ID/$nm" ;;

  e2-tierA-k4)
    run_stage "$nm" "$wh" "$PY" "$BASE/e2_patch.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode mc --limit "$E2_N" \
      --tail-k "$TAIL_K" --run-id "$RUN_ID/$nm" ;;

  e1-tierA)
    run_stage "$nm" "$wh" "$PY" "$BASE/e1_knockout.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode mc --limit "$E1_N" \
      --run-id "$RUN_ID/$nm" ;;

  e0-tierB-const|e0-tierB-proc)
    sk=pchem-constants; [ "$nm" = "e0-tierB-proc" ] && sk=pchem-procedure
    run_stage "$nm" "$wh" "$PY" "$BASE/e0_effect.py" \
      --model "$MAIN_MODEL" --device "$DEVICE" \
      --tasks "$B_TASKS" --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
      --mode num --limit "$TIERB_N" --run-id "$RUN_ID/$nm" \
      --filter-known "$BASE/tasks/tier_b/tasks.filtered.$sk.jsonl" ;;

  e7-tierB)
    run_stage "$nm" "$wh" "$PY" "$BASE/e7_repr.py" \
      --model "$MAIN_MODEL" --device "$DEVICE" \
      --tasks "$B_TASKS" --mode num --limit "$TIERB_N" \
      --skill "$BASE/tasks/tier_b/SKILL.pchem-constants.md" \
      --skill "$BASE/tasks/tier_b/SKILL.pchem-procedure.md" \
      --run-id "$RUN_ID/$nm" ;;

  e2-tierB-const|e2-tierB-proc|e1-tierB-const|e1-tierB-proc)
    case "$nm" in *-const) sk=pchem-constants ;; *) sk=pchem-procedure ;; esac
    filtered=$BASE/tasks/tier_b/tasks.filtered.$sk.jsonl
    # 层间实验的分母是行为效应。分母是噪声时,恢复率不是"小",是没有定义 ——
    # 所以门槛没过就跳过,而不是照跑然后在报告里解释。
    if [ $DRYRUN -eq 0 ] && ! gate_ok "$OUT/e0-tierB-${nm##*-}/summary.json"; then
      echo
      echo "[跳过] $nm —— $sk 没过 Phase 0 门槛（或还没跑）。"
      echo "        层间实验的因变量差值是恢复率的分母,分母是噪声时那个比值没有定义。"
      record "$nm" skipped-gate 0
      continue
    fi
    if [ ! -f "$filtered" ] && [ $DRYRUN -eq 0 ]; then
      echo "[跳过] $nm —— 缺 $(basename "$filtered")（先跑 e0-tierB-*）"
      record "$nm" skipped-nofile 0
      continue
    fi
    case "$nm" in
      e2-*) run_stage "$nm" "$wh" "$PY" "$BASE/e2_patch.py" \
              --model "$MAIN_MODEL" --device "$DEVICE" \
              --tasks "$filtered" --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
              --mode num --limit "$E2_N" --layer-step "$LAYER_STEP_B" \
              --run-id "$RUN_ID/$nm" ;;
      e1-*) run_stage "$nm" "$wh" "$PY" "$BASE/e1_knockout.py" \
              --model "$MAIN_MODEL" --device "$DEVICE" \
              --tasks "$filtered" --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
              --mode num --limit "$E1_N" --group "$GROUP_B" \
              --run-id "$RUN_ID/$nm" ;;
    esac ;;

  *) echo "[!] 阶段表里有 $nm,但没有对应的命令" ;;
  esac
done

echo
echo "=============================================================="
echo " 结束: $(date '+%F %T')"
if [ $DRYRUN -eq 0 ]; then
  echo
  column -t -s "$(printf '\t')" "$STATUS" 2>/dev/null || cat "$STATUS"
  echo
  "$PY" "$BASE/report.py" "$OUT"
  echo
  echo " 单独再看一次汇总: $PY report.py results/$RUN_ID"
fi
echo "=============================================================="
