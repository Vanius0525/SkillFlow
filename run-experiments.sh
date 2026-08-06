#!/usr/bin/env bash
# 顺序跑完整实验矩阵: 朴素 harness 扫 top-k 0/1/4/8，SkillFlow 只跑 k=8，
# 三个 benchmark 各一套 —— 3 x (4 + 1) = 15 组。
#
#   source env.sh
#   ./run-server.sh start          # 等它加载完
#   nohup ./run-experiments.sh > logs/experiments.log 2>&1 &
#   tail -f logs/experiments.log
#
# 全程严格串行 —— 任何时刻只有一个 python 进程在跑，不会出现两组 worker
# 同时打 vLLM 的情况。
#
# 每组跑完在 logs/.done/ 留一个标记，重跑本脚本会跳过已完成的组，所以中途挂了
# 直接重新执行即可。要强制重跑用 --force，或删掉对应标记文件。
# 用 --dry-run 先看一遍将要执行的命令。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR=$BASE/logs
DONEDIR=$LOGDIR/.done
RESULTS=$BASE/results
mkdir -p "$LOGDIR" "$DONEDIR" "$RESULTS"

# 每组的三个产物同名，便于对照:
#   results/<组名>.jsonl   logs/<组名>.log   logs/.done/<组名>
# 例如 results/scibench_baseline_k4.jsonl / logs/scibench_baseline_k4.log

# ---------------------------------------------------------------------------
# 配置（都可以用环境变量覆盖，例如 TOPKS="0 1" ./run-experiments.sh）
# ---------------------------------------------------------------------------
TOPKS=${TOPKS:-"0 1 4 8"}              # 朴素 harness 扫描的 k
SKILLFLOW_TOPKS=${SKILLFLOW_TOPKS:-"8"}  # SkillFlow 只跑 k=8
WORKERS=${WORKERS:-3}
DELAY=${DELAY:-0}                 # 本地 vLLM，不需要给 API 限速留间隔
BACKEND=${BACKEND:-qwen}

FAST_TIMEOUT=${FAST_TIMEOUT:-300}     # AssistantBench / SciBench
FAST_BUDGET=${FAST_BUDGET:-10000}
GAIA_TIMEOUT=${GAIA_TIMEOUT:-600}     # GAIA: 题目更长，附件更多
GAIA_BUDGET=${GAIA_BUDGET:-20000}

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
# 前置检查 —— 跑 24 组之前先把会让整批白跑的问题挡掉
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
    || fail "$PARQUET 不是有效 parquet（LFS 指针？）—— 先 git lfs pull"

  # web-search 用得上，但不装也能跑（只是联网题会答不好），所以只警告
  curl -sf -m 5 "http://127.0.0.1:${SEARXNG_PORT:-8888}/" >/dev/null 2>&1 \
    || echo "[WARN] SearXNG 没响应 —— 联网类题目会缺证据。./run-searxng.sh start"
fi

echo "=============================================================="
echo " 实验矩阵"
echo "   backend=$BACKEND  workers=$WORKERS  delay=$DELAY"
echo "   朴素 harness top-k = [$TOPKS]"
echo "   SkillFlow  top-k = [$SKILLFLOW_TOPKS]"
echo "   AssistantBench/SciBench: budget=$FAST_BUDGET timeout=${FAST_TIMEOUT}s"
echo "   GAIA:                    budget=$GAIA_BUDGET timeout=${GAIA_TIMEOUT}s"
echo "   开始: $(date '+%F %T')"
echo "=============================================================="

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
  local out=$RESULTS/$name.jsonl

  if [ $DRYRUN -eq 1 ]; then
    printf '[%2d] %-30s -> results/%s.jsonl\n' "$STAGE" "$name" "$name"
    printf '     %s\n' "$*"
    return 0
  fi

  if [ $FORCE -eq 0 ] && [ -f "$marker" ]; then
    echo "[$STAGE] SKIP  $name  (完成于 $(cat "$marker"))"
    return 0
  fi

  # 所有 eval 脚本都以 "a" 模式写结果。这一组要么没跑过、要么上次失败留下了
  # 残缺文件，两种情况都必须先清掉，否则重跑会把新记录追加到旧记录后面。
  rm -f "$out"

  echo
  echo "--------------------------------------------------------------"
  echo "[$STAGE] RUN   $name        $(date '+%F %T')"
  echo "        $*"
  echo "        结果: $out"
  echo "        日志: $log"
  echo "--------------------------------------------------------------"

  local t0=$SECONDS
  "$@" > "$log" 2>&1
  local rc=$?
  local mins=$(( (SECONDS - t0) / 60 ))

  if [ $rc -eq 0 ]; then
    date '+%F %T' > "$marker"
    echo "[$STAGE] DONE  $name  (${mins} 分钟)"
    # 把结果摘要抬到主日志，省得挨个翻子日志
    sed -n '/RESULTS SUMMARY/,/^===/p' "$log" | tail -12
  else
    echo "[$STAGE] FAIL  $name  (exit $rc, ${mins} 分钟)"
    tail -15 "$log"
    FAILED+=("$name")
    # 不中断: 各组互相独立，让整批跑完再一起看
  fi
  return 0
}

