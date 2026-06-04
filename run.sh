#!/bin/bash
# myteam 启动脚本
# 用法: ./run.sh [start|stop]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR/backend:${PYTHONPATH:-}"
export MYTEAM_ROOT="$SCRIPT_DIR"

export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="${NO_PROXY}"

PORT=${LOCAL_AGENT_PORT:-8765}
PID_FILE="$SCRIPT_DIR/.agent-hub.pid"
SERVER="$SCRIPT_DIR/backend/hub/api/server.py"

find_python() {
  if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    echo "$SCRIPT_DIR/venv/bin/python3"
  else
    command -v python3 || command -v python
  fi
}

find_server_pids() {
  local pids=""

  if [ -f "$PID_FILE" ]; then
    local pid
    pid=$(tr -d '[:space:]' < "$PID_FILE")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      pids="$pid"
    fi
  fi

  if [ -z "$pids" ] && command -v pgrep >/dev/null 2>&1; then
    pids=$(pgrep -f "$SERVER" 2>/dev/null | tr '\n' ' ')
  fi

  if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
  fi

  echo "$pids" | tr ' ' '\n' | sed '/^$/d' | sort -u | tr '\n' ' '
}

stop_server() {
  local pids
  pids=$(find_server_pids)

  if [ -z "$pids" ]; then
    echo "未找到运行中的 Agent Hub（端口 $PORT）"
    rm -f "$PID_FILE"
    return 1
  fi

  echo "停止 Agent Hub (PID: $(echo "$pids" | tr ' ' ', ') )..."
  kill $pids 2>/dev/null

  local i
  for i in 1 2 3 4 5; do
    sleep 0.4
    pids=$(find_server_pids)
    [ -z "$pids" ] && break
  done

  pids=$(find_server_pids)
  if [ -n "$pids" ]; then
    echo "进程未退出，强制停止..."
    kill -9 $pids 2>/dev/null
    sleep 0.2
  fi

  rm -f "$PID_FILE"
  echo "Agent Hub 已停止"
  return 0
}

start_server() {
  PYTHON=$(find_python)
  if [ -z "$PYTHON" ]; then
    echo "错误: 未找到 Python 3"
    exit 1
  fi

  if [ -n "$(find_server_pids)" ]; then
    echo "Agent Hub 已在运行（端口 $PORT）"
    exit 1
  fi

  "$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "安装依赖..."
    "$PYTHON" -m pip install -q -r requirements.txt
  }

  echo ""
  echo "=============================================="
  echo "  myteam Agent Hub"
  echo "  Local:   http://localhost:$PORT"
  echo "  Network: http://0.0.0.0:$PORT (局域网通过本机 IP 访问)"
  echo "  根目录: $SCRIPT_DIR"
  echo "  停止: ./run.sh stop"
  echo "=============================================="
  echo ""

  trap 'rm -f "$PID_FILE"' EXIT INT TERM
  echo $$ > "$PID_FILE"
  export LOCAL_AGENT_PORT="$PORT"
  exec "$PYTHON" "$SERVER"
}

case "${1:-start}" in
  start) start_server ;;
  stop) stop_server ;;
  *) echo "用法: $0 [start|stop]"; exit 1 ;;
esac
