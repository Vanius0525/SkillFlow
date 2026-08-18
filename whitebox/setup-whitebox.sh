#!/usr/bin/env bash
# 白盒实验的服务器端体检 + 可选安装。
#
#   ./setup-whitebox.sh                # 只检查,不动环境(默认)
#   ./setup-whitebox.sh --install      # 装缺的依赖
#   ./setup-whitebox.sh --download     # 拉开发用的小模型
#   ./setup-whitebox.sh --install --download
#
# 默认只检查是有意的。这个仓库的 venv 同时供着 vLLM,而 vLLM 对 torch 版本很挑;
# 一次顺手的 `pip install -U` 就可能把黑盒那批实验弄坏。所以除非你显式说要装,
# 这个脚本一个包都不碰。
#
# 显存:一张 24GB 卡装不下 vLLM 的 8B 加上 HF 的 8B。跑白盒前先 ./run-server.sh stop。
# 开发用 1.7B 的话可以和 vLLM 共存(1.7B bf16 约 3.4GB),但仍然建议错开。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$BASE/.." && pwd)"

DO_INSTALL=0; DO_DOWNLOAD=0
for a in "$@"; do
  case "$a" in
    --install)  DO_INSTALL=1 ;;
    --download) DO_DOWNLOAD=1 ;;
    *) echo "用法: $0 [--install] [--download]" >&2; exit 1 ;;
  esac
done

PASS=0; WARN=0; FAILN=0
ok()   { echo "  [ OK ]  $*"; PASS=$((PASS+1)); }
warn() { echo "  [WARN]  $*"; WARN=$((WARN+1)); }
bad()  { echo "  [FAIL]  $*"; FAILN=$((FAILN+1)); }
hint() { echo "          -> $*"; }

echo "=============================================================="
echo " 白盒实验环境体检"
echo " repo   : $REPO"
echo " python : $(command -v python || echo '(缺)')"
echo " 模式   : $([ $DO_INSTALL -eq 1 ] && echo '会安装' || echo '只检查')"
echo "=============================================================="

# --- 1. GPU ----------------------------------------------------------------
echo
echo "--- 1. GPU ---"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,memory.used \
             --format=csv,noheader | sed 's/^/          /'
  ok "nvidia-smi 可用"
  USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  if [ "${USED:-0}" -gt 4000 ] 2>/dev/null; then
    warn "显存已占用 ${USED}MiB —— 多半是 vLLM 在跑"
    hint "跑 8B 白盒之前: $REPO/run-server.sh stop"
  fi
else
  bad "没有 nvidia-smi"; hint "白盒必须有 GPU,CPU 上跑不动"
fi

# --- 2. Python 依赖 --------------------------------------------------------
echo
echo "--- 2. Python 依赖 ---"
need_install=0
for pkg in torch transformers accelerate; do
  if python -c "import $pkg" >/dev/null 2>&1; then
    v=$(python -c "import $pkg;print(getattr($pkg,'__version__','?'))" 2>/dev/null)
    ok "$pkg $v"
  else
    warn "$pkg 缺失"; need_install=1
  fi
done

if [ $need_install -eq 1 ]; then
  if [ $DO_INSTALL -eq 1 ]; then
    echo "  安装缺失的包(不升级已有的 —— 保护 vLLM 的 torch 版本)..."
    python -m pip install --root-user-action=ignore \
      transformers accelerate 2>&1 | tail -3
    # torch 故意不在这里装:vLLM 已经带了一个,版本必须由 vLLM 决定
    python -c "import torch" >/dev/null 2>&1 \
      || { bad "torch 缺失且本脚本不代装"; hint "它归 vLLM 管,按 vLLM 的版本要求装"; }
  else
    hint "装上: $0 --install"
    hint "(torch 不会被本脚本安装或升级 —— 它的版本归 vLLM 管)"
  fi
fi

