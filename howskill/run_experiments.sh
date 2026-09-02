#!/usr/bin/env bash
# 按顺序跑完 P3 + P8 白盒的全部步骤。在服务器上：
#
#   cd $BASE/howskill
#   nohup bash run_experiments.sh > $BASE/logs/exp.log 2>&1 &
#   echo $! > $BASE/logs/exp.pid
#   tail -f $BASE/logs/exp.log
#
# 一律写成 `bash run_experiments.sh`。可执行位在这个仓库里靠 git 传递，
# 而它是从 Windows 提交的 —— chmod 在那边不生效，曾经就漏过一次。
# `bash <脚本>` 不依赖可执行位，也不依赖 shebang。
#
# 从某一步继续（前面的结果已经在了就不重跑）：
#   FROM=4 bash run_experiments.sh
# 只看会跑什么、不真跑：
#   DRY=1 bash run_experiments.sh
#
# 门槛是硬的：GATE-W0 不过就停在那一步，不往下推。理由见
# ../HOWSKILLWORK/P8-WHITEBOX.md §3.5 —— token 错位不会报错，只会给出
# 看起来很正常但完全错误的内部量。
set -u -o pipefail

BASE=${BASE:-/inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness}
HOWSKILL=${HOWSKILL:-$BASE/howskill}
MODEL_DIR=${WB_MODEL:-$BASE/models/Qwen3-8B}
SERVED=${QWEN_SERVED_NAME:-Qwen/Qwen3-8B}
FROM=${FROM:-1}
DRY=${DRY:-0}
WORKERS=${WORKERS:-8}

cd "$HOWSKILL" || exit 1
mkdir -p results logs

say() { echo; echo "=== [$(date +%H:%M:%S)] $*"; }
run() {
  echo "\$ $*"
  [ "$DRY" = "1" ] && return 0
  "$@"
}
# 只在这一步的产物还不存在时才跑
skip_if() { [ -e "$1" ] && { echo "  (已存在，跳过: $1)"; return 0; } || return 1; }

step() { [ "$FROM" -le "$1" ]; }

say "自检（每次都跑，代码变了这里最先炸）"
run python -m howskill.selftest || exit 1

# ---------------------------------------------------------------- 1. 服务
if step 1; then
  say "1. 确认 vLLM 在跑，且服务的是 8B"
  if [ "$DRY" != "1" ]; then
    curl -sf http://127.0.0.1:8000/health >/dev/null || {
      echo "vLLM 没起。先跑: pkill -f 'vllm serve'; sleep 5; \$BASE/run-server.sh start"
      exit 1; }
    got=$(curl -s http://127.0.0.1:8000/v1/models \
          | python -c "import json,sys;print(json.load(sys.stdin)['data'][0]['id'])")
    echo "  served: $got"
    [ "$got" = "$SERVED" ] || { echo "服务的模型不是 $SERVED，停"; exit 1; }
  fi
fi

# ---------------------------------------------------------------- 2. P3
if step 2; then
  say "2. P3 深挖子集（从 P2 实测基线里选，PROTOCOL §1.3）"
  skip_if data/deep_subset.json || \
    run python -m howskill.subset results/p2 --baseline p2-no_skill || exit 1

  say "3. P3 内容消融 12 臂 x 400"
  for arm in drop_M1 drop_M2 drop_M3 drop_M4 drop_M5 m5_clinical \
             ctrl_shuffled ctrl_corrupted no_tool no_tool_no_M4 gold no_skill; do
    skip_if "results/p3/p3-$arm.jsonl" && continue
    run python -m howskill.run --arm "$arm" --temperature 0 \
        --calculators data/deep_subset.json --workers "$WORKERS" \
        --out results/p3 --tag "p3-$arm" || exit 1
  done
  run python -m howskill.analyze results/p3 \
      --baseline p3-no_skill --control p3-ctrl_shuffled --steps
