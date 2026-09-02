#!/usr/bin/env bash
# 白盒实验流水线：按顺序把多个实验跑完,每个阶段一份日志,最后汇总成一页。
#
#   ./run-whitebox.sh --list            # 有哪些阶段,各自回答什么问题
#   ./run-whitebox.sh --smoke --phase a # 几题几层跑通全流程（先做这个,一两分钟）
#   ./run-whitebox.sh --phase a         # 第一梯：知识型 skill + 单步（1.7B,分钟级）
#   ./run-whitebox.sh --phase b         # 第二梯：真实任务（8B,小时级）
#   ./run-whitebox.sh --only e2-tierA   # 只跑一个阶段
#   ./run-whitebox.sh --from e6-tierA   # 从某个阶段往后
#   ./run-whitebox.sh --skip e1-tierA   # 排除某个阶段（可重复）
#   ./run-whitebox.sh --dry-run         # 只打印会跑什么,不产生任何文件
#   ./run-whitebox.sh --force           # 忽略"已经跑过",重跑
#   ./run-whitebox.sh --no-gate         # 跳过 Phase 0 门槛检查（现在门槛不过也会跑,只是标记）（分母你自己确认过）
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
# E1 一次敲一层时，单层的真实效应比题间方差还小（selftest：单层 1.4 vs 全层 20.9），
# 在 28 条那样的曲线里取最大值只会拿到噪声的上尾。Tier B 一直是 4，
# Tier A 之前漏了，默认跟 Tier B 对齐。
GROUP_A=${WB_TIERA_GROUP:-4}

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
  "e0-tierA|a|有没有值得解释的效应？不过门槛,后面全是在解释噪声（含各类干扰项的间距）"
  "e0-tierA-filler|a|中性文档对照：Tier A 的效应里有多少只是「上下文里多了份长文档」"
  "e0-tierA-num|a|同一批题改成填空：+36pp 里有多少是「会算」,多少是「会在四个选项里选」"
  "errors-tierA|a|skill 消掉的是哪一类错？格式 / 选错表 / 读错行"
  "errors-tierA-filler|a|中性文档消掉的是哪一类错 —— 和 errors-tierA 相减才是内容修的那部分"
  "e7-tierA|a|注入之后表示层出现了什么 pattern？一个共享方向还是逐题内容"
  "e6-tierA|a|模型真的在读那张表吗？改掉一个换算因子,答案跟谁走"
  "e6-tierA-near|a|近似匹配的错值是不是更容易锚住模型（H5 上下文干扰）"
  "e6-diagnose-tierA|a|E6 的 follow rate 无定义时,原始生成到底长什么样（纯后处理）"
  "e6-diagnose-tierA-near|a|同上,近似口味"
  "e2-tierA|a|效应能不能压进一个向量？能=H2 选择,不能=H1 检索"
  "e2-tierA-k4|a|换成补 K 个位置还压不进吗？区分「压不进」和「一个位置装不下」"
  "e1-tierA|a|哪些层在读 skill？早层=读一次,中后层持续=反复回看"
  "e0-tierB-const|b|选装置任务上,只给常数的 skill 有没有效应（含轴间距）"
  "e0-tierB-proc|b|选装置任务上,只给方法的 skill 有没有效应（含轴间距）"
  "e0-tierB-filler|b|中性文档对照：通用成分在 Tier B 上有多大,轴间距是否真的免疫"
  "errors-tierB-const|b|常数 skill 修的是单位轴还是关系式轴（双重分离的一半）"
  "errors-tierB-proc|b|方法 skill 修的是关系式轴还是单位轴（另一半）"
  "errors-tierB-filler|b|中性文档在 Tier B 上消掉哪一类错（两份 skill 的共同基线）"
  "did-tierB|b|双重分离的判据：轴间距的双重差分 + 配对 bootstrap 的 CI"
  "e7-tierB|b|两份内容互斥的 skill,在表示层是同一个方向还是两个方向（带中性填充对照）"
  "e2-tierB-const|b|预注册预测：example 型 skill 应当压不进向量（带中性文档对照）"
  "e2-tierB-proc|b|预注册预测：principle 型 skill 应当压得进向量（带中性文档对照）"
  "e1-tierB-const|b|检索型 skill 的注意力依赖是不是持续到中后层"
  "e1-tierB-proc|b|流程型 skill 是不是只在早层被读一次"
  "figs|0|把这个 run 里每一条层扫描画成论文用的 tikz 片段（纯后处理）"
)

