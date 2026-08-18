#!/usr/bin/env bash
# GAIA 对比,只跑 smolagents + SkillFlow 两家。
#
# 为什么单独留一个入口
# --------------------
# inspect 那一格现在跑不起来,但卡点跟数据无关 —— GAIA 数据链路是通的(补丁生效、
# 86 道 validation 载入、模型解析成功)。卡的是工具集:官方 GAIA task 的
# default_solver 是
#
#     tools=[bash(code_timeout), python(code_timeout)] + web_browser()
#
# 而 web_browser() 不是进程内工具,是沙箱里的一个服务(官方靠
# aisiuk/inspect-tool-support 镜像提供)。--sandbox local 下探不到它,直接
# PrerequisiteError。详见 HANDOFF.md 的"当前阻塞"。
#
# 这个脚本不复制批次逻辑,只是把 SCAFFOLDS 定死之后转交 experiments-agents.sh。
# 于是 run 目录、.done 续跑、run-info.txt、超时、并发全都和三家版本一致,产出的
# jsonl 可以直接跟以后补上的 inspect 结果并排看 —— 而不是变成"另一套实验"。
#
#   ./experiments-agents-noinspect.sh                # 全量(自动转后台)
#   MAXQ=3 ./experiments-agents-noinspect.sh         # 冒烟,每 level 3 题
#   ./experiments-agents-noinspect.sh --dry-run      # 只看会跑哪些 cell(前台)
#   ./experiments-agents-noinspect.sh --fg           # 强制前台(tmux 里用)
#   RUN_ID=20260818-175613 ./experiments-agents-noinspect.sh   # 接着那次跑
#
# 默认转后台,起来之后可以直接关终端 —— 全量要跑几小时。--fg 关掉这个行为;
# --dry-run 自动留在前台(它就是给你看输出的)。
#
# 其余参数原样透传(--force / --dry-run)。环境变量(MAXQ / LEVELS / TIMEOUT /
# CONCURRENCY / K / REPEATS ...)也一样,含义见 experiments-agents.sh 顶部。
#
# inspect 修好之后就不需要这个脚本了,直接跑 experiments-agents.sh。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 重新执行自己时不能用 $0:`bash 脚本名` 启动的话 $0 是裸文件名,没有目录部分,
# 而 setsid 走 execvp —— 它按 PATH 找,而 . 不在 PATH 上,于是
# "failed to execute: No such file or directory"。用 ./脚本 启动时碰不到,所以
# 这个坑只在换一种调用方式时才现形。绝对路径两种方式都对。
SELF="$BASE/$(basename "${BASH_SOURCE[0]}")"

# --fg 是本脚本自己的开关,不能透传 —— experiments-agents.sh 见到不认识的参数
# 会直接报用法并退出。
FG=0
PASS=()
for arg in "$@"; do
  case "$arg" in
    --fg)      FG=1 ;;
    --dry-run) FG=1; PASS+=("$arg") ;;   # dry-run 转后台没有意义
    *)         PASS+=("$arg") ;;
  esac
done

# 少了 smolagents 就只剩 SkillFlow 一条腿,那不是对比。与其跑几个小时之后在汇总
# 表里才发现只有一行,不如现在就停。确实想单跑 SkillFlow 就 ALLOW_SOLO=1。
if [ "${ALLOW_SOLO:-0}" != "1" ] && ! python -c 'import smolagents' >/dev/null 2>&1; then
  echo "[FATAL] smolagents 没装 —— 这一批会只剩 SkillFlow,没有对照组。" >&2
  echo "        装上: ./setup-external.sh --only smolagents" >&2
  echo "        确实要单跑 SkillFlow: ALLOW_SOLO=1 $SELF $*" >&2
  exit 1
fi

# 顺序和三家版本保持一致:外部 baseline 在前,SkillFlow 最后。外部 scaffold 更
# 容易因为版本/依赖当场炸,早跑早发现;自己的方法放最后,前面挂了也不影响它。
export SCAFFOLDS="smolagents skillflow"

