#!/usr/bin/env bash
# 安装 + 体检:对比用的外部 agent harness。
#
#   source env.sh
#   ./setup-external.sh              # 装 + 查
#   ./setup-external.sh --check      # 只查,不装
#   ./setup-external.sh --only smolagents
#
# 三个外部 scaffold 的要求差别很大,这个脚本把差别都摊开、逐项检查,并且在
# 检查不过时直接给出修复命令,而不是让你到跑了三小时之后才发现缺东西。
#
#   smolagents   pip 一条命令,不需要 Docker。最容易接。
#   inspect      两个看起来吓人、其实都能绕过的门槛:
#                 - GAIA 数据在 HF 上是 gated 的,但它用 snapshot_download 且
#                   local_dir 填好就不下载,所以本脚本直接拿仓库里的 GAIA/ 副本
#                   填进去,不用申请授权、不用 HF_TOKEN。
#                 - 官方 GAIA eval 默认在 Docker 里跑 bash,容器里起不了 daemon
#                   时用 --sandbox local。
#   magentic-one 需要 Playwright + 浏览器二进制。目前没有接 runner,只装依赖。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CHECK_ONLY=0
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --only)  ONLY="${2:-}"; shift ;;
    *) echo "用法: $0 [--check] [--only smolagents|inspect|magentic]" >&2; exit 1 ;;
  esac
  shift
done

want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }

PASS=0; WARN=0; FAILN=0
ok()   { echo "  [ OK ]  $*"; PASS=$((PASS+1)); }
warn() { echo "  [WARN]  $*"; WARN=$((WARN+1)); }
bad()  { echo "  [FAIL]  $*"; FAILN=$((FAILN+1)); }
hint() { echo "          -> $*"; }

pyhas() { python -c "import $1" >/dev/null 2>&1; }

echo "=============================================================="
echo " 外部 harness 环境配置"
echo " python : $(command -v python || echo '(缺)')"
echo " 模式   : $([ $CHECK_ONLY -eq 1 ] && echo '只检查' || echo '安装+检查')"
echo "=============================================================="

# ---------------------------------------------------------------------------
echo
echo "--- 0. 公共前提 ---"
if pyhas anthropic; then ok "venv 已激活(anthropic 可导入)"
else bad "venv 没激活或依赖缺失"; hint "source \$BASE/env.sh"; fi

