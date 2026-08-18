#!/usr/bin/env bash
# GAIA 上的 scaffold 横向对比:SkillFlow vs 外部权威 harness。
#
#   source env.sh
#   ./run-server.sh start
#   ./setup-external.sh              # 先把外部依赖装好、体检过
#   ./experiments-agents.sh --dry-run
#   nohup ./experiments-agents.sh > logs/agents.log 2>&1 &
#
# ---------------------------------------------------------------------------
# 这个脚本和 run-experiments.sh 的区别
# ---------------------------------------------------------------------------
# run-experiments.sh 跑的是内部消融:我们自己的 baseline 在不同上下文管理策略
# 下的表现,回答"SkillFlow 的收益从哪来"。
#
# 这个脚本一个自家 baseline 都不跑。它回答另一个问题:把 SkillFlow 放到公开
# 的、别人也在用的 scaffold 旁边,它站得住吗。所以这里的每一行都是一个完整的
# 独立 harness,各跑各的 agent loop、各自的工具、各自的终止方式:
#
#   skillflow    我们的方法                          (JSON tool call)
#   smolagents   HF CodeAgent,GAIA 上最强的开源 scaffold (Python 代码动作)
#   inspect      UK AISI 的 react agent + 官方 GAIA eval  (中立参考实现)
#
# 四件事严格对齐,其余一概不干预:
#   1. 同一个模型、同一个 vLLM 端点     —— 差的是 scaffold,不是权重
#   2. 同一批 GAIA 题目(同 levels)
#   3. 官方 GAIA scorer
#   4. 同样的每题墙钟上限 + 同样的并发(CONCURRENCY)
#
# 注意:三者的 token 口径不完全可比(各自的 prompt 开销不同),所以 token 只
# 作为成本参考,结论看准确率。
#
# Magentic-One 没有接 —— 它要 Playwright + 浏览器,而且 1+4 个 agent 的 GAIA
# adapter 是另一份工作量。setup-external.sh --only magentic 只负责装依赖。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 每次调用落到自己的 run 目录,跑第二遍不会盖掉第一遍。时间戳排序即时间序,
# 不用另存元数据就能看出先后。
#
# .done 标记也放在 run 目录里,于是"续跑"和"重跑"由 RUN_ID 一个变量决定:
#   ./experiments-agents.sh                      新的一次,全跑
#   RUN_ID=20260818-175613 ./experiments-agents.sh   接着那次跑,已完成的跳过
# 这一点是有意的 —— 如果 .done 留在全局位置,新 run 目录会是空的、标记却说
# 做完了,于是产出一批空结果还报成功。
RUN_ID=${RUN_ID:-$(date '+%Y%m%d-%H%M%S')}
LOGDIR=$BASE/logs/$RUN_ID
DONEDIR=$LOGDIR/.done
RESULTS=$BASE/results/$RUN_ID
mkdir -p "$LOGDIR" "$DONEDIR" "$RESULTS"

# latest 软链省得每次记时间戳。指向最近一次*启动*的 run,不是最近一次成功的。
# 软链建不了(比如同名实体目录挡着)就算了,只是便利,不该因此中断整批。
ln -sfn "$RESULTS" "$BASE/results/latest" 2>/dev/null || true
ln -sfn "$LOGDIR"  "$BASE/logs/latest"    2>/dev/null || true

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
BACKEND=${BACKEND:-qwen}
# 默认只跑 L1+L2。L3 是可选的:LEVELS="1 2 3"。
# 它是 scaffold 差异最大的一档,但 8B 在上面基本是 0 分,加进来主要是拉长运行
# 时间而不是增加区分度 —— 想要就显式打开。
LEVELS=${LEVELS:-"1 2"}
MAXQ=${MAXQ:-0}                        # 0 = 全量
# 每题只跑一次。想要方差估计就 REPEATS=3(见 run-experiments.sh 里的说明)。
REPEATS=${REPEATS:-1}

