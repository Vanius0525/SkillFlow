#!/usr/bin/env bash
# Tier B 单独跑：自己的 RUN_ID、自己的 paper/，跑完把新曲线和 latex 收齐。
#
#   ./tierb.sh --check                    # 先做这个：量 8B 的 bf16 误差，然后停
#   ./tierb.sh --smoke --dtype float32    # 再做这个：8B fp32 装不装得下（几分钟）
#   nohup ./tierb.sh --dtype bfloat16 > logs/tierb-$(date +%m%d).log 2>&1 &
#   nohup ./tierb.sh --dtype bfloat16 --full > logs/tierb-$(date +%m%d).log 2>&1 &
#
# 它不重新实现流水线。阶段表、门槛、断点续跑在 run-whitebox.sh，前置检查和产物
# 收集在 experiment.sh；这个脚本只加四件 Tier B 单独跑才需要的事：
#
#   1. 自己的 RUN_ID（默认 tierb-<时间戳>）。§12.3r (e) 建议接在 Tier A 的
#      RUN_ID 里跑，让八条曲线汇进同一个 paper/；单独跑就没有那个汇总，
#      report.py 的交叉校验只看得见 Tier B 这一半。这是取舍，不是错误。
#   2. **dtype 必须显式给**。bf16 下末层恒等读不到 1.000 是 bf16 的性质，
#      不是 bug；但它意味着补丁通路在这一跑里没有端到端自证。用哪个是量过
#      之后的决定（--check），不是默认值，所以这里不给默认值。
#   3. --full 把两条 e2 从 40 题放到 116 题。Tier B 基线 0.819、Δacc 只有
#      +6.9pp(const)/+0.9pp(proc)，40 题里无 skill 答错的约 7 题，
#      "skill 修好的题"这一组只有 3-7 题，读不出东西。116 题时约 8-10 题。
#      代价：两条 e2 各 116x18x4 次前向，墙钟大约翻倍。
#   4. 跑完自动出 e2_acc.py 的读数，并把 latex 片段列成可以直接粘的样子。
#
# 退出码沿用 experiment.sh：0 全跑完，1 前置没过，2 有阶段失败。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$BASE/.." && pwd)"
cd "$BASE" || exit 1

CONFIG="${WB_CONFIG:-$BASE/whitebox.conf}"
# shellcheck source=/dev/null
[ -f "$CONFIG" ] && . "$CONFIG"
PY=${WB_PYTHON:-python}
MAIN_MODEL=${WB_MAIN_MODEL:-$REPO/models/Qwen3-8B}
DEVICE=${WB_DEVICE:-cuda}

DTYPE=""; FULL=0; CHECK=0; SMOKE=(); PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dtype)   DTYPE="${2:-}"; shift ;;
    --full)    FULL=1 ;;
    --check)   CHECK=1 ;;
    --smoke)   SMOKE=(--smoke) ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *)         PASS+=("$1") ;;          # 其余原样传给 experiment.sh
  esac
  shift
done

hr() { printf '=%.0s' $(seq 70); echo; }
step() { echo; hr; echo " $*"; hr; }

# ------------------------------------------------------------- --check
# §12.3r (c)。fp32 那次 OOM 就退 --device cpu --limit 3，慢但不占卡。
if [ $CHECK -eq 1 ]; then
  step "量 8B 的 bf16 误差（跑完自己看，然后用 --dtype 决定）"
  tasks=$BASE/tasks/tier_b2/tasks.jsonl
  skill=$BASE/tasks/tier_b/SKILL.pchem-constants.md
  "$PY" "$BASE/patchcheck.py" --model "$MAIN_MODEL" --device "$DEVICE" \
    --tasks "$tasks" --skill "$skill" --limit 8
  echo
  "$PY" "$BASE/patchcheck.py" --model "$MAIN_MODEL" --device "$DEVICE" \
    --tasks "$tasks" --skill "$skill" --limit 4 --dtype float32
  cat <<'EOF'

怎么读：
  - 两次的 gold logprob 差多少 nats，就是 bf16 在 Tier B 上的误差量级。
    Tier A 上单题 0.5-2.5 nats，39 题平均之后只剩 0.05 —— 大概率 8B 也这样，
    但"大概率"不是量过。
  - fp32 那次跑得动 -> ./tierb.sh --smoke --dtype float32 再确认整条流水线装得下。
  - fp32 OOM -> --dtype bfloat16，并且**把末层恒等读不到 1.000 当已知偏差记下来**，
    上面这个数就是它的量级。那不是新 bug。
EOF
  exit 0
fi

if [ -z "$DTYPE" ]; then
  cat >&2 <<'EOF'
[!] 要显式给 --dtype。

bf16 下末层恒等一定读不到 1.000（bf16 的性质，不是 bug），代价是这一跑的补丁
通路没有端到端自证；fp32 能自证，但 8B 的 32GB 权重在 48GB 卡上装不装得下没人
量过。先量，再决定：

    ./tierb.sh --check                     # 几分钟
    ./tierb.sh --smoke --dtype float32     # 几分钟，落进 -smoke 目录
    ./tierb.sh --dtype <量完定的>
