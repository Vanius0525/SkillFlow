#!/usr/bin/env bash
# SearXNG 服务管理: ./run-searxng.sh [start|stop|status|log]
# 部署位置: Inspire Studio 容器 $BASE/run-searxng.sh
#
# 日志和 pidfile 的默认值与 scibench_skills/web-search/scripts/search.py 完全
# 一致，两边读同一组环境变量，所以手动启动和 search.py 的按需拉起不会打架。
# 想改位置就在 env.sh 里 export，两边同时生效。
BASE=/inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness
SEARXNG_HOME=${SEARXNG_HOME:-$(dirname "$BASE")/searxng}

SRC=${SEARXNG_SRC:-$SEARXNG_HOME/searxng}
PY=${SEARXNG_PYTHON:-$SEARXNG_HOME/searxng-venv/bin/python}
SETTINGS=${SEARXNG_SETTINGS:-$SEARXNG_HOME/.config/searxng/settings.yml}
PORT=${SEARXNG_PORT:-8888}
LOG=${SEARXNG_LOG:-/tmp/searxng.log}
PIDFILE=${SEARXNG_PIDFILE:-/tmp/searxng.pid}

is_running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

case "${1:-start}" in
  start)
    if is_running; then
      echo "已在运行 (PID $(cat "$PIDFILE"))"; exit 0
    fi
    if [ ! -x "$PY" ] || [ ! -d "$SRC" ]; then
      echo "未安装: 找不到 $PY 或 $SRC"
      echo "先跑 $BASE/install-searxng.sh"; exit 1
    fi
    PYTHONPATH=$SRC SEARXNG_SETTINGS_PATH=$SETTINGS \
      nohup "$PY" -m searx.webapp > "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    echo "已启动 (PID $(cat "$PIDFILE"))"
    echo "看日志: $0 log   查状态: $0 status"
    ;;
  stop)
    if is_running; then
      kill "$(cat "$PIDFILE")" && echo "已停止 (PID $(cat "$PIDFILE"))"
      rm -f "$PIDFILE"
    else
      echo "未在运行"
    fi
    ;;
  status)
    if is_running; then
      echo "进程运行中 (PID $(cat "$PIDFILE"))"
      # 健康检查走 JSON —— 默认配置只开 html，这里能同时验出 formats 配错的情况
      body=$(curl -sS -m 10 "http://127.0.0.1:$PORT/search?q=test&format=json" 2>&1)
      if echo "$body" | head -c 200 | grep -q '"results"'; then
        echo "JSON API: OK (http://127.0.0.1:$PORT/search)"
      else
        echo "JSON API: 异常 —— 检查 settings.yml 的 search.formats 是否含 json"
        echo "响应前 200 字节: $(echo "$body" | head -c 200)"
      fi
    else
      echo "未运行"
    fi
    ;;
  log)
    tail -f "$LOG"
    ;;
  *)
    echo "用法: $0 [start|stop|status|log]"; exit 1
    ;;
esac
