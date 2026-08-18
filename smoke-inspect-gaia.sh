#!/usr/bin/env bash
# 冒烟测试:inspect_evals 的 GAIA 这条链路,从数据一路验到真跑一题。
#
#   source env.sh
#   ./smoke-inspect-gaia.sh              # 全部
#   ./smoke-inspect-gaia.sh --no-eval    # 只跑离线部分,不需要 vLLM
#
# 分层的理由:这条链上每一层坏掉,报出来的都是同一个 GatedRepoError/403。
# 单看那个报错分不出是 LFS 没拉、暂存路径不对、还是补丁没挂上。所以这里每层
# 单独判定,前一层不过就停,让报错指向真正的那一层。
#
#   1  仓库数据      GAIA/ 是真 parquet 还是 LFS 指针
#   2  暂存位置      .inspect_cache 下的 GAIA 能不能读到
#   3  包            inspect_ai / inspect_evals 装了没
#   4  路径一致      inspect_evals 算出来的 GAIA_DATASET_DIR 是否就是第 2 层那个
#   5  零联网        强制 HF_HUB_OFFLINE=1 建 task —— 过了就等于证明不碰网络
#   6  样本可用      题目数量、附件文件真的落在磁盘上
#   7  vLLM          端点活着,而且 model id 对得上
#   8  端到端        真跑一题(顺带覆盖凭据映射、sandbox、agent、scorer)
#
# 第 5 层是整套里最有分量的一条。平时不该设 HF_HUB_OFFLINE(见
# run_inspect_gaia.py 顶部),但在这里反过来当断言用:补丁真挂上了就不会有任何
# 网络请求,那么强制离线也必须能通过。通过 = 证明了零联网,而不只是"这次没报错"。
set -uo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE"

RUN_EVAL=1
[ "${1:-}" = "--no-eval" ] && RUN_EVAL=0

PASS=0; FAILN=0
ok()   { echo "  [ OK ]  $*"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL]  $*"; FAILN=$((FAILN+1)); }
hint() { echo "          -> $*"; }
die()  { echo; echo "在第 $1 层停下 —— 后面的层依赖它,继续跑只会看到派生的报错。"; exit 1; }

echo "=============================================================="
echo " inspect GAIA 冒烟测试"
echo " repo   : $BASE"
echo " python : $(command -v python || echo '(缺)')"
echo "=============================================================="

# --- 1. 仓库数据 -----------------------------------------------------------
echo
echo "--- 1. 仓库里的 GAIA ---"
SRC=$BASE/GAIA/2023/validation/metadata.parquet
if [ "$(head -c 4 "$SRC" 2>/dev/null)" = "PAR1" ]; then
  ok "GAIA/2023/validation/metadata.parquet 是真 parquet"
else
  bad "$SRC 不是 parquet(多半是 LFS 指针)"
  hint "git lfs pull"
  die 1
fi

# --- 2. 暂存位置 -----------------------------------------------------------
echo
echo "--- 2. inspect 的暂存位置 ---"
CACHE=${INSPECT_EVALS_CACHE_DIR:-$BASE/.inspect_cache}
DEST=$CACHE/gaia_dataset/GAIA
[ -n "${INSPECT_EVALS_CACHE_DIR:-}" ] \
  && ok "INSPECT_EVALS_CACHE_DIR=$CACHE(env 里显式设了)" \
  || ok "INSPECT_EVALS_CACHE_DIR 未设,用默认 $CACHE"
if [ -f "$DEST/2023/validation/metadata.parquet" ]; then
  [ -L "$DEST" ] && ok "GAIA 已就位(软链 -> $(readlink "$DEST"))" \
                 || ok "GAIA 已就位(实体副本)"