EOF
  exit 1
fi

RUN_ID=${RUN_ID:-tierb-$(date '+%Y%m%d-%H%M%S')}
# experiment.sh 给 smoke 加 -smoke 后缀，下面收产物时要用同一个名字。
[ -n "${SMOKE[0]+x}" ] && [ "${RUN_ID%-smoke}" = "$RUN_ID" ] && RUN_ID="$RUN_ID-smoke"
OUT=$BASE/results/$RUN_ID

export WB_TIERB_DTYPE="$DTYPE"
[ $FULL -eq 1 ] && export WB_E2_LIMIT=116

step "Tier B 单独跑"
echo "  run id   : $RUN_ID      -> results/$RUN_ID/"
echo "  模型     : $MAIN_MODEL"
echo "  精度     : $DTYPE$([ "$DTYPE" = bfloat16 ] && echo '   （末层恒等读不到 1.000 是预期的）')"
echo "  e2 题数  : ${WB_E2_LIMIT:-40}$([ $FULL -eq 1 ] && echo '   （--full：为了「skill 修好的题」那一组）')"
echo "  阶段     : 12 条 Tier B + 前置检查 + figs（./run-whitebox.sh --list 看全表）"

RUN_ID=$RUN_ID ./experiment.sh --phase b \
  ${SMOKE[0]+"${SMOKE[@]}"} ${PASS[0]+"${PASS[@]}"}
rc=$?

# ------------------------------------------------------------- 收
# experiment.sh 已经收过 paper/ 和末层恒等。这里补它不知道的两件事：
# e2 的准确率通道（e2_acc.py 不在阶段表里，它是后处理），和 latex 的粘贴清单。
if [ ! -d "$OUT" ]; then
  echo "[!] 没有 $OUT，什么都没跑起来"
  exit "${rc:-2}"
fi

step "准确率通道 + 分组读数（e2_acc.py）"
mkdir -p "$OUT/paper"
stages=()
for d in "$OUT"/e2-tierB*/; do
  [ -f "$d/per_layer.jsonl" ] && stages+=("$d")
done
if [ ${#stages[@]} -eq 0 ]; then
  echo "  （这一跑里没有跑成的 e2 阶段，跳过）"
else
  txt=$OUT/paper/e2-acc.txt
  "$PY" "$BASE/e2_acc.py" "${stages[@]}" 2>&1 | tee "$txt"
  echo
  echo "  存了一份: results/$RUN_ID/paper/$(basename "$txt")"
  echo "  重点看三处：filler 是不是停在无 skill 基线（停住 = 补丁带的是内容，"
  echo "  不是「上下文里有份长文档」）、别题向量恢复多少（高 = 带的是这份 skill"
  echo "  的共享状态，不到逐题）、以及 fixed 那一组的曲线（行为效应就是它构成的）。"
fi

step "latex"
if [ -d "$OUT/paper" ] && ls "$OUT/paper"/*.tex >/dev/null 2>&1; then
  ls -1 "$OUT/paper"/*.tex | sed "s|^$OUT/paper/|               |"
  cat <<EOF

  取回本机：
    scp -r <server>:$OUT/paper ./tierb-figs

  正文里（每张图三行，\\usepackage{tikz} 之外没有依赖）：

    \\begin{figure}[t] \\centering
      \\input{fig-e2-tierB-const}
      \\caption{Tier B, constants skill: 逐层补丁的恢复率。四条曲线缺一不可 ——
        filler 说恢复是不是关于内容，mean 和 mismatched 说它是不是关于这道题。}
    \\end{figure}

  一条 e2 出三张：
    fig-e2-tierB-*.tex          恢复率（logprob 通道，比值，1.0 = 复现全部行为效应）
    fig-e2-tierB-*-acc.tex      准确率（同一次干预的另一条通道，绝对读数）
    fig-e2-tierB-*-fixed.tex    **新的**：同一次扫描只看 skill 修好的那些题
  两条 e1 各出一张 fig-e1-tierB-*.tex（net 和它的 CI 带）。

  -fixed 那张的 caption 必须写进两件构造性的事，否则会被读成比实际强的主张：
  这一组是**用有 skill 的结果定义的**，组内两个基线按构造就是 0 和 1，只有补丁
  曲线有信息；而且它小（Tier A 13 题，Tier B 不跑 --full 只有 3-7 题）——
  读方向，不要读成比率。
EOF
else
  echo "  [!] 没有 .tex —— figs 阶段没跑成，或者这一跑里没有层扫描"
  echo "      单独补: $PY paperfig.py results/$RUN_ID --all --outdir results/$RUN_ID/paper"
fi

echo
if [ "$rc" -ne 0 ]; then
  echo "[!] 有阶段失败，日志在 results/$RUN_ID/logs/。修完重跑同一个 RUN_ID"
  echo "    就行，跑成功的阶段会跳过："
  echo "    RUN_ID=$RUN_ID ./tierb.sh --dtype $DTYPE$([ $FULL -eq 1 ] && echo ' --full')"
  exit 2
fi
echo "完成。RUN_ID=$RUN_ID"
