#!/usr/bin/env bash
# Qwen3-8B vLLM 服务管理: ./run-server.sh [start|stop|status|log]
# 部署位置: Inspire Studio 容器 $BASE/run-server.sh
BASE=/inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness
# 默认 Qwen3-8B。切换模型（P1 校准要用 Qwen3-4B）：
#   QWEN_MODEL_DIR=$BASE/models/Qwen3-4B QWEN_SERVED_NAME=Qwen/Qwen3-4B ./run-server.sh start
# 一张 4090 放不下两个模型，切换前先 stop。
MODEL_DIR=${QWEN_MODEL_DIR:-$BASE/models/Qwen3-8B}
SERVED_NAME=${QWEN_SERVED_NAME:-Qwen/Qwen3-8B}
PORT=${QWEN_PORT:-8000}
LOG=$BASE/logs/vllm.log
PIDFILE=$BASE/logs/vllm.pid

source $BASE/.venv/bin/activate
mkdir -p $BASE/logs

is_running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

case "${1:-start}" in
  start)
    if is_running; then
      echo "已在运行 (PID $(cat "$PIDFILE"))"; exit 0
    fi
    nohup vllm serve "$MODEL_DIR" \
        --served-model-name "$SERVED_NAME" \
        --max-model-len 32768 \
        --gpu-memory-utilization 0.90 \
        --enable-auto-tool-choice \
        --tool-call-parser hermes \
        --reasoning-parser qwen3 \
        --port $PORT \
        > "$LOG" 2>&1 &
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
      if curl -s http://localhost:$PORT/health >/dev/null 2>&1; then
        echo "API 健康检查: OK (http://localhost:$PORT/v1)"
      else
        echo "API 尚未就绪（可能还在加载模型，用 '$0 log' 看进度）"
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
