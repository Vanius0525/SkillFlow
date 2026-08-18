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
#   magentic-one 默认跳过 —— 需要 Playwright + 浏览器二进制,而且 runner 还没接。
#                想装再 --only magentic。
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

# 默认只处理这两个。magentic 不在默认集里:它要 Playwright 加一整套浏览器
# 二进制(在缺系统依赖的容器里经常装不上),而 runner 还没接,装了也跑不了。
# 真要装就显式 --only magentic。
DEFAULT_TARGETS="smolagents inspect"
want() {
  if [ -n "$ONLY" ]; then [ "$ONLY" = "$1" ]; return; fi
  case " $DEFAULT_TARGETS " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

PASS=0; WARN=0; FAILN=0
ok()   { echo "  [ OK ]  $*"; PASS=$((PASS+1)); }
warn() { echo "  [WARN]  $*"; WARN=$((WARN+1)); }
bad()  { echo "  [FAIL]  $*"; FAILN=$((FAILN+1)); }
hint() { echo "          -> $*"; }

pyhas() { python -c "import $1" >/dev/null 2>&1; }

# Always install with the SAME interpreter we then import with. Plain `pip` is
# whatever is first on PATH -- with a venv and conda base both active that is
# usually conda's, so the install lands in another environment, exits 0, and the
# import check fails with nothing on screen to explain why.
PIP=(python -m pip install --root-user-action=ignore)
pipinstall() {
  echo "  安装中: python -m pip install $*"
  "${PIP[@]}" "$@" 2>&1 | tail -3
  return "${PIPESTATUS[0]}"
}

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

# openai SDK 版本。inspect 的 openai-api provider 要 >= 3.1.0,而 llm_backend
# 用的是同一个包 —— 升级会同时影响每一个 SkillFlow cell,所以升完立刻拿真端点
# 验一次,而不是等跑到一半才发现整批白跑。
OPENAI_MIN=3.1.0
OPENAI_VER=$(python -c 'import openai;print(openai.__version__)' 2>/dev/null)
if [ -z "$OPENAI_VER" ]; then
  bad "openai 包缺失"; hint "python -m pip install 'openai>=$OPENAI_MIN'"
elif python -c "
import sys
from importlib.metadata import version
def t(v): return tuple(int(x) for x in v.split('.')[:3] if x.isdigit())
sys.exit(0 if t('$OPENAI_VER') >= t('$OPENAI_MIN') else 1)" 2>/dev/null; then
  ok "openai $OPENAI_VER (>= $OPENAI_MIN)"
elif [ $CHECK_ONLY -eq 0 ]; then
  warn "openai $OPENAI_VER < $OPENAI_MIN —— inspect 的 openai-api provider 会拒绝启动"
  pipinstall --upgrade "openai>=$OPENAI_MIN" && \
    ok "已升级到 $(python -c 'import openai;print(openai.__version__)' 2>/dev/null)" || \
    bad "openai 升级失败"
else
  bad "openai $OPENAI_VER < $OPENAI_MIN"; hint "python -m pip install --upgrade 'openai>=$OPENAI_MIN'"
fi

# 升级 openai 之后最要紧的一件事:确认我们自己的 qwen backend 还能用。
# 这条不是可选的礼节 —— llm_backend 是每个 SkillFlow cell 的唯一出口。
if curl -sf -m 5 "${QWEN_URL%/v1}/health" >/dev/null 2>&1; then
  if BASE_DIR="$BASE" QWEN_URL="$QWEN_URL" MODEL_ID="${SERVED:-${QWEN_MODEL:-Qwen/Qwen3-8B}}" \
     python - <<'PY' >/dev/null 2>&1
import os, sys
sys.path.insert(0, os.environ["BASE_DIR"])
from llm_backend import make_client
c = make_client("qwen", base_url=os.environ["QWEN_URL"], model=os.environ["MODEL_ID"])
r = c.messages.create(model="ignored", max_tokens=8,
                      messages=[{"role": "user", "content": "Reply with the word ok."}])
assert r.usage.input_tokens > 0, "no usage reported"
assert any(getattr(b, "text", None) for b in r.content), "no text returned"
PY
  then ok "llm_backend 在当前 openai 版本下仍可用(已打真端点验证)"
  else
    bad "llm_backend 打 vLLM 失败 —— openai 升级可能破坏了 qwen backend"
    hint "手动复现: python skillflow.py task --backend qwen --task 'what is 2+2'"
  fi
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
  pipinstall 'smolagents[toolkit]' || bad "smolagents 安装失败"
  # GAIA 附件含 .xlsx / .pdf。smolagents 在构造 agent 时会校验每一个 authorized
  # import 是否装上,缺一个就直接拒绝建 agent(不是运行时才报),所以这些要先装。
  # 两边 harness 的 Python 都用得上它们。
  pipinstall openpyxl pypdf chess sympy numpy \
    || warn "附件解析库没装全 —— agent 能跑,但 xlsx/pdf 题会答不好"
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
  bad "smolagents 不可用"; hint "python -m pip install 'smolagents[toolkit]'"
  hint "(若刚装完仍导不进来: pip 装到了别的解释器 —— 用 python -m pip)"
fi
fi

# ---------------------------------------------------------------------------
if want inspect; then
echo
echo "--- 2. Inspect AI + inspect_evals (参考基线) ---"
if [ $CHECK_ONLY -eq 0 ] && ! pyhas inspect_ai; then
  pipinstall inspect-ai 'inspect-evals' || bad "inspect 安装失败"
fi
if pyhas inspect_ai; then
  ok "inspect_ai 已装"
  command -v inspect >/dev/null 2>&1 && ok "inspect CLI 在 PATH 上" \
    || warn "inspect CLI 不在 PATH —— 用 python -m inspect_ai 代替"
else
  bad "inspect_ai 不可用"; hint "python -m pip install inspect-ai inspect-evals"
  hint "(若刚装完仍导不进来: pip 装到了别的解释器 —— 用 python -m pip)"
fi
pyhas inspect_evals && ok "inspect_evals 已装" \
  || { bad "inspect_evals 不可用"; hint "python -m pip install inspect-evals"
  hint "(若刚装完仍导不进来: pip 装到了别的解释器 —— 用 python -m pip)"; }

# GAIA 数据的处理见下面第 4 节 —— 它不受 --only 影响,所以填充本地副本
# 不需要先把 inspect 装上。

# openai-api provider 的凭据命名:openai-api/<provider>/<model> 读的是
# <PROVIDER>_API_KEY / <PROVIDER>_BASE_URL,不是 OPENAI_*。
# experiments-agents.sh 会自己从 $INSPECT_MODEL 推导并设好,这里只是说明,
# 手工跑 inspect eval 时需要自己 export。
INSPECT_MODEL_HINT=${INSPECT_MODEL:-openai-api/local/${QWEN_MODEL:-Qwen/Qwen3-8B}}
PROV_HINT=$(printf '%s' "$INSPECT_MODEL_HINT" | awk -F/ '{print $2}' | tr 'a-z-' 'A-Z_')
ok "inspect 凭据变量: ${PROV_HINT}_API_KEY / ${PROV_HINT}_BASE_URL(脚本会自动设)"
echo "          手工跑时: export ${PROV_HINT}_API_KEY=EMPTY ${PROV_HINT}_BASE_URL=$QWEN_URL"

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
echo "--- 3. Magentic-One (默认跳过;--only magentic 才装) ---"
if [ $CHECK_ONLY -eq 0 ] && ! pyhas autogen_agentchat; then
  pipinstall autogen-agentchat 'autogen-ext[openai,magentic-one]' \
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
# 这个副本有 ~80MB,和 tracked 的 GAIA/ 一模一样。默认位置 $BASE/.inspect_cache
# 在 .gitignore 里;若外部把 INSPECT_EVALS_CACHE_PATH 指到了仓库内的别处,提前
# 说出来,别等它被 git add 进去。
case "$INSPECT_CACHE" in
  "$BASE/.inspect_cache"*) : ;;
  "$BASE"/*) warn "缓存在仓库内的非默认位置: $INSPECT_CACHE"
             hint "建议 export INSPECT_EVALS_CACHE_PATH=$BASE/.inspect_cache" ;;
esac
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