PHASE=""; ONLY=""; FROM=""; SKIP=""; DRYRUN=0; FORCE=0; LIST=0; NOGATE=0
SMOKE=0; FAILED=0
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
    --no-gate) NOGATE=1 ;;
    --smoke)   SMOKE=1 ;;
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
    printf "  [%s] %-22s %s\n" "$(phase_of "$s")" "$(name_of "$s")" "$(what_of "$s")"
  done
  cat <<'EOF'

梯队 0 不花算力,每次都跑。
梯队 a 是知识型 skill + 单步 —— 单位是编出来的,不查表答不出来,所以效应是构造
       保证的。它的作用是让「没测到」只能有一个解释：代码坏了。
梯队 b 是选装置任务（tier_b2,116 题,无算术）+ 两份内容互斥的 skill。
       机制结论从这里出：头一个是行为层的双重分离,常数那份 skill 应当只修
       单位轴、方法那份只修关系式轴,e0+errors 就能判,不用层扫描。
       效应量结论不从这里出 —— 题是生成的,见 HANDOFF §15.4。
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

# set_gate_flag <e0-summary.json> —— 门槛没过时不跳过,但把"分母未确认"这个
# 污点一路带下去。设置全局 GATE_FLAG,调用方原样展开。
#
# 恢复率 = (补丁后 - 无skill) / (有skill - 无skill)。分母是行为效应,门槛没过
# 意味着那个分母的 CI 含 0 —— 所以这个比值不是"小",是**没有定义**:分母趋近 0
# 时它可以是任意大的数,符号也随抽样翻转。以前的做法是跳过,现在改成跑完并标记,
# 因为曲线的**形状**（哪一层起跳、别题向量恢复多少）即使在分母不确定时也有诊断
# 价值,只是那个**比值**不能报。
#
# 关键是标记必须进 summary.json,而不只是打在终端上:半年后读到 "recovery
# +1.07" 的人不会去翻当时的日志。
#
# 这原来只挂在 Tier B 上,理由是 Tier A 是正对照、"当然过得了门槛"。§12.3m 换掉
# 题集之后它就不过了（n=39,Δacc 的 CI 下界压在 0 上）,于是 e2-tierA 打出一个
# 分母未确认的恢复率,还不带任何警告 —— 正对照的身份不是豁免。
set_gate_flag() {
  GATE_FLAG=()
  [ $DRYRUN -eq 1 ] && return 0
  [ $NOGATE -eq 1 ] && return 0
  gate_ok "$1" && return 0
  echo
  echo "  ############################################################"
  echo "  #  [!!] 分母未确认 —— $nm"
  echo "  #"
  echo "  #  $(basename "$(dirname "$1")") 没过 Phase 0 门槛（或这个 RUN_ID"
  echo "  #  下还没跑过它）。恢复率的分母是那个行为效应,它的 CI 含 0。"
  echo "  #"
  echo "  #  照跑,但结论只能读**曲线形状**（哪一层起跳、对照恢复多少）,"
  echo "  #  **那个比值不能报**。summary.json 里会带 gate_unconfirmed 标记,"
  echo "  #  report.py 会一直提醒。"
  echo "  ############################################################"
  echo
  GATE_FLAG=(--gate-unconfirmed)
}

