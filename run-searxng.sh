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
    if ! is_running; then
      echo "未运行"; exit 0
    fi
    echo "进程运行中 (PID $(cat "$PIDFILE"))"

    # 第一段: 服务起来没有。打首页，不触发真实搜索，所以很快。
    if ! curl -sS -m 5 -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then
      echo "HTTP: 无响应 —— 进程活着但没在 $PORT 上服务"
      echo "  刚启动的话等几秒重试；否则看日志: $0 log"
      exit 1
    fi
    echo "HTTP: OK (http://127.0.0.1:$PORT/)"

    # 第二段: JSON 接口。这一步会真的去查上游引擎，慢是正常的，
    # 所以超时给到 30s —— 默认配置只开 html，403 就是 formats 没配对。
    probe=$(mktemp)
    code=$(curl -sS -m 30 -o "$probe" -w '%{http_code}' \
             "http://127.0.0.1:$PORT/search?q=test&format=json" 2>/dev/null || echo "000")
    case "$code" in
      200)
        if grep -q '"results"' "$probe"; then
          echo "JSON API: OK"
        else
          echo "JSON API: 返回 200 但没有 results 字段"
          echo "  响应前 200 字节: $(head -c 200 "$probe")"
        fi
        ;;
      403)
        echo "JSON API: 403 —— settings.yml 的 search.formats 缺 json，或 limiter 没关"
        echo "  配置文件: $SETTINGS"
        ;;
      000)
        echo "JSON API: 30s 内无响应 —— 上游搜索引擎慢或不可达"
        echo "  验证出网: curl -sS -m 10 -o /dev/null -w '%{http_code}\\n' https://duckduckgo.com"
        echo "  看日志:   $0 log"
        ;;
      *)
        echo "JSON API: HTTP $code"
        echo "  响应前 200 字节: $(head -c 200 "$probe")"
        ;;
    esac
    rm -f "$probe"
    ;;
  log)
    tail -f "$LOG"
    ;;
  *)
    echo "用法: $0 [start|stop|status|log]"; exit 1
    ;;
esac
