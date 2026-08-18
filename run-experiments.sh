#!/usr/bin/env bash
# GAIA 消融矩阵 —— 串行跑完所有 cell。
#
#   source env.sh
#   ./run-server.sh start                  # 等它加载完
#   ./run-experiments.sh --dry-run         # 先看一遍计划
#   nohup ./run-experiments.sh > logs/experiments.log 2>&1 &
#   tail -f logs/experiments.log
#
# 全程严格串行 —— 任何时刻只有一个 python 进程在打 vLLM。
# 每个 cell 跑完在 logs/.done/ 留标记,重跑会跳过已完成的,中途挂了直接重新执行。
# --force 强制重跑,--dry-run 只打印计划。
#
# ---------------------------------------------------------------------------
# 为什么是这个矩阵
# ---------------------------------------------------------------------------
# 旧矩阵是 3 个 benchmark 各扫一遍 top-k。问题是 SciBench 轨迹只有 1-3 步,
# 上下文管理在那种长度上没有作用空间;AssistantBench 依赖实时网页,不可复现。
# 两个都已放弃(脚本不再跑它们,eval 脚本本身保留)。
#
# 现在全部火力集中在 GAIA,分三组回答三个不同的问题:
#
#   A. 技能预算    —— SkillFlow 的收益是不是"多塞了几篇技能文档"就能买到?
#                     base 扫 k=0/1/4/8,SkillFlow 只在 k=8 对齐。
#
#   B. 上下文管理  —— 这是核心主张。四个 cell 的 what-to-drop 策略完全相同,
#                     只有 what-to-keep 不同:
#                        base        什么都不做
#                        cond_heur   固定标记,零模型调用   (OpenHands 启发式)
#                        cond_llm    逐条摘要,付费         (同策略,付费机制)
#                        skillflow   多通道 residual
#                     赢 base 不算结果,赢 cond_heur 才算;和 cond_llm 的差
#                     才是"结构"的价值 —— 两边花一样的推理钱。
#
#   C. 终止契约    —— --no-submit-tool 复现旧行为,量化 harness 修复本身值多少分。
#                     这一格的差不能算进 SkillFlow 头上。
#
# 第二个 benchmark 是 AppWorld —— GAIA 平均 5-15 步,短到上下文管理没多少作用
# 空间;AppWorld 上限 2000 次 API 调用、默认 1000 次交互,transcript 真的会撑爆
# 32k 窗口,那才是 SkillFlow 声称要解决的场景。它的动作空间是 Python 解释器而
# 不是文件系统,所以走 skillflow.py 的 AppWorldToolset,不用 eval_gaia 那套。
# 没装就整段跳过。
#
# tau2-bench 还没接。DABstep 按要求先不跑。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR=$BASE/logs
DONEDIR=$LOGDIR/.done
RESULTS=$BASE/results
mkdir -p "$LOGDIR" "$DONEDIR" "$RESULTS"

# ---------------------------------------------------------------------------
# 配置(都可以用环境变量覆盖,例如 TOPKS="0 8" LEVELS="1 2 3" ./run-experiments.sh)
# ---------------------------------------------------------------------------
BACKEND=${BACKEND:-qwen}
WORKERS=${WORKERS:-3}
DELAY=${DELAY:-0}                      # 本地 vLLM,不需要限速间隔

TOPKS=${TOPKS:-"0 1 4 8"}              # A 组:base 扫描的 k
K=${K:-8}                              # B/C 组统一在这个 k 上对齐

APPWORLD_SPLIT=${APPWORLD_SPLIT:-dev}     # 正式结果用 test_normal
APPWORLD_WORKERS=${APPWORLD_WORKERS:-1}   # 每题各自开环境,先 1,跑干净了再加
APPWORLD_TIMEOUT=${APPWORLD_TIMEOUT:-1800}
APPWORLD_BUDGET=${APPWORLD_BUDGET:-60000}
# 长程任务必须放开熔断器:默认 40 次工具调用在 GAIA 上够用,在 AppWorld 上会把
# 题目拦腰砍断,量到的是熔断器不是 agent。
APPWORLD_MAX_TOOL_CALLS=${APPWORLD_MAX_TOOL_CALLS:-300}

LEVELS=${LEVELS:-"1 2"}                # GAIA 难度。L3 是 scaffold 差异最大的一档,
                                       # 但 8B 在上面基本是 0 分 —— 想要就 LEVELS="1 2 3"