if [ $DRYRUN -eq 0 ]; then
  mkdir -p "$LOGS"
  [ -f "$STATUS" ] || printf "stage\tstatus\tseconds\tstarted\n" > "$STATUS"
fi

record() {
  [ $DRYRUN -eq 1 ] && return 0
  printf "%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$(date '+%F %T')" >> "$STATUS"
}

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
    FAILED=$((FAILED+1))
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

[ $DRYRUN -eq 0 ] && {
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
B_TASKS=$BASE/tasks/tier_b2/tasks.jsonl
# Tier B v1 (SciBench, free numeric) is kept for reference but is no longer
# on the ladder: the no-CoT decoding it inherits puts its baseline at 0.067,
# with no room for a skill to act in. See HANDOFF-whitebox.md 15.
B_TASKS_V1=$BASE/tasks/tier_b/tasks.jsonl

# --smoke：几道题、几层，跑通全流程用的。数字全是错的,唯一的问题是
# "每一步会不会跑起来"。真跑之前先 smoke 一遍,比在第 40 分钟撞到一个
# 参数拼错要便宜得多。
A_LIMIT=(); E2_STEP=(); E1_GROUP=(--group "$GROUP_A")
if [ $SMOKE -eq 1 ]; then
  A_LIMIT=(--limit 8); E2_N=4; E1_N=4; TIERB_N=8
  E2_STEP=(--layer-step 8); E1_GROUP=(--group 8)
  LAYER_STEP_B=8; GROUP_B=8
  echo
  echo "[smoke] 每个阶段只跑几题几层。这一轮的数字没有意义,看的是能不能跑通。"
fi
# 空数组在 set -u 下直接展开会报错(bash < 4.4),所以下面一律写成 ${a[@]+"${a[@]}"}

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
      --tasks "$A_TASKS" --skill "$A_SKILL" ${A_LIMIT[@]+"${A_LIMIT[@]}"} \
      --mode mc --margins --run-id "$RUN_ID/$nm"
    if [ $DRYRUN -eq 0 ] && [ $NOGATE -eq 0 ] && ! gate_ok "$OUT/$nm/summary.json"; then
      echo
      echo "[!] Tier A 是**正对照**：这批题不查表答不出来,所以没有大效应"
      echo "    只有一个解释 —— 流水线坏了,不是假设错了。后面的层间实验先别看。"
    fi ;;

  e0-tierA-filler)
    # The arm Tier A never had. e0-tierA measures skill against nothing, so its
    # delta contains both "the document says how to convert" and "a 688-token
    # document is in context at all" -- and the second one is not small: 12.3j
    # found a neutral document moves the residual as far as a skill does, and
    # 12.3k found the mean vector, which carries no per-item content, recovers
    # MORE than the document itself. Tier B has had this condition since 12.3l.
    # On Tier A the generic component had been measured only inside E2 and E7,
    # never on accuracy -- which is the number this tier is quoted for.
    #
    # Same items, same model, same length of context; only the document differs.
    # --control because here a failed gate is the expected result.
    run_stage "$nm" "$wh" "$PY" "$BASE/e0_effect.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$BASE/tasks/filler-neutral.md" \
      ${A_LIMIT[@]+"${A_LIMIT[@]}"} \
      --mode mc --margins --control --run-id "$RUN_ID/$nm" ;;

  e0-tierA-num)
    # Same items, same skill, free-form numeric answers instead of four options.
    # E6 already runs Tier A in num mode and reports that with the correct,
    # unperturbed skill the model produces the right value on 0% of items -- so
    # the MC accuracy the gate passed on may be discrimination among four
    # options rather than the conversion. This stage measures that directly
    # instead of leaving it as an inference from E6's skipped-item pool.
    run_stage "$nm" "$wh" "$PY" "$BASE/e0_effect.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode num \
      ${A_LIMIT[@]+"${A_LIMIT[@]}"} --run-id "$RUN_ID/$nm" ;;

  errors-tierA|errors-tierA-filler)
    # The same typology on both arms. errors-tierA says which error classes the
    # skill removes; errors-tierA-filler says which ones a document that knows
    # nothing about Zorb units removes. The difference is the only Tier A claim
    # about content that survives 12.3j, and it is free -- both stages read a
    # per_item.jsonl the e0 stages already wrote.
    case "$nm" in
      *-filler) src=e0-tierA-filler; lbl=filler-neutral ;;
      *)        src=e0-tierA;        lbl=zorb-units ;;
    esac
    if [ $DRYRUN -eq 0 ] && [ ! -f "$OUT/$src/per_item.jsonl" ]; then
      echo "[跳过] $nm —— 缺 $src/per_item.jsonl（先跑 $src）"
      record "$nm" skipped-nofile 0
      continue
    fi
    [ $DRYRUN -eq 0 ] && mkdir -p "$OUT/$nm"
    run_stage "$nm" "$wh" "$PY" "$BASE/errors.py" \
      --per-item "$OUT/$src/per_item.jsonl" --tasks "$A_TASKS" \
      --mode mc --label "$lbl" --out "$OUT/$nm/errors.json" ;;

  e6-diagnose-tierA|e6-diagnose-tierA-near)
    # Written months ago and never run until 2026-08-31, when it turned the E6
    # "100% neither" readout from a broken measurement into positive evidence.
    # A diagnostic nobody remembers to run is a diagnostic that does not exist,
    # so it is a stage.
    src=${nm#e6-diagnose-}
    if [ $DRYRUN -eq 0 ] && [ ! -f "$OUT/e6-$src/per_item.jsonl" ]; then
      echo "[跳过] $nm —— 缺 e6-$src/per_item.jsonl（先跑 e6-$src）"
      record "$nm" skipped-nofile 0
      continue
    fi
    [ $DRYRUN -eq 0 ] && mkdir -p "$OUT/$nm"
    run_stage "$nm" "$wh" "$PY" "$BASE/e6_diagnose.py" "$OUT/e6-$src" \
      --out "$OUT/$nm/e6diag.json" ;;

  figs)
    # paperfig walks the run itself: which sweeps exist depends on the tier and
    # on which stages were asked for, and a list in the shell would go stale.
    [ $DRYRUN -eq 0 ] && mkdir -p "$OUT/paper"
    run_stage "$nm" "$wh" "$PY" "$BASE/paperfig.py" "$OUT" --all \
      --outdir "$OUT/paper" ;;

  e7-tierA)
    # 中性填充文档当第三份"skill"：它不是 skill,所以它要是也走同一个方向,
    # 那个方向就不是 skill 的签名,而是"上下文里多了一份长文档"。
    # 多一遍前向,e7 是全流水线最便宜的那个。
    run_stage "$nm" "$wh" "$PY" "$BASE/e7_repr.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" \
      --skill "$BASE/tasks/filler-neutral.md" --mode mc --probe family \
      ${A_LIMIT[@]+"${A_LIMIT[@]}"} --run-id "$RUN_ID/$nm" ;;

  e6-tierA)
    run_stage "$nm" "$wh" "$PY" "$BASE/e6_counterfactual.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --flavour far ${A_LIMIT[@]+"${A_LIMIT[@]}"} \
      --run-id "$RUN_ID/$nm" ;;

  e6-tierA-near)
    run_stage "$nm" "$wh" "$PY" "$BASE/e6_counterfactual.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --flavour near ${A_LIMIT[@]+"${A_LIMIT[@]}"} \
      --run-id "$RUN_ID/$nm" ;;

  e2-tierA|e2-tierA-k4)
    # --filler is not optional any more. E7 found the injection direction is
    # generic -- a neutral document moves the residual as far as a skill does
    # (HANDOFF 12.3j) -- so a recovery number without this condition cannot be
    # told apart from "a document was in context when the vector was captured".
    set_gate_flag "$OUT/e0-tierA/summary.json"
    K4=(); [ "$nm" = "e2-tierA-k4" ] && K4=(--tail-k "$TAIL_K")
    run_stage "$nm" "$wh" "$PY" "$BASE/e2_patch.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode mc --limit "$E2_N" \
      --filler "$BASE/tasks/filler-neutral.md" \
      ${E2_STEP[@]+"${E2_STEP[@]}"} ${K4[@]+"${K4[@]}"} \
      ${GATE_FLAG[@]+"${GATE_FLAG[@]}"} \
      --run-id "$RUN_ID/$nm" ;;

  e1-tierA)
    set_gate_flag "$OUT/e0-tierA/summary.json"
    run_stage "$nm" "$wh" "$PY" "$BASE/e1_knockout.py" \
      --model "$DEV_MODEL" --device "$DEVICE" \
      --tasks "$A_TASKS" --skill "$A_SKILL" --mode mc --limit "$E1_N" \
      ${E1_GROUP[@]+"${E1_GROUP[@]}"} \
      ${GATE_FLAG[@]+"${GATE_FLAG[@]}"} --run-id "$RUN_ID/$nm" ;;

  e0-tierB-const|e0-tierB-proc)
    sk=pchem-constants; [ "$nm" = "e0-tierB-proc" ] && sk=pchem-procedure
    # No --filter-known here. v1 used it to drop the items the model already got
    # right, which is the correct move against a CEILING and the wrong one
    # against a floor: at 0.067 it would have left a pool with a 0% baseline.
    # The v2 set is built to land mid-range on its own; if it does not, the fix
    # belongs in the generator, not in a filter applied after the fact.
    run_stage "$nm" "$wh" "$PY" "$BASE/e0_effect.py" \
      --model "$MAIN_MODEL" --device "$DEVICE" \
      --tasks "$B_TASKS" --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
      --mode mc --limit "$TIERB_N" --margins --run-id "$RUN_ID/$nm" ;;

  e0-tierB-filler)
    # The same measurement with a document that says nothing about chemistry.
    # Two things it settles that nothing else can: how big the generic "a long
    # document is present" effect is on THIS tier (Tier A's was the whole
    # effect), and whether the axis margins are really blind to it -- they are
    # supposed to be, and this is the condition that checks the claim rather
    # than assuming it. Marked --control so a failed gate reads as the expected
    # result rather than as a failure.
    run_stage "$nm" "$wh" "$PY" "$BASE/e0_effect.py" \
      --model "$MAIN_MODEL" --device "$DEVICE" \
      --tasks "$B_TASKS" --skill "$BASE/tasks/filler-neutral.md" \
      --mode mc --limit "$TIERB_N" --margins --control \
      --run-id "$RUN_ID/$nm" ;;

  errors-tierB-const|errors-tierB-proc|errors-tierB-filler)
    # Half the double dissociation each, plus the neutral arm they share. The
    # comparison ACROSS the files is what carries the result -- report.py does
    # it, and did-tierB puts an interval on it.
    case "$nm" in
      *-const)  sk=pchem-constants; e0=e0-tierB-const ;;
      *-filler) sk=filler-neutral;  e0=e0-tierB-filler ;;
      *)        sk=pchem-procedure; e0=e0-tierB-proc ;;
    esac
    if [ $DRYRUN -eq 0 ] && [ ! -f "$OUT/$e0/per_item.jsonl" ]; then
      echo "[跳过] $nm —— 缺 $e0/per_item.jsonl（先跑 $e0）"
      record "$nm" skipped-nofile 0
      continue
    fi
    [ $DRYRUN -eq 0 ] && mkdir -p "$OUT/$nm"
    run_stage "$nm" "$wh" "$PY" "$BASE/errors.py" \
      --per-item "$OUT/$e0/per_item.jsonl" --tasks "$B_TASKS" --mode mc \
      --label "$sk" --out "$OUT/$nm/errors.json" ;;

  did-tierB)
    # The preregistered verdict, run by the pipeline instead of by hand. It is
    # pure post-processing over the two e0 per_item files, so it costs nothing,
    # and there is no reason for the one number the 2x2 was built to produce to
    # live only in somebody's shell history. The four branches of the verdict
    # are written into did.py (12.3l), fixed before any margin was seen.
    if [ $DRYRUN -eq 0 ] && { [ ! -f "$OUT/e0-tierB-const/per_item.jsonl" ] \
       || [ ! -f "$OUT/e0-tierB-proc/per_item.jsonl" ]; }; then
      echo "[跳过] $nm —— 缺 e0-tierB-const / e0-tierB-proc 的 per_item.jsonl"
      record "$nm" skipped-nofile 0
      continue
    fi
    [ $DRYRUN -eq 0 ] && mkdir -p "$OUT/$nm"
    run_stage "$nm" "$wh" "$PY" "$BASE/did.py" "$OUT" \
      --out "$OUT/$nm/did.json" ;;

  e7-tierB)
    run_stage "$nm" "$wh" "$PY" "$BASE/e7_repr.py" \
      --model "$MAIN_MODEL" --device "$DEVICE" \
      --tasks "$B_TASKS" --mode mc --limit "$TIERB_N" \
      --skill "$BASE/tasks/tier_b/SKILL.pchem-constants.md" \
      --skill "$BASE/tasks/tier_b/SKILL.pchem-procedure.md" \
      --skill "$BASE/tasks/filler-neutral.md" \
      --run-id "$RUN_ID/$nm" ;;

  e2-tierB-const|e2-tierB-proc|e1-tierB-const|e1-tierB-proc)
    case "$nm" in *-const) sk=pchem-constants ;; *) sk=pchem-procedure ;; esac
    # v1 pointed these at tasks.filtered.<skill>.jsonl, the output of
    # --filter-known. v2 has no filter step, so they run on the same items e0
    # did -- which is also what E2 needs: the two recovery curves are only
    # comparable if both skills were measured on an identical pool.
    filtered=$B_TASKS
    set_gate_flag "$OUT/e0-tierB-${nm##*-}/summary.json"
    if [ ! -f "$filtered" ] && [ $DRYRUN -eq 0 ]; then
      echo "[跳过] $nm —— 缺 $(basename "$filtered")（先跑 e0-tierB-*）"
      record "$nm" skipped-nofile 0
      continue
    fi
    case "$nm" in
      e2-*) run_stage "$nm" "$wh" "$PY" "$BASE/e2_patch.py" \
              --model "$MAIN_MODEL" --device "$DEVICE" \
              --tasks "$filtered" --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
              --mode mc --limit "$E2_N" --layer-step "$LAYER_STEP_B" \
              --filler "$BASE/tasks/filler-neutral.md" \
              ${GATE_FLAG[@]+"${GATE_FLAG[@]}"} \
              --run-id "$RUN_ID/$nm" ;;
      e1-*) run_stage "$nm" "$wh" "$PY" "$BASE/e1_knockout.py" \
              --model "$MAIN_MODEL" --device "$DEVICE" \
              --tasks "$filtered" --skill "$BASE/tasks/tier_b/SKILL.$sk.md" \
              --mode mc --limit "$E1_N" --group "$GROUP_B" \
              ${GATE_FLAG[@]+"${GATE_FLAG[@]}"} \
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
  if [ $FAILED -gt 0 ]; then
    echo
    echo " [!] $FAILED 个阶段失败,日志在 results/$RUN_ID/logs/。"
    echo "     修完之后重跑同一个 RUN_ID 就行,跑成功的阶段会跳过:"
    echo "       RUN_ID=$RUN_ID $0 ${ARGS[*]}"
  fi
fi
echo "=============================================================="
[ $FAILED -eq 0 ] || exit 1