python -c "import torch;assert torch.cuda.is_available()" 2>/dev/null \
  && ok "torch 能看到 CUDA" \
  || bad "torch 看不到 CUDA"

# --- 3. 模型 ---------------------------------------------------------------
echo
echo "--- 3. 模型 ---"
LOCAL8B=$REPO/models/Qwen3-8B
if [ -f "$LOCAL8B/config.json" ]; then
  ok "本地 8B: $LOCAL8B"
  python - <<PY 2>/dev/null | sed 's/^/          /'
import json
c=json.load(open(r"$LOCAL8B/config.json"))
print({k:c.get(k) for k in ("num_hidden_layers","hidden_size",
      "num_attention_heads","num_key_value_heads")})
PY
else
  warn "$LOCAL8B 里没有 config.json"
fi

DEV_MODEL=${WB_DEV_MODEL:-Qwen/Qwen3-1.7B}
if [ $DO_DOWNLOAD -eq 1 ]; then
  echo "  下载开发用小模型 $DEV_MODEL ..."
  echo "  (HF_ENDPOINT=${HF_ENDPOINT:-<未设>})"
  python -m pip show huggingface_hub >/dev/null 2>&1 || \
    python -m pip install --root-user-action=ignore huggingface_hub 2>&1 | tail -1
  huggingface-cli download "$DEV_MODEL" --local-dir "$REPO/models/$(basename "$DEV_MODEL")" \
    && ok "已下载到 models/$(basename "$DEV_MODEL")" \
    || bad "下载失败 —— Qwen3 不是 gated,失败多半是网络/HF_ENDPOINT"
else
  hint "开发用小模型: $0 --download   (默认 $DEV_MODEL,改用 WB_DEV_MODEL=...)"
fi

# --- 4. 任务集 -------------------------------------------------------------
echo
echo "--- 4. 任务集(应当和生成器一致)---"
( cd "$BASE/tasks/tier_a" && python build.py --check ) 2>&1 | sed 's/^/  /' \
  || bad "Tier A 任务集和生成器对不上"
( cd "$BASE/tasks/tier_b" && python build.py --check ) 2>&1 | sed 's/^/  /' \
  || bad "Tier B 任务集和生成器对不上(SciBench 数据在不在?git lfs pull)"

# --- 5. 污染检查 -----------------------------------------------------------
echo
echo "--- 5. 污染检查 ---"
python "$BASE/contamination.py" 2>&1 | tail -12 | sed 's/^/  /'

# --- 汇总 ------------------------------------------------------------------
echo
echo "=============================================================="
echo " 通过 $PASS,警告 $WARN,失败 $FAILN"
if [ $FAILN -eq 0 ]; then
cat <<EOF

 下一步,按顺序:

   1. 自检(先在小模型上,秒级):
        python selftest.py --model $REPO/models/$(basename "$DEV_MODEL")
      七项全过才往下走。任何一项失败都意味着干预代码是坏的 ——
      坏的干预照样出数字,只是没有意义。

   2. Tier A 正对照(skill 必然有用,效应必然大):
        python e0_effect.py --model $REPO/models/$(basename "$DEV_MODEL") \\
          --tasks tasks/tier_a/tasks.jsonl \\
          --skill tasks/tier_a/SKILL.zorb-units.md \\
          --mode mc --run-id tierA-dev
      这里没有大效应 = 流水线坏了,不是假设错了。

   3. Tier B 效应筛查(真实问题所在):
        python e0_effect.py --model $REPO/models/Qwen3-8B \\
          --tasks tasks/tier_b/tasks.jsonl \\
          --skill tasks/tier_b/SKILL.pchem-constants.md \\
          --mode num --limit 120 --run-id tierB-const-8b \\
          --filter-known tasks/tier_b/tasks.filtered.jsonl

 细节见 README.md,研究设计见 ../HANDOFF-whitebox.md
EOF
else
  echo
  echo " 有 FAIL,先修完再往下。"
fi
echo "=============================================================="
