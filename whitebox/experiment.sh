#!/usr/bin/env bash
# 一条命令：从「代码是不是最新的」到「论文素材躺在一个目录里」。
#
#   ./experiment.sh --smoke        # 几题几层验通路,一两分钟,数字无意义
#   ./experiment.sh --phase a      # 只跑 Tier A（1.7B,十几分钟,可以前台看）
#   ./experiment.sh                # 两梯全跑（Tier B 是 8B,小时级 —— 用 nohup）
#
#   nohup ./experiment.sh > logs/exp-$(date +%m%d).log 2>&1 &
#   tail -f logs/exp-*.log
#
# 它不重新实现流水线。阶段表、门槛、断点续跑都还在 run-whitebox.sh 里；这个脚本
# 只负责把「跑之前必须确认的」「跑」「跑完必须收的」按顺序串起来,并且在每一步
# 把「继续下去还有没有意义」明确判一次。写它是因为那三件事以前散在 README 的
# 三个小节里,靠人记得照做 —— e6_diagnose 就是这么被忘了几个月的。
#
# 退出码：0 全部跑完；1 前置检查没过（什么都没跑）；2 跑到一半有阶段失败。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$BASE/.." && pwd)"
cd "$BASE" || exit 1

PHASE=all
SMOKE=()
RESTORE=0
PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --phase)   PHASE="${2:-all}"; shift ;;
    --smoke)   SMOKE=(--smoke) ;;
    # 跑完把 vLLM 放回去。默认不放：这台机器上黑盒那批实验也在用 GPU,替别人
    # 决定什么时候把 16GB 拿回去不是这个脚本该干的事。
    --restore-server) RESTORE=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *)         PASS+=("$1") ;;          # 其余原样传给 run-whitebox.sh
  esac
  shift
done

RUN_ID=${RUN_ID:-$(date '+%Y%m%d-%H%M%S')}
OUT=$BASE/results/$RUN_ID

hr() { printf '=%.0s' $(seq 70); echo; }
step() { echo; hr; echo " $*"; hr; }

# ---------------------------------------------------------------- 0. 前置
step "0. 前置检查"

# --smoke must never share a results directory with a real run.
#
# A stage skips itself when its summary.json already exists -- that is what
# makes an interrupted run resumable, and it is keyed on the RUN_ID alone. A
# smoke pass writes exactly those files with 8 items and 4 layers, so a real
# run started afterwards under the same RUN_ID skips every stage and reports
# the smoke numbers as results. Nothing in the summary says they are smoke:
# n=8 and "layers 0..24" are the only tell, and they are easy to read past.
#
# The obvious fix is to tell people not to reuse the id, which is the fix that
# already failed. Giving smoke its own suffix makes the collision impossible.
if [ -n "${SMOKE[0]+x}" ] && [ "${RUN_ID%-smoke}" = "$RUN_ID" ]; then
  RUN_ID="$RUN_ID-smoke"
fi
OUT=$BASE/results/$RUN_ID

echo "run id     : $RUN_ID"
echo "梯队       : $PHASE${SMOKE[0]+   (smoke)}"
echo "commit     : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '?')"

# 跑的是不是推上去的那份代码。这一条挂过：2026-08-25 那次整跑用的是旧代码,
# --filler / --boot / errors 分层 / --control 四处新对照一个都没生效,而结果
# 看起来完全正常 —— 直到有人去翻为什么某一列是空的。
dirty=$(git -C "$REPO" status --porcelain 2>/dev/null | wc -l)
[ "$dirty" -gt 0 ] && echo "[!] 工作区有 $dirty 个文件没提交 —— 跑的不是仓库里那份"
if git -C "$REPO" rev-parse --verify -q origin/master >/dev/null 2>&1; then
  behind=$(git -C "$REPO" rev-list --count HEAD..origin/master 2>/dev/null || echo 0)
  [ "${behind:-0}" -gt 0 ] && \
    echo "[!] 落后 origin/master $behind 个提交 —— 先 git fetch && git reset --hard origin/master"
fi

if [ ! -f "$BASE/whitebox.conf" ]; then
  echo "[!] 没有 whitebox.conf,用的是默认模型路径。要改就"
  echo "    cp whitebox.conf.example whitebox.conf"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  echo "显存已占用 : ${used:-?} MiB"
  if [ "${used:-0}" -gt 4000 ] 2>/dev/null && [ "$PHASE" != "a" ]; then
    echo
    echo "[FAIL] 要跑 8B 那一梯,但显存已被占用 —— 多半是 vLLM。先："
    echo "         $REPO/run-server.sh stop"
    echo "       只跑 Tier A 的话 1.7B 可以和它共存：--phase a"
    exit 1
  fi
fi

# ---------------------------------------------------------------- 1. 跑
# selftest 是 run-whitebox.sh 里的硬门槛,不过就直接退出,所以这里不用再判一次。
# 干预机制坏掉照样产出数字,只是没有意义 —— 那种数字比报错难发现得多。
step "1. 流水线（阶段表见 ./run-whitebox.sh --list）"
RUN_ID=$RUN_ID ./run-whitebox.sh --phase "$PHASE" \
  ${SMOKE[0]+"${SMOKE[@]}"} ${PASS[0]+"${PASS[@]}"}
rc=$?

# ---------------------------------------------------------------- 2. 收
step "2. 产物"

echo "run 目录   : results/$RUN_ID"
if [ -d "$OUT/paper" ]; then
  echo "论文图     : results/$RUN_ID/paper/"
  ls -1 "$OUT/paper" 2>/dev/null | sed 's/^/               /'
  echo
  echo "  取回本机覆盖论文目录里的同名文件即可。Tier A 的 E2 那张是正文的"
  echo "  Figure 2（fig-e2-tierA.tex -> fig_e2sweep.tex）。"
else
  echo "[!] 没有 paper/ —— figs 阶段没跑成,或者这一跑里没有层扫描"
fi

# 末层恒等检查：补最后一个 block 的输出必须精确复现源前向。它是这条流水线
# 唯一一个能端到端证明补丁通路接对了的数,所以在这里再喊一次。
step "3. 通路自证"
found=0
for f in "$OUT"/e2-*/  ; do
  [ -d "$f" ] || continue
  log=$OUT/logs/$(basename "$f").log
  [ -f "$log" ] || continue
  line=$(grep -a "末层恒等检查" "$log" | tail -1)
  [ -n "$line" ] && { echo "  $(basename "$f"): ${line#*] }"; found=1; }
done
[ $found -eq 0 ] && echo "  （这一跑里没有 e2 阶段,没有可自证的东西）"

if [ $RESTORE -eq 1 ]; then
  step "4. 把 vLLM 放回去"
  "$REPO/run-server.sh" start
else
  echo
  echo "vLLM 没有自动重启。黑盒那批实验要用的话："
  echo "  $REPO/run-server.sh start"
fi

echo
if [ $rc -ne 0 ]; then
  echo "[!] 有阶段失败,日志在 results/$RUN_ID/logs/。修完重跑同一个 RUN_ID"
  echo "    就行,跑成功的阶段会跳过：RUN_ID=$RUN_ID $0 --phase $PHASE"
  exit 2
fi
echo "完成。RUN_ID=$RUN_ID"