fi

# ---------------------------------------------------------------- 3. 单步臂
if step 4; then
  say "4. P8 单步行为跑：单轮、无工具、记 logprobs（GATE-W0 要用）"
  # --logprobs 1 是必须的：P1/P2 没记 logprob，没有它 GATE-W0 无从比对。
  # --no-tool-protocol + *_no_tool 臂 = 一次前向就出答案，因果链干净。
  for arm in no_skill gold_no_tool ctrl_neutral_no_tool; do
    skip_if "results/p8-step/p8-$arm.jsonl" && continue
    run python -m howskill.run --arm "$arm" --temperature 0 \
        --no-tool-protocol --logprobs 1 --workers "$WORKERS" \
        --out results/p8-step --tag "p8-$arm" || exit 1
  done
  run python -m howskill.analyze results/p8-step \
      --baseline p8-no_skill --control p8-ctrl_neutral_no_tool
fi

# ---------------------------------------------------------------- 4. 四格
if step 5; then
  say "5. 建 R/F/K/B 四格（行为定义），并给出 calculator 内配对的版本"
  run python -m howskill.cells results/p8-step \
      --without p8-no_skill --with p8-gold_no_tool \
      --out data/cells.json || exit 1
  run python -m howskill.cells results/p8-step \
      --without p8-no_skill --with p8-gold_no_tool --paired \
      --out data/cells_paired.json || exit 1
fi

# ---------------------------------------------------------------- 5. 白盒
# 从这里开始要停 vLLM —— 一张 4090 放不下 vLLM 和 HF 两份 8B。
if step 6; then
  say "6. 停 vLLM，腾显存给 HF 重放"
  run bash -c "pkill -f 'vllm serve' || true; sleep 5"
  run bash -c "nvidia-smi --query-compute-apps=pid,used_memory --format=csv"
fi

if step 7; then
  say "7. M1/M2/M3 + GATE-W0（gold）"
  run python -m howskill.wb_replay --results results/p8-step \
      --cells data/cells.json --model "$MODEL_DIR" \
      --without p8-no_skill --with p8-gold_no_tool --arm gold_no_tool \
      --cells-keep R,F --n-per-cell 150 \
      --out results/p8-wb/profiles-gold.jsonl
  rc=$?
  run python -m howskill.wb_analyze results/p8-wb/profiles-gold.jsonl
  if [ "$rc" != "0" ] && [ "$DRY" != "1" ]; then
    echo
    echo "GATE-W0 未通过 —— 停在这里。查 chat template / --thinking /"
    echo "第 4 步是否带了 --logprobs。不要往下跑，后面每个数都是错位的产物。"
    exit 1
  fi
fi

if step 8; then
  say "8. GATE-W2：同样的测量在 ctrl_neutral 上再跑一遍"
  run python -m howskill.wb_replay --results results/p8-step \
      --cells data/cells.json --model "$MODEL_DIR" \
      --without p8-no_skill --with p8-ctrl_neutral_no_tool \
      --arm ctrl_neutral_no_tool --cells-keep R,F --n-per-cell 150 \
      --out results/p8-wb/profiles-neutral.jsonl || exit 1
  run python -m howskill.wb_analyze results/p8-wb/profiles-neutral.jsonl
fi

if step 9; then
  say "9. M4 因果：敲除 + 残差流嫁接（最贵，先小规模）"
  run python -m howskill.wb_patch --results results/p8-step \
      --cells data/cells.json --model "$MODEL_DIR" \
      --arm gold_no_tool --cells-keep R,F --n-per-cell 40 --layer-stride 4 \
      --out results/p8-wb/patch-gold.jsonl || exit 1
  run python -m howskill.wb_analyze results/p8-wb/patch-gold.jsonl --kind patch
fi

say "全部结束。产物："
run bash -c "ls -la results/p3 results/p8-step results/p8-wb 2>/dev/null | head -40"