echo "=============================================================="
echo " 两家模式: SCAFFOLDS=\"$SCAFFOLDS\""
echo " inspect 已排除 —— web_browser 需要沙箱服务,--sandbox local 下不可用"
echo " 原因和后续处理见 HANDOFF.md"
echo "=============================================================="

# ---------------------------------------------------------------------------
# 自动转后台
# ---------------------------------------------------------------------------
if [ $FG -eq 0 ] && [ "${AGENTS_DETACHED:-0}" != "1" ]; then

  # experiments-agents.sh 的前置检查跑在子进程里,失败只会落进 console.log。
  # 那意味着你看到"已转入后台"就关了终端,而它两秒后就死了。所以把最容易挂的
  # 两项提到脱离之前、在前台查 —— 剩下的(LFS、scorer 契约)慢一些也罕见,留给
  # 子进程,由下面那句"确认真的起来了"兜底。
  # 万一 SELF 算错(奇怪的调用方式),现在就说清楚 —— 否则报错会是 setsid 那句
  # 难懂的 "failed to execute ...: No such file or directory"。
  [ -f "$SELF" ] || { echo "[FATAL] 找不到自身: $SELF" >&2; exit 1; }

  QWEN_URL=${QWEN_BASE_URL:-http://localhost:8000/v1}
  python -c 'import anthropic' 2>/dev/null \
    || { echo "[FATAL] venv 没激活 —— source env.sh" >&2; exit 1; }
  curl -sf -m 5 "${QWEN_URL%/v1}/health" >/dev/null 2>&1 \
    || { echo "[FATAL] vLLM 没响应 ($QWEN_URL) —— ./run-server.sh start" >&2; exit 1; }

  # RUN_ID 在这里定死再传给子进程。让子进程自己生成的话,console.log 的路径就
  # 和它实际用的 run 目录对不上,你也无从知道结果落在哪。
  RUN_ID=${RUN_ID:-$(date '+%Y%m%d-%H%M%S')}
  mkdir -p "$BASE/logs/$RUN_ID"
  CONSOLE=$BASE/logs/$RUN_ID/console.log

  # setsid 开新会话,彻底没有控制终端;没有 setsid 就退回 nohup(忽略 SIGHUP,
  # 效果够了)。stdin 接 /dev/null,免得后台进程去读终端被 SIGTTIN 停住。
  if command -v setsid >/dev/null 2>&1; then
    AGENTS_DETACHED=1 RUN_ID="$RUN_ID" setsid "$SELF" "${PASS[@]+"${PASS[@]}"}" \
      > "$CONSOLE" 2>&1 < /dev/null &
  else
    AGENTS_DETACHED=1 RUN_ID="$RUN_ID" nohup "$SELF" "${PASS[@]+"${PASS[@]}"}" \
      > "$CONSOLE" 2>&1 < /dev/null &
    disown 2>/dev/null || true
  fi

  echo
  echo " 已转入后台,可以关终端了。"
  echo "   run id : $RUN_ID"
  echo "   产物   : results/$RUN_ID/"
  echo "   总进度 : tail -f logs/$RUN_ID/console.log"
  echo "   单 cell: tail -f logs/$RUN_ID/agents_smolagents.log"
  echo "   还活着 : pgrep -af experiments-agents"
  echo "   停止   : kill \$(cat logs/$RUN_ID/run.pid)"
  echo "   续跑   : RUN_ID=$RUN_ID $SELF"
  echo
  echo " 关之前先确认它真起来了(等几秒):"
  echo "   tail -5 logs/$RUN_ID/console.log"
  exit 0
fi

# 到这里说明已经在后台(或者 --fg)。记下真实 pid 供后续 kill —— 前台那边拿到的
# $! 是 setsid 的,setsid fork 之后自己就退了,那个 pid 不能用。
[ "${AGENTS_DETACHED:-0}" = "1" ] && echo $$ > "$BASE/logs/${RUN_ID}/run.pid"

exec "$BASE/experiments-agents.sh" "${PASS[@]+"${PASS[@]}"}"