# eval_assistant_with_skill.py 只接受 --output-prefix，自己拼成
# "<prefix>_k<K>.jsonl"，所以传去掉 _k<K> 的组名，拼出来正好等于组名。
baseline_assistant() { python "$BASE/eval_assistant_with_skill.py" --backend "$BACKEND" \
    --top-k "$1" --workers "$WORKERS" --delay "$DELAY" \
    --token-budget $FAST_BUDGET --task-timeout $FAST_TIMEOUT \
    --output-prefix "$RESULTS/assistantbench_baseline"; }

baseline_scibench() { python "$BASE/eval_scibench_with_skills.py" --backend "$BACKEND" \
    --top-k "$1" --workers "$WORKERS" --delay "$DELAY" \
    --token-budget $FAST_BUDGET --task-timeout $FAST_TIMEOUT \
    --output "$RESULTS/scibench_baseline_k$1.jsonl"; }

baseline_gaia() { python "$BASE/eval_gaia_with_skills.py" --backend "$BACKEND" \
    --top-k "$1" --workers "$WORKERS" --delay "$DELAY" \
    --token-budget $GAIA_BUDGET --task-timeout $GAIA_TIMEOUT \
    --output "$RESULTS/gaia_baseline_k$1.jsonl"; }

skillflow_run() { local bench=$1 k=$2 budget=$3 timeout=$4
  python "$BASE/skillflow.py" eval --backend "$BACKEND" --benchmark "$bench" \
    --top-k "$k" --workers "$WORKERS" --delay "$DELAY" \
    --token-budget "$budget" --task-timeout "$timeout" \
    --output "$RESULTS/${bench}_skillflow_k$k.jsonl"; }

# ---------------------------------------------------------------------------
# 1. AssistantBench
# ---------------------------------------------------------------------------
for k in $TOPKS; do run_stage "assistantbench_baseline_k$k" baseline_assistant "$k"; done
for k in $SKILLFLOW_TOPKS; do
  run_stage "assistantbench_skillflow_k$k" skillflow_run assistantbench "$k" $FAST_BUDGET $FAST_TIMEOUT
done

# ---------------------------------------------------------------------------
# 2. SciBench
# ---------------------------------------------------------------------------
for k in $TOPKS; do run_stage "scibench_baseline_k$k" baseline_scibench "$k"; done
for k in $SKILLFLOW_TOPKS; do
  run_stage "scibench_skillflow_k$k" skillflow_run scibench "$k" $FAST_BUDGET $FAST_TIMEOUT
done

# ---------------------------------------------------------------------------
# 3. GAIA
#
# eval_gaia_with_skills.py 现在支持 k=0，且默认读 scibench_skills（和其余入口
# 一致），所以这里能和上面两个 benchmark 用完全对称的结构。
# 注意 eval_gaia.py 不能当基线: 它是 no-tools 的纯问答，也没有 --backend，
# 只能打 Anthropic API。
# ---------------------------------------------------------------------------
for k in $TOPKS; do run_stage "gaia_baseline_k$k" baseline_gaia "$k"; done
for k in $SKILLFLOW_TOPKS; do
  run_stage "gaia_skillflow_k$k" skillflow_run gaia "$k" $GAIA_BUDGET $GAIA_TIMEOUT
done

# ---------------------------------------------------------------------------
[ $DRYRUN -eq 1 ] && { echo; echo "(dry-run，未执行)"; exit 0; }

echo
echo "=============================================================="
echo " 全部结束: $(date '+%F %T')"
if [ ${#FAILED[@]} -eq 0 ]; then
  echo " ${STAGE} 组全部成功。"
else
  echo " ${#FAILED[@]}/${STAGE} 组失败:"
  for f in "${FAILED[@]}"; do echo "   - $f   (日志: $LOGDIR/$f.log)"; done
  echo " 修好后重跑本脚本，已完成的组会自动跳过。"
fi
echo " 结果文件: $RESULTS/"
echo "=============================================================="