MAXQ=${MAXQ:-0}                        # 0 = 全量;调试时设小一点

GAIA_TIMEOUT=${GAIA_TIMEOUT:-600}
GAIA_BUDGET=${GAIA_BUDGET:-20000}

# 上下文管理参数。ratio 用 0.5 而不是默认 0.8:32k 窗口上 0.8 的闸门开在 26214,
# 距离窗口顶只剩 6.5k(约 1.6 次工具调用),太窄了。见 test_compression_hook.py。
RATIO=${RATIO:-0.5}
KEEP_FIRST=${KEEP_FIRST:-1}
ATTN_WINDOW=${ATTN_WINDOW:-2}
COND_MAX_CALLS=${COND_MAX_CALLS:-4}

# 每题只跑一次。想要方差估计就 REPEATS=3 —— 已有工作报告同模型内 scaffold
# 差异可达 28 个点,重复跑才能把噪声和效应分开;单次跑省时间,但误差条无从谈起。
REPEATS=${REPEATS:-1}

FORCE=0
DRYRUN=0
for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=1 ;;
    --dry-run) DRYRUN=1 ;;
    *) echo "用法: $0 [--force] [--dry-run]" >&2; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# 前置检查 —— 跑几十个 cell 之前先把会让整批白跑的问题挡掉
# ---------------------------------------------------------------------------
fail() { echo "[FATAL] $*" >&2; exit 1; }