QWEN_URL=${QWEN_BASE_URL:-http://localhost:8000/v1}
if curl -sf -m 5 "${QWEN_URL%/v1}/health" >/dev/null 2>&1; then
  ok "vLLM 在跑 ($QWEN_URL)"
  SERVED=$(curl -sf -m 5 "$QWEN_URL/models" 2>/dev/null \
           | python -c 'import sys,json;print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)
  [ -n "${SERVED:-}" ] && ok "服务的模型: $SERVED" \
    || warn "拿不到 /v1/models 的模型名 —— 外部 harness 的 model_id 必须和它一致"
else
  bad "vLLM 没响应 ($QWEN_URL)"; hint "./run-server.sh start"
fi

# 外部 harness 全都走 OpenAI 协议,统一用这两个环境变量指过去
if [ -z "${OPENAI_API_KEY:-}" ]; then
  warn "OPENAI_API_KEY 未设 —— 本地 vLLM 不校验,但很多客户端要求非空"
  hint "在 env.sh 里加: export OPENAI_API_KEY=EMPTY"
else ok "OPENAI_API_KEY 已设"; fi
if [ "${OPENAI_BASE_URL:-}" = "$QWEN_URL" ]; then ok "OPENAI_BASE_URL 指向本地 vLLM"
else
  warn "OPENAI_BASE_URL 没指向 $QWEN_URL"
  hint "在 env.sh 里加: export OPENAI_BASE_URL=$QWEN_URL"
fi

# ---------------------------------------------------------------------------
if want smolagents; then
echo
echo "--- 1. smolagents (CodeAct 维度;不需要 Docker) ---"
if [ $CHECK_ONLY -eq 0 ] && ! pyhas smolagents; then
  echo "  安装中: pip install 'smolagents[toolkit]'"
  pip install -q 'smolagents[toolkit]' || bad "smolagents 安装失败"
fi
if pyhas smolagents; then
  VER=$(python -c 'import smolagents;print(getattr(smolagents,"__version__","?"))' 2>/dev/null)
  ok "smolagents 已装 (v$VER)"
  python - <<'PY' 2>/dev/null && ok "CodeAgent / OpenAIServerModel / 工具 均可导入" \
    || bad "smolagents 导入不全 —— 版本可能对不上"
from smolagents import CodeAgent, OpenAIServerModel, WebSearchTool, VisitWebpageTool
PY
  # #908: OpenAIServerModel 默认发结构化 content parts,vLLM 的 chat 端点会拒。
  # run_smolagents_gaia.py 里已经强制 flatten_messages_as_text=True。
  ok "vLLM 兼容性:已在 run_smolagents_gaia.py 里强制 flatten_messages_as_text"
else
  bad "smolagents 不可用"; hint "pip install 'smolagents[toolkit]'"
fi
fi

# ---------------------------------------------------------------------------
if want inspect; then
echo
echo "--- 2. Inspect AI + inspect_evals (参考基线) ---"
if [ $CHECK_ONLY -eq 0 ] && ! pyhas inspect_ai; then
  echo "  安装中: pip install inspect-ai inspect-evals"
  pip install -q inspect-ai 'inspect-evals' || bad "inspect 安装失败"
fi
if pyhas inspect_ai; then
  ok "inspect_ai 已装"
  command -v inspect >/dev/null 2>&1 && ok "inspect CLI 在 PATH 上" \
    || warn "inspect CLI 不在 PATH —— 用 python -m inspect_ai 代替"
else
  bad "inspect_ai 不可用"; hint "pip install inspect-ai inspect-evals"
fi
pyhas inspect_evals && ok "inspect_evals 已装" \
  || { bad "inspect_evals 不可用"; hint "pip install inspect-evals"; }

# GAIA 数据的处理见下面第 4 节 —— 它不受 --only 影响,所以填充本地副本
# 不需要先把 inspect 装上。

# Docker:官方 GAIA eval 默认把 bash 放容器里跑
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    ok "Docker 可用 —— 可以用官方默认沙箱"
    echo "          inspect eval inspect_evals/gaia --model openai-api/local/\$MODEL"
  else
    warn "有 docker 命令但 daemon 连不上(容器里通常就是这样)"
    hint "改用 --sandbox local(见下)"
  fi
else
  warn "没有 Docker"
  hint "改用 --sandbox local(见下)"
fi
cat <<'EOF'
          说明:inspect_evals/gaia 默认在 Docker 容器里执行 bash。租来的
          容器里一般起不了 Docker daemon。Inspect 本身支持 local 沙箱:

              inspect eval inspect_evals/gaia --sandbox local ...

          local 沙箱直接在 Inspect 进程里跑命令,官方文档说明它只应在
          "整个评测已经跑在另一层沙箱里" 时使用 —— 你租的容器正好就是那一层,
          所以这里是成立的,但要在论文里写明沙箱不同于官方配置。
EOF
fi

# ---------------------------------------------------------------------------
if want magentic; then
echo
echo "--- 3. Magentic-One (未接 runner,仅装依赖) ---"
if [ $CHECK_ONLY -eq 0 ] && ! pyhas autogen_agentchat; then
  echo "  安装中: pip install autogen-agentchat 'autogen-ext[openai,magentic-one]'"
  pip install -q autogen-agentchat 'autogen-ext[openai,magentic-one]' \
    || bad "autogen 安装失败"
fi
if pyhas autogen_agentchat; then
  ok "autogen-agentchat 已装"
  if [ $CHECK_ONLY -eq 0 ]; then
    echo "  安装 Playwright 浏览器(WebSurfer 需要)..."
    playwright install --with-deps chromium >/dev/null 2>&1 \
      && ok "Playwright chromium 已装" \
      || warn "playwright install 失败 —— WebSurfer 用不了(缺系统依赖时常见)"
  fi
else
  warn "autogen 不可用(没接 runner,不影响其他 cell)"
fi
echo "          注意:自定义模型必须显式给 model_info(function_calling /"
echo "          json_output / vision / family / structured_output),否则 autogen 直接拒绝。"
fi

# ---------------------------------------------------------------------------
echo
echo "--- 4. GAIA 数据(所有 cell 共用)---"
PARQUET=$BASE/GAIA/2023/validation/metadata.parquet
if [ "$(head -c 4 "$PARQUET" 2>/dev/null)" = "PAR1" ]; then
  ok "metadata.parquet 是真 parquet"
else
  bad "$PARQUET 不是有效 parquet(LFS 指针?)"; hint "git lfs pull"
fi

# GAIA 数据。inspect_evals 用
#   snapshot_download(repo_id="gaia-benchmark/GAIA", local_dir=GAIA_DATASET_DIR)
# 而 snapshot_download 在 local_dir 已经填好时会直接复用,不去下载。仓库里
# GAIA/ 就是这个数据集的完整副本,所以把它放到那个位置就不需要 HF_TOKEN —
# 授权在当初把数据 commit 进仓库时就已经付过一次了。
INSPECT_CACHE=${INSPECT_EVALS_CACHE_PATH:-$BASE/.inspect_cache}
GAIA_DEST=$INSPECT_CACHE/gaia_dataset/GAIA
if [ -f "$GAIA_DEST/2023/validation/metadata.parquet" ]; then
  ok "inspect 的 GAIA 副本已就位 ($GAIA_DEST)"
elif [ $CHECK_ONLY -eq 0 ] && [ -d "$BASE/GAIA/2023" ]; then
  echo "  从仓库副本填充 inspect 的 GAIA 缓存..."
  mkdir -p "$(dirname "$GAIA_DEST")"
  cp -r "$BASE/GAIA" "$GAIA_DEST" 2>/dev/null && ok "已填充 $GAIA_DEST" \
    || bad "复制失败 —— 手动: cp -r $BASE/GAIA $GAIA_DEST"
else
  warn "inspect 的 GAIA 副本不在 $GAIA_DEST"
  hint "跑一次不带 --check 的 setup-external.sh 让它自动填充"
fi
echo "          需要在 env.sh 里导出(experiments-agents.sh 也会用):"
echo "              export INSPECT_EVALS_CACHE_PATH=$INSPECT_CACHE"
echo "              export HF_HUB_OFFLINE=1     # 强制只用本地副本"

if [ -n "${HF_TOKEN:-}" ]; then
  ok "HF_TOKEN 已设(有本地副本时其实用不上)"
elif [ -f "$GAIA_DEST/2023/validation/metadata.parquet" ]; then
  ok "HF_TOKEN 未设,但有本地 GAIA 副本 —— 够用了"
else
  warn "HF_TOKEN 未设,本地副本也没就位 —— 二选一"
  hint "要么让本脚本填充本地副本(推荐,不用申请)"
  hint "要么去 https://huggingface.co/datasets/gaia-benchmark/GAIA 填表并 export HF_TOKEN"
fi


echo
echo "=============================================================="
echo " OK=$PASS  WARN=$WARN  FAIL=$FAILN"
if [ $FAILN -gt 0 ]; then
  echo " 有 $FAILN 项未通过 —— 修完再跑 ./experiments-agents.sh"
  echo "=============================================================="
  exit 1
fi
echo " 可以跑: ./experiments-agents.sh --dry-run"
echo "=============================================================="