# 每题墙钟上限,三个 scaffold 共用。300s 是为了让整批跑得完,代价是更多题会被
# 截断而不是答错 —— 两者在准确率里长得一样,所以跑完务必看一眼截断率(见脚本
# 末尾提示),截断率高的话这批数字反映的是时间预算,不是 scaffold。
TIMEOUT=${TIMEOUT:-300}

# 并发必须三家一致,否则比的不只是 scaffold。三家共用一台 vLLM:并发一高,
# 单个请求排队变慢,同样的墙钟上限就会砍掉更多题 —— 那个准确率差是
# 并发造成的,不是 scaffold 造成的。
#
# 特别注意 inspect:它默认自适应并发(min=10 start=20 max=100),不显式限制的话
# 会拿 20+ 路并发去打这台 4090,既拖垮服务也把它自己的题跑超时。
CONCURRENCY=${CONCURRENCY:-3}
BUDGET=${BUDGET:-20000}                # 只有我们自己的 harness 认 token 预算
K=${K:-8}
RATIO=${RATIO:-0.5}

SMOL_MAX_STEPS=${SMOL_MAX_STEPS:-20}

# Inspect:容器里通常起不了 Docker daemon,所以默认 local 沙箱。
# 有可用的 Docker 就设 INSPECT_SANDBOX=docker 换回官方默认配置。
INSPECT_SANDBOX=${INSPECT_SANDBOX:-local}
INSPECT_MODEL=${INSPECT_MODEL:-openai-api/local/${QWEN_MODEL:-Qwen/Qwen3-8B}}
# inspect_evals 从这个缓存目录下的 gaia_dataset/GAIA 读 GAIA(见 constants.py:
# INSPECT_EVALS_CACHE_DIR,不设则是 platformdirs 的 user_cache_dir)。指到仓库
# 副本填充出来的缓存,再配合 run_inspect_gaia.py 换掉那个无条件的
# snapshot_download,才不需要 HF_TOKEN。见 setup-external.sh。
INSPECT_EVALS_CACHE_DIR=${INSPECT_EVALS_CACHE_DIR:-$BASE/.inspect_cache}
export INSPECT_EVALS_CACHE_DIR

