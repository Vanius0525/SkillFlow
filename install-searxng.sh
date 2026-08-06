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
  request_timeout: 10.0
  pool_connections: 100
  pool_maxsize: 20
EOF
fi

echo
echo "==> 完成。接下来:"
echo "   1. 把这一行加进 env.sh:"
echo "        export SEARXNG_HOME=$SEARXNG_HOME"
echo "   2. 启动:  $BASE/run-searxng.sh start"
echo "   3. 验证:  $BASE/run-searxng.sh status"