elif [ -e "$DEST" ]; then
  # 被 403 打断的 snapshot_download 会留下一个半截目录。它有两重坑:挡住 ln -s,
  # 而且 `ln -s 源 已存在的目录` 会把软链建到那个目录*里面*(GAIA/GAIA),命令
  # 退出 0,看着像成功,实际没接上。所以这里单独报,不和"压根没填"混为一谈。
  bad "$DEST 存在但不完整 —— 多半是中断的下载留下的"
  hint "先看清楚要删什么: find '$DEST' -type f | head; du -sh '$DEST'"
  hint "确认无用后:       rm -rf '$DEST' && ln -s '$BASE/GAIA' '$DEST'"
  die 2
else
  bad "$DEST 不存在"
  hint "./setup-external.sh --only gaia"
  hint "或直接: mkdir -p '$(dirname "$DEST")' && ln -s '$BASE/GAIA' '$DEST'"
  die 2
fi
# 软链指向别处、或副本本身是 LFS 指针,都会在这里现形
if [ "$(head -c 4 "$DEST/2023/validation/metadata.parquet" 2>/dev/null)" = "PAR1" ]; then
  ok "通过暂存路径读到的也是真 parquet"
else
  bad "$DEST 下的 parquet 无效(软链断了?LFS 指针?)"; die 2
fi

# --- 3. 包 -----------------------------------------------------------------
echo
echo "--- 3. inspect 包 ---"
python - <<'PY' || die 3
import sys
try:
    import inspect_ai, inspect_evals
except ImportError as e:
    print(f"  [FAIL]  {e}")
    print("          -> python -m pip install inspect-ai inspect-evals")
    sys.exit(1)
print(f"  [ OK ]  inspect_ai {getattr(inspect_ai, '__version__', '?')}")
print(f"  [ OK ]  inspect_evals 可导入")
PY
PASS=$((PASS+2))

# --- 4. 路径一致 -----------------------------------------------------------
# 这一层专门盯之前那个 bug:脚本导的是 INSPECT_EVALS_CACHE_PATH,而
# inspect_evals 读的是 INSPECT_EVALS_CACHE_DIR,于是数据摆在一个地方、加载器
# 去另一个地方找,两边各自都"看起来没问题"。
echo
echo "--- 4. inspect_evals 算出来的路径 ---"
EXPECTED="$DEST" python - <<'PY' || die 4
import os, pathlib, sys
sys.path.insert(0, os.getcwd())
import run_inspect_gaia as launcher
launcher.ensure_cache_dir()
gaia_ds = launcher.load_gaia_dataset_module()
if gaia_ds is None:
    sys.exit(1)
actual = pathlib.Path(gaia_ds.GAIA_DATASET_DIR).resolve()
expected = pathlib.Path(os.environ["EXPECTED"]).resolve()
if actual == expected:
    print(f"  [ OK ]  GAIA_DATASET_DIR 与暂存位置一致")
    print(f"          {actual}")
else:
    print(f"  [FAIL]  路径对不上 —— 数据在一处,加载器找另一处")
    print(f"          加载器: {actual}")
    print(f"          暂存  : {expected}")
    print(f"          -> export INSPECT_EVALS_CACHE_DIR={expected.parent.parent}")
    sys.exit(1)
PY
PASS=$((PASS+1))

# --- 5 + 6. 零联网 & 样本可用 ----------------------------------------------
echo
echo "--- 5/6. 强制离线建 task ---"
python - <<'PY' || die 5
import os, sys, pathlib

# 断言用途,不是推荐配置:补丁挂上了就不会有网络请求,所以强制离线也必须能过。
# 一旦有任何一步偷偷回去连 HF,这里会直接 OfflineModeIsEnabled。
os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, os.getcwd())

import run_inspect_gaia as launcher
launcher.ensure_cache_dir()
gaia_ds = launcher.load_gaia_dataset_module()
path = pathlib.Path(gaia_ds.GAIA_DATASET_DIR)

if not launcher.is_populated(path):
    print(f"  [FAIL]  {path} 判定为空"); sys.exit(1)
if not launcher.patch_snapshot_download(gaia_ds, path):
    print("  [FAIL]  补丁没挂上"); sys.exit(1)