QWEN_URL=${QWEN_BASE_URL:-http://localhost:8000/v1}
MODEL_ID=${QWEN_MODEL:-Qwen/Qwen3-8B}

# 顺序有意为之:先跑两个外部 baseline,最后跑 skillflow。外部 scaffold 更容易
# 因为版本/依赖问题当场炸,早跑早发现;把自己的方法放最后,前面挂了也不影响它。
SCAFFOLDS=${SCAFFOLDS:-"smolagents inspect skillflow"}

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
# 前置检查
# ---------------------------------------------------------------------------
fail() { echo "[FATAL] $*" >&2; exit 1; }
have() { python -c "import $1" >/dev/null 2>&1; }

if [ $DRYRUN -eq 0 ]; then
  python -c 'import anthropic' 2>/dev/null || fail "venv 没激活 —— source env.sh"
  curl -sf -m 5 "${QWEN_URL%/v1}/health" >/dev/null 2>&1 \
    || fail "vLLM 没响应 ($QWEN_URL) —— ./run-server.sh start"
  PARQUET=$BASE/GAIA/2023/validation/metadata.parquet
  [ "$(head -c 4 "$PARQUET" 2>/dev/null)" = "PAR1" ] \
    || fail "GAIA metadata.parquet 是 LFS 指针 —— git lfs pull"
  python "$BASE/test_contract_and_scorer.py" >/dev/null 2>&1 \
    || fail "test_contract_and_scorer.py 失败 —— scorer/契约有回退,先修"
  echo "[预检] 通过。"
fi

# ---------------------------------------------------------------------------
# 阶段执行器
# ---------------------------------------------------------------------------
# cell 名一律加 agents_ 前缀:run-experiments.sh 里也有一个 gaia_skillflow_k8,
# 同名会互相覆盖 results/ 并共用 logs/.done 标记,两边结果就串了。
STAGE=0; FAILED=(); SKIPPED=()

run_stage() {
  local name=$1; shift
  STAGE=$((STAGE + 1))
  local marker=$DONEDIR/$name log=$LOGDIR/$name.log
  OUT=$RESULTS/$name.jsonl

  if [ $DRYRUN -eq 1 ]; then
    printf '[%2d] %-36s -> results/%s/%s.jsonl\n' "$STAGE" "$name" "$RUN_ID" "$name"
    return 0
  fi
  if [ $FORCE -eq 0 ] && [ -f "$marker" ]; then
    echo "[$STAGE] SKIP  $name  (完成于 $(cat "$marker"))"; return 0
  fi
  rm -f "$OUT"

  echo
  echo "--------------------------------------------------------------"
  echo "[$STAGE] RUN   $name        $(date '+%F %T')"
  echo "        日志: $log"
  echo "--------------------------------------------------------------"

  local t0=$SECONDS
  "$@" > "$log" 2>&1
  local rc=$? mins=$(( (SECONDS - t0) / 60 ))

  if [ $rc -eq 0 ]; then
    date '+%F %T' > "$marker"
    echo "[$STAGE] DONE  $name  (${mins} 分钟)"
    sed -n '/RESULTS SUMMARY/,/^Saved to/p' "$log" | tail -20
  else
    echo "[$STAGE] FAIL  $name  (exit $rc, ${mins} 分钟)"
    tail -20 "$log"
    FAILED+=("$name")
  fi
  return 0
}

MAXQ_ARG=(); [ "$MAXQ" -gt 0 ] 2>/dev/null && MAXQ_ARG=(--max "$MAXQ")

# --- 1. SkillFlow (我们的方法) ---------------------------------------------
sf_run() {
  python "$BASE/skillflow.py" eval --benchmark gaia --framework skillflow \
    --backend "$BACKEND" --levels $LEVELS --top-k "$K" \
    --workers "$CONCURRENCY" --delay 0 --compress-ratio "$RATIO" \
    --token-budget "$BUDGET" --task-timeout "$TIMEOUT" \
    "${MAXQ_ARG[@]+"${MAXQ_ARG[@]}"}" --output "$OUT"
}

# --- 2. smolagents CodeAgent ------------------------------------------------
smol_run() {
  python "$BASE/run_smolagents_gaia.py" \
    --levels $LEVELS --model "$MODEL_ID" --base-url "$QWEN_URL" \
    --max-steps "$SMOL_MAX_STEPS" --task-timeout "$TIMEOUT" \
    --workers "$CONCURRENCY" \
    "${MAXQ_ARG[@]+"${MAXQ_ARG[@]}"}" --output "$OUT"
}

# --- 3. Inspect AI + inspect_evals -----------------------------------------
# Inspect 自带 GAIA task、自带 scorer、自带日志格式,所以这里只是把它启动起来,
# 结果留在它自己的 ./logs/ 里(.eval 文件),用 `inspect view` 看。
# 它的 level 是靠不同 task 名区分的,不是一个 --levels 参数。
inspect_run() {
  local tasks=""
  for l in $LEVELS; do tasks="$tasks inspect_evals/gaia_level$l"; done
  local limit=()
  [ "$MAXQ" -gt 0 ] 2>/dev/null && limit=(--limit "$MAXQ")

  # 不设 HF_HUB_OFFLINE。inspect_evals 无条件调用
  #   snapshot_download(..., local_dir=GAIA_DATASET_DIR)
  # 而带 local_dir 的调用必须先列远端文件树才知道该放哪些文件,所以离线模式并
  # 不会让它改读本地副本 —— 只会让它直接失败(OfflineModeIsEnabled)。
  # 改由 run_inspect_gaia.py 处理:本地副本齐全就把 snapshot_download 换成
  # "返回本地目录",副本不在就原样退回上游的下载逻辑。
  unset HF_HUB_OFFLINE

  # openai-api/<provider>/<model> 的凭据来自 <PROVIDER>_API_KEY 和
  # <PROVIDER>_BASE_URL,不是 OPENAI_*。provider 名取模型串的第二段并大写,
  # 连字符换下划线(环境变量名不允许连字符)。所以 .../local/... 要的是
  # LOCAL_API_KEY / LOCAL_BASE_URL。名字从 $INSPECT_MODEL 推导而不是写死,
  # 这样换 provider 名也不会再撞一次同样的墙。
  local prov
  prov=$(printf '%s' "$INSPECT_MODEL" | awk -F/ '{print $2}' | tr 'a-z-' 'A-Z_')
  if [ -z "$prov" ]; then
    echo "[FATAL] INSPECT_MODEL='$INSPECT_MODEL' 不是 openai-api/<provider>/<model> 形式" >&2
    return 1
  fi

  env "${prov}_API_KEY=${OPENAI_API_KEY:-EMPTY}" \
      "${prov}_BASE_URL=$QWEN_URL" \
      OPENAI_BASE_URL="$QWEN_URL" OPENAI_API_KEY="${OPENAI_API_KEY:-EMPTY}" \
  python "$BASE/run_inspect_gaia.py" eval $tasks \
    --model "$INSPECT_MODEL" \
    --sandbox "$INSPECT_SANDBOX" \
    --time-limit "$TIMEOUT" \
    --max-connections "$CONCURRENCY" \
    --max-samples "$CONCURRENCY" \
    --log-dir "$RESULTS/inspect_logs" \
    "${limit[@]+"${limit[@]}"}"
}


# ---------------------------------------------------------------------------
echo "=============================================================="
echo " GAIA scaffold 横向对比"
echo "   模型     : $MODEL_ID @ $QWEN_URL"
echo "   levels   : [$LEVELS]   repeats=$REPEATS   timeout=${TIMEOUT}s/题"
echo "   并发     : $CONCURRENCY(三家一致 —— 不一致的话准确率差里会混进排队效应)"
echo "   scaffolds: $SCAFFOLDS"
echo "   inspect  : sandbox=$INSPECT_SANDBOX  model=$INSPECT_MODEL"
[ "$MAXQ" -gt 0 ] 2>/dev/null && echo "   [!] MAXQ=$MAXQ —— 冒烟测试,不是正式结果"
echo "   run id   : $RUN_ID   ->  results/$RUN_ID/"
echo "   开始     : $(date '+%F %T')"
case " $LEVELS " in *" 3 "*) echo "   [!] 含 GAIA L3 —— 8B 在这一档接近 0 分,运行时间显著变长" ;; esac
echo "=============================================================="