if [ $DRYRUN -eq 0 ]; then
  python -c 'import anthropic' 2>/dev/null \
    || fail "venv 没激活或依赖缺失 —— 先 source env.sh"

  QWEN_URL=${QWEN_BASE_URL:-http://localhost:8000/v1}
  curl -sf -m 5 "${QWEN_URL%/v1}/health" >/dev/null 2>&1 \
    || fail "vLLM 没响应 (${QWEN_URL%/v1}/health) —— 先 ./run-server.sh start 并等它加载完"

  PARQUET=$BASE/GAIA/2023/validation/metadata.parquet
  [ "$(head -c 4 "$PARQUET" 2>/dev/null)" = "PAR1" ] \
    || fail "$PARQUET 不是有效 parquet(LFS 指针?)—— 先 git lfs pull"

  # 两个离线预检。不需要 GPU,几秒钟,但能挡掉最贵的两类错误:
  # 压缩闸门够不到(组件其实没跑),和 scorer / 终止契约回退。
  echo "[预检] 上下文压力闸门 ..."
  python "$BASE/test_compression_hook.py" --compress-ratio "$RATIO" >/dev/null 2>&1 \
    || fail "test_compression_hook.py 失败 —— 单独跑一遍看原因,别带着坏掉的闸门开跑"
  echo "[预检] 终止契约 + GAIA scorer ..."
  python "$BASE/test_contract_and_scorer.py" >/dev/null 2>&1 \
    || fail "test_contract_and_scorer.py 失败 —— 同上"
  echo "[预检] 通过。"

  # web-search 用得上,但不装也能跑(只是联网题会答不好),所以只警告
  curl -sf -m 5 "http://127.0.0.1:${SEARXNG_PORT:-8888}/" >/dev/null 2>&1 \
    || echo "[WARN] SearXNG 没响应 —— 联网类题目会缺证据。./run-searxng.sh start"
fi

# ---------------------------------------------------------------------------
# 公共参数
# ---------------------------------------------------------------------------
MAXQ_ARG=()
[ "$MAXQ" -gt 0 ] 2>/dev/null && MAXQ_ARG=(--max "$MAXQ")

common_args() {
  printf '%s\n' --backend "$BACKEND" --workers "$WORKERS" --delay "$DELAY" \
    --levels $LEVELS --token-budget "$GAIA_BUDGET" --task-timeout "$GAIA_TIMEOUT" \
    "${MAXQ_ARG[@]+"${MAXQ_ARG[@]}"}"
}

cond_args() {   # $1 = heuristic | llm
  printf '%s\n' --condenser "$1" --keep-first "$KEEP_FIRST" \
    --attention-window "$ATTN_WINDOW" --condense-ratio "$RATIO" \
    --condenser-max-calls "$COND_MAX_CALLS"
}

# 朴素 harness(baseline)
base_run() {    # $1 = top-k, 其余透传
  local k=$1; shift
  mapfile -t CA < <(common_args)
  python "$BASE/eval_gaia_with_skills.py" "${CA[@]}" --top-k "$k" "$@" \
    --output "$OUT"
}

# SkillFlow
sf_run() {      # $1 = top-k, 其余透传
  local k=$1; shift
  mapfile -t CA < <(common_args)
  python "$BASE/skillflow.py" eval --benchmark gaia "${CA[@]}" --top-k "$k" \
    --compress-ratio "$RATIO" "$@" --output "$OUT"
}

# AppWorld。baseline 和 SkillFlow 走同一个入口,只差 --framework —— 两边共用
# 同一个 agent loop / 工具面 / 终止契约 / condenser,所以差的只有 framework。
aw_run() {      # $1 = framework, $2 = top-k, 其余透传
  local fw=$1 k=$2; shift 2
  MAX_TOOL_CALLS_PER_TURN=$APPWORLD_MAX_TOOL_CALLS \
  python "$BASE/skillflow.py" eval --benchmark appworld --framework "$fw" \
    --backend "$BACKEND" --appworld-split "$APPWORLD_SPLIT" \
    --workers "$APPWORLD_WORKERS" --delay "$DELAY" --top-k "$k" \
    --token-budget "$APPWORLD_BUDGET" --task-timeout "$APPWORLD_TIMEOUT" \
    --compress-ratio "$RATIO" "${MAXQ_ARG[@]+"${MAXQ_ARG[@]}"}" "$@" \
    --output "$OUT"
}

appworld_ready() {
  python -c 'import appworld' >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# 阶段执行器
# ---------------------------------------------------------------------------
STAGE=0
FAILED=()

run_stage() {
  local name=$1; shift
  STAGE=$((STAGE + 1))
  local marker=$DONEDIR/$name
  local log=$LOGDIR/$name.log
  OUT=$RESULTS/$name.jsonl          # 给 base_run / sf_run 用

  if [ $DRYRUN -eq 1 ]; then
    printf '[%2d] %-34s -> results/%s.jsonl\n' "$STAGE" "$name" "$name"
    return 0
  fi

  if [ $FORCE -eq 0 ] && [ -f "$marker" ]; then
    echo "[$STAGE] SKIP  $name  (完成于 $(cat "$marker"))"
    return 0
  fi

  # eval 脚本都以 "a" 模式写结果。这个 cell 要么没跑过、要么上次失败留了残缺
  # 文件,两种情况都必须先清掉,否则新记录会追加到旧记录后面。
  rm -f "$OUT"

  echo
  echo "--------------------------------------------------------------"
  echo "[$STAGE] RUN   $name        $(date '+%F %T')"
  echo "        结果: $OUT"
  echo "        日志: $log"
  echo "--------------------------------------------------------------"

  local t0=$SECONDS
  "$@" > "$log" 2>&1
  local rc=$?
  local mins=$(( (SECONDS - t0) / 60 ))

  if [ $rc -eq 0 ]; then
    date '+%F %T' > "$marker"
    echo "[$STAGE] DONE  $name  (${mins} 分钟)"
    # 把摘要抬到主日志。现在这一段除了准确率,还带 compression / condenser /
    # termination 三行 —— 想知道组件到底跑没跑,看那三行,不是看代码。
    sed -n '/RESULTS SUMMARY/,/^Saved to/p' "$log" | tail -24
  else
    echo "[$STAGE] FAIL  $name  (exit $rc, ${mins} 分钟)"
    tail -15 "$log"
    FAILED+=("$name")
    # 不中断: 各 cell 互相独立,让整批跑完再一起看
  fi
  return 0
}

# ---------------------------------------------------------------------------
echo "=============================================================="
echo " GAIA 消融矩阵"
echo "   backend=$BACKEND  workers=$WORKERS  levels=[$LEVELS]  repeats=$REPEATS"
echo "   base top-k = [$TOPKS]        对齐 k = $K"
echo "   budget=$GAIA_BUDGET  timeout=${GAIA_TIMEOUT}s  ratio=$RATIO"
echo "   condenser: keep_first=$KEEP_FIRST attention_window=$ATTN_WINDOW"
echo "   appworld : split=$APPWORLD_SPLIT workers=$APPWORLD_WORKERS budget=$APPWORLD_BUDGET timeout=${APPWORLD_TIMEOUT}s tool_calls<=$APPWORLD_MAX_TOOL_CALLS"
[ "$MAXQ" -gt 0 ] 2>/dev/null && echo "   [!] MAXQ=$MAXQ —— 这是冒烟测试,不是正式结果"
echo "   开始: $(date '+%F %T')"
case " $LEVELS " in *" 3 "*) echo "   [!] 含 GAIA L3 —— 8B 在这一档接近 0 分,运行时间显著变长" ;; esac
echo "=============================================================="

for rep in $(seq 1 "$REPEATS"); do
  # REPEATS=1 时不加后缀,保持文件名干净
  if [ "$REPEATS" -gt 1 ]; then SUF="_r$rep"; else SUF=""; fi
  [ "$REPEATS" -gt 1 ] && { echo; echo "########## 第 $rep/$REPEATS 轮 ##########"; }

  # --- A. 技能预算扫描 ----------------------------------------------------
  for k in $TOPKS; do
    run_stage "gaia_base_k${k}${SUF}" base_run "$k"
  done

  # --- B. 上下文管理消融(全部在 k=$K) -----------------------------------
  # gaia_base_k$K 已经在 A 组跑过,就是这一组的 "什么都不做" 那一格。
  mapfile -t CH < <(cond_args heuristic)
  mapfile -t CL < <(cond_args llm)

  run_stage "gaia_cond_heur_k${K}${SUF}"  base_run "$K" "${CH[@]}"
  run_stage "gaia_cond_llm_k${K}${SUF}"   base_run "$K" "${CL[@]}"
  run_stage "gaia_skillflow_k${K}${SUF}"  sf_run   "$K"
  run_stage "gaia_skillflow_cond_k${K}${SUF}" sf_run "$K" "${CH[@]}"

  # --- C. 终止契约 --------------------------------------------------------
  run_stage "gaia_base_k${K}_nocontract${SUF}" base_run "$K" --no-submit-tool

  # --- D. 两条 baseline 实现的一致性校验 -----------------------------------
  # gaia_base_* 走 eval_gaia_with_skills.py,AppWorld 的 baseline 走
  # skillflow.py --framework plain。两者应当给出相近的分数;差太多说明两条
  # baseline 有实现差异,那 AppWorld 和 GAIA 的结论就不能并排放。
  mapfile -t CA < <(common_args)
  run_stage "gaia_plain_k${K}${SUF}" \
    python "$BASE/skillflow.py" eval --benchmark gaia --framework plain \
      "${CA[@]}" --top-k "$K" --compress-ratio "$RATIO" \
      --output "$RESULTS/gaia_plain_k${K}${SUF}.jsonl"

  # --- E. AppWorld(长程) --------------------------------------------------
  if appworld_ready; then
    run_stage "appworld_base_k0${SUF}"              aw_run plain     0
    run_stage "appworld_base_k${K}${SUF}"           aw_run plain     "$K"
    run_stage "appworld_cond_heur_k${K}${SUF}"      aw_run plain     "$K" "${CH[@]}"
    run_stage "appworld_cond_llm_k${K}${SUF}"       aw_run plain     "$K" "${CL[@]}"
    run_stage "appworld_skillflow_k${K}${SUF}"      aw_run skillflow "$K"
    run_stage "appworld_skillflow_cond_k${K}${SUF}" aw_run skillflow "$K" "${CH[@]}"
  elif [ $DRYRUN -eq 1 ]; then
    echo "     (跳过 AppWorld: 未安装)"
  else
    echo "[WARN] AppWorld 未安装,跳过全部 AppWorld cell。"
    echo "       pip install appworld && appworld install && appworld download data"
  fi
done

# ---------------------------------------------------------------------------
[ $DRYRUN -eq 1 ] && { echo; echo "(dry-run,未执行) 共 $STAGE 个 cell"; exit 0; }

echo
echo "=============================================================="
echo " 全部结束: $(date '+%F %T')"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo " ${STAGE} 个 cell 全部成功。"
else
  echo " ${#FAILED[@]}/${STAGE} 个 cell 失败:"
  for f in "${FAILED[@]}"; do echo "   - $f   (日志: $LOGDIR/$f.log)"; done
  echo " 修好后重跑本脚本,已完成的会自动跳过。"
fi
echo " 结果文件: $RESULTS/"
echo
echo " 看结论之前先确认组件真的跑了:"
echo "   grep -h 'compression fired\|condenser \|termination' $LOGDIR/*.log"
echo
echo " AppWorld 官方聚合分(TGC/SGC)另外跑:"
echo "   appworld evaluate <experiment_name> $APPWORLD_SPLIT"
echo "   experiment_name = 结果文件名去掉 .jsonl,例如 appworld_skillflow_k8"
echo "=============================================================="
