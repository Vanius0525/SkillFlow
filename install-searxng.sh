#!/usr/bin/env bash
# SearXNG 一次性安装脚本: ./install-searxng.sh
#
# 装在仓库外面（默认 $BASE 的同级目录），避免 git status 刷屏，也避免
# git clean -fd 把它删掉。装完用 ./run-searxng.sh start 启动。
#
# 布局与 scibench_skills/web-search/scripts/search.py 读的环境变量一致:
#   $SEARXNG_HOME/searxng                     源码（靠 PYTHONPATH 运行，不装进 venv）
#   $SEARXNG_HOME/searxng-venv                依赖
#   $SEARXNG_HOME/.config/searxng/settings.yml
set -euo pipefail

BASE=/inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness
SEARXNG_HOME=${SEARXNG_HOME:-$(dirname "$BASE")/searxng}

SRC=$SEARXNG_HOME/searxng
VENV=$SEARXNG_HOME/searxng-venv
SETTINGS=$SEARXNG_HOME/.config/searxng/settings.yml
PORT=${SEARXNG_PORT:-8888}

echo "==> 安装位置: $SEARXNG_HOME"
mkdir -p "$SEARXNG_HOME/.config/searxng"

# ---- 源码 ----
if [ -d "$SRC/.git" ]; then
  echo "==> 源码已存在，跳过 clone"
else
  echo "==> clone SearXNG"
  git clone --depth 1 https://github.com/searxng/searxng.git "$SRC"
fi

# ---- 依赖 ----
# search.py 用 PYTHONPATH=$SRC 跑 `python -m searx.webapp`，所以 venv 里
# 只需要依赖，不需要装 searxng 本身。
if [ -x "$VENV/bin/python" ]; then
  echo "==> venv 已存在，跳过创建"
else
  echo "==> 创建 venv"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 "$VENV"
  else
    python3 -m venv "$VENV"
  fi
fi

echo "==> 安装依赖"
if command -v uv >/dev/null 2>&1; then
  uv pip install --python "$VENV/bin/python" -r "$SRC/requirements.txt"
else
  "$VENV/bin/pip" install -U pip
  "$VENV/bin/pip" install -r "$SRC/requirements.txt"
fi

# ---- 配置 ----
if [ -f "$SETTINGS" ]; then
  echo "==> 配置已存在，保留不动: $SETTINGS"
else
  echo "==> 写配置"
  if command -v openssl >/dev/null 2>&1; then
    SECRET=$(openssl rand -hex 32)
  else
    SECRET=$("$VENV/bin/python" -c 'import secrets; print(secrets.token_hex(32))')
  fi
  # formats 必须含 json — 默认只开 html，search.py 请求 format=json 会吃 403。
  # limiter 必须关 — 否则并发 worker 会被反爬限流挡掉。
  cat > "$SETTINGS" <<EOF
use_default_settings: true

server:
  secret_key: "$SECRET"
  bind_address: "127.0.0.1"
  port: $PORT
  limiter: false
  public_instance: false
  image_proxy: false

search:
  safe_search: 0
  formats:
    - html
    - json

outgoing:
  request_timeout: 8.0
  max_request_timeout: 15.0
  pool_connections: 100
  pool_maxsize: 20

# 引擎按 Inspire 容器的实际出网情况显式指定 —— 不依赖各版本的默认启用状态。
# 实测 2026-08-07: duckduckgo / brave / startpage / qwant / yahoo 的域名全部
# 连不上（ConnectTimeout），wikidata 的 SPARQL 端点返 403。留着它们的唯一效果
# 是每次搜索白等一轮超时，日志也会被刷满。
# 重新测: for h in <域名>; do curl -sS -m 8 -o /dev/null -w '%{http_code}\n' https://\$h/; done
engines:
  - name: duckduckgo
    disabled: true
  - name: duckduckgo images
    disabled: true
  - name: duckduckgo news
    disabled: true
  - name: duckduckgo videos
    disabled: true
  - name: duckduckgo weather
    disabled: true
  - name: duckduckgo web
    disabled: true
  - name: ddg definitions
    disabled: true
  - name: brave
    disabled: true
  - name: brave.images
    disabled: true
  - name: brave.news
    disabled: true
  - name: brave.videos
    disabled: true
  - name: startpage
    disabled: true
  - name: startpage images
    disabled: true
  - name: startpage news
    disabled: true
  - name: qwant
    disabled: true
  - name: qwant images
    disabled: true
  - name: qwant news
    disabled: true
  - name: qwant videos
    disabled: true
  - name: yahoo
    disabled: true
  - name: wikidata
    disabled: true

  # 可达的，显式打开
  - name: bing
    disabled: false
  - name: bing news
    disabled: false
  - name: mojeek
    disabled: false
  - name: mojeek news
    disabled: false
  - name: wikipedia
    disabled: false
  - name: yandex
    disabled: false
  - name: google news
    disabled: false
  # academic 分类 —— arxiv / pubmed / scholar / semantic scholar / crossref 实测均可达
  - name: arxiv
    disabled: false
  - name: pubmed
    disabled: false
  - name: google scholar
    disabled: false
  - name: semantic scholar
    disabled: false
  - name: crossref
    disabled: false
  # social 分类 —— 这个实例不带 reddit 引擎，reddit.com 也不通。
  # boardreader 是论坛聚合，最接近原用途；lobste.rs 只有技术话题。
  # lemmy 未启用: 默认指向已死的 lemmy.ml，改用 lemmy.world 要覆盖 base_url。
  - name: boardreader
    disabled: false
  - name: lobste.rs
    disabled: false
EOF
fi

echo
echo "==> 完成。接下来:"
echo "   1. 把这一行加进 env.sh:"
echo "        export SEARXNG_HOME=$SEARXNG_HOME"
echo "   2. 启动:  $BASE/run-searxng.sh start"
echo "   3. 验证:  $BASE/run-searxng.sh status"