# 配置快照。几周后回头看一堆 run 目录时,光靠目录名分不出哪个是 MAXQ=3 的冒烟、
# 哪个是全量;记下 git commit 是因为 scaffold 代码本身也在动。
{
  echo "run_id      : $RUN_ID"
  echo "started     : $(date '+%F %T %z')"
  echo "git_commit  : $(git -C "$BASE" rev-parse --short HEAD 2>/dev/null || echo '(not a git repo)')"
  echo "git_dirty   : $(git -C "$BASE" status --porcelain 2>/dev/null | wc -l) files modified"
  echo "model       : $MODEL_ID @ $QWEN_URL"
  echo "levels      : $LEVELS"
  echo "maxq        : $MAXQ  (0 = 全量)"
  echo "repeats     : $REPEATS"
  echo "timeout     : ${TIMEOUT}s/题"
  echo "concurrency : $CONCURRENCY"
  echo "scaffolds   : $SCAFFOLDS"
  echo "inspect     : sandbox=$INSPECT_SANDBOX model=$INSPECT_MODEL"
  echo "host        : $(hostname 2>/dev/null || echo '?')"
} > "$RESULTS/run-info.txt"

for rep in $(seq 1 "$REPEATS"); do
  if [ "$REPEATS" -gt 1 ]; then SUF="_r$rep"; echo; echo "##### 第 $rep/$REPEATS 轮 #####"; else SUF=""; fi

  for sc in $SCAFFOLDS; do
    case "$sc" in
      skillflow)
        run_stage "agents_skillflow_k${K}${SUF}" sf_run ;;
      smolagents)
        if [ $DRYRUN -eq 1 ] || have smolagents; then
          run_stage "agents_smolagents${SUF}" smol_run
        else
          echo "[--] SKIP  agents_smolagents${SUF} —— 未安装 (./setup-external.sh --only smolagents)"
          SKIPPED+=("agents_smolagents${SUF}")
        fi ;;
      inspect)
        if [ $DRYRUN -eq 1 ] || { have inspect_ai && have inspect_evals; }; then
          GAIA_LOCAL=$INSPECT_EVALS_CACHE_DIR/gaia_dataset/GAIA/2023/validation/metadata.parquet
          if [ $DRYRUN -eq 0 ] && [ -z "${HF_TOKEN:-}" ] && [ ! -f "$GAIA_LOCAL" ]; then
            echo "[--] SKIP  agents_inspect${SUF} —— 既没有 HF_TOKEN 也没有本地 GAIA 副本"
            echo "           跑 ./setup-external.sh 填充本地副本即可,不必申请授权"
            SKIPPED+=("agents_inspect${SUF}")
          else
            run_stage "agents_inspect${SUF}" inspect_run
          fi
        else
          echo "[--] SKIP  agents_inspect${SUF} —— 未安装 (./setup-external.sh --only inspect)"
          SKIPPED+=("agents_inspect${SUF}")
        fi ;;
      *) echo "[WARN] 未知 scaffold: $sc" ;;
    esac
  done
