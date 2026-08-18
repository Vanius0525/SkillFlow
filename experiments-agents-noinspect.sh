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
#   ./experiments-agents-noinspect.sh                # 全量
#   MAXQ=3 ./experiments-agents-noinspect.sh         # 冒烟,每 level 3 题
#   ./experiments-agents-noinspect.sh --dry-run      # 只看会跑哪些 cell
#   RUN_ID=20260818-175613 ./experiments-agents-noinspect.sh   # 接着那次跑
#
# 参数原样透传(--force / --dry-run)。环境变量(MAXQ / LEVELS / TIMEOUT /
# CONCURRENCY / K / REPEATS ...)也一样,含义见 experiments-agents.sh 顶部。
#
# inspect 修好之后就不需要这个脚本了,直接跑 experiments-agents.sh。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 少了 smolagents 就只剩 SkillFlow 一条腿,那不是对比。与其跑几个小时之后在汇总
# 表里才发现只有一行,不如现在就停。确实想单跑 SkillFlow 就 ALLOW_SOLO=1。
if [ "${ALLOW_SOLO:-0}" != "1" ] && ! python -c 'import smolagents' >/dev/null 2>&1; then
  echo "[FATAL] smolagents 没装 —— 这一批会只剩 SkillFlow,没有对照组。" >&2
  echo "        装上: ./setup-external.sh --only smolagents" >&2
  echo "        确实要单跑 SkillFlow: ALLOW_SOLO=1 $0 $*" >&2
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

exec "$BASE/experiments-agents.sh" "$@"