# 真正的证据:调的是注册表里那个 task,和 eval 走的完全是同一条路
try:
    from inspect_evals.gaia import gaia_level1
    task = gaia_level1()
except Exception as e:
    print(f"  [FAIL]  强制离线下建 task 失败: {type(e).__name__}: {e}")
    print("          -> 说明这条链上还有地方要联网,补丁没覆盖到")
    sys.exit(1)

n = len(task.dataset)
print(f"  [ OK ]  HF_HUB_OFFLINE=1 下建 task 成功 —— 零联网已证明")
print(f"  [ OK ]  gaia_level1 载入 {n} 题")
if n == 0:
    print("  [FAIL]  题目数为 0"); sys.exit(1)

# 附件:record_to_sample 把 files 映射成绝对路径,断链在这里暴露
sample = task.dataset[0]
print(f"  [ OK ]  首题 id={sample.id}")
missing = [src for src in (sample.files or {}).values() if not os.path.isfile(src)]
if missing:
    print(f"  [FAIL]  首题附件指向不存在的文件: {missing}"); sys.exit(1)

with_files = sum(1 for s in task.dataset if s.files)
print(f"  [ OK ]  {with_files}/{n} 题带附件,首题附件路径有效")
PY
PASS=$((PASS+5))

if [ $RUN_EVAL -eq 0 ]; then
  echo
  echo "=============================================================="
  echo " 离线部分全过 ($PASS 项)。--no-eval,不跑真题。"
  echo "=============================================================="
  exit 0
fi

# --- 7. vLLM ---------------------------------------------------------------
echo
echo "--- 7. vLLM ---"
QWEN_URL=${QWEN_BASE_URL:-http://localhost:8000/v1}
if curl -sf -m 5 "${QWEN_URL%/v1}/health" >/dev/null 2>&1; then
  ok "vLLM 在跑 ($QWEN_URL)"
else
  bad "vLLM 没响应 ($QWEN_URL)"; hint "./run-server.sh start"; die 7
fi
SERVED=$(curl -sf -m 5 "$QWEN_URL/models" 2>/dev/null \
         | python -c 'import sys,json;print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null)
WANT=${QWEN_MODEL:-Qwen/Qwen3-8B}
if [ "$SERVED" = "$WANT" ]; then
  ok "model id 对得上: $SERVED"
else
  bad "model id 不一致 —— 服务端 '$SERVED',要传给 inspect 的是 '$WANT'"
  hint "两边必须一字不差,否则 provider 会 404"
  die 7
fi

# --- 8. 端到端 -------------------------------------------------------------
# 这一层顺带覆盖了前面单独测不到的东西:凭据映射(provider 名取模型串第二段)、
# sandbox、react agent、scorer。跑 1 题就够,不是为了看分数。
echo
echo "--- 8. 真跑一题 ---"
PROV=$(printf '%s' "openai-api/local/$WANT" | awk -F/ '{print $2}' | tr 'a-z-' 'A-Z_')
echo "  provider=$PROV  model=openai-api/local/$WANT"
LOGDIR=$BASE/logs/smoke
mkdir -p "$LOGDIR"
if env "${PROV}_API_KEY=${OPENAI_API_KEY:-EMPTY}" \
       "${PROV}_BASE_URL=$QWEN_URL" \
       python "$BASE/run_inspect_gaia.py" eval inspect_evals/gaia_level1 \
         --model "openai-api/local/$WANT" \
         --sandbox local \
         --limit 1 \
         --time-limit 300 \
         --log-dir "$LOGDIR" \
         --display plain; then
  ok "端到端跑通"
  hint "看日志: inspect view --log-dir $LOGDIR"
else
  bad "端到端失败 —— 前 7 层都过了,所以问题在模型/sandbox/agent/scorer 这一段"
  hint "看日志: inspect view --log-dir $LOGDIR"
  die 8
fi

echo
echo "=============================================================="
echo " 全过:$PASS 项,失败 $FAILN 项"
echo "=============================================================="