done

[ $DRYRUN -eq 1 ] && { echo; echo "(dry-run,未执行) 共 $STAGE 个 cell"; exit 0; }

echo
echo "=============================================================="
echo " 全部结束: $(date '+%F %T')"
[ ${#SKIPPED[@]} -gt 0 ] && { echo " 跳过 ${#SKIPPED[@]} 个:"; for s in "${SKIPPED[@]}"; do echo "   - $s"; done; }
if [ ${#FAILED[@]} -eq 0 ]; then
  echo " ${STAGE} 个 cell 全部成功。"
else
  echo " ${#FAILED[@]}/${STAGE} 个失败:"
  for f in "${FAILED[@]}"; do echo "   - $f   (日志: $LOGDIR/$f.log)"; done
fi
echo
echo " 本次 run: $RUN_ID   (配置快照: results/$RUN_ID/run-info.txt)"
echo "   skillflow / smolagents : results/$RUN_ID/*.jsonl(同一套格式,官方 scorer)"
echo "   inspect                : inspect view --log-dir results/$RUN_ID/inspect_logs"
if [ ${#FAILED[@]} -gt 0 ]; then
  echo
  echo " 修好之后接着这次跑(已完成的 cell 会跳过,不用从头来):"
  echo "   RUN_ID=$RUN_ID ./experiments-agents.sh"
fi
echo
echo " 截断率(TIMEOUT=${TIMEOUT}s 砍掉了多少题)—— 高的话这批数字反映的是"
echo " 时间预算而不是 scaffold:"
echo "   python summarize-agents.py --results-dir results/$RUN_ID"
echo "   (results/latest 指向最近一次启动的 run)"
echo
echo " 提醒:三者 token 口径不同(各自 prompt 开销不同),结论看准确率,"
echo "       token 只作成本参考。"
echo "=============================================================="
