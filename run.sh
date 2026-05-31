#!/bin/bash
# Local Agent Chat 启动脚本
# 启动 web 服务器，通过浏览器与 AI Agent 对话

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 确保本地流量不走代理（解决代理缓存/拦截问题）
export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="${NO_PROXY}"

# 优先使用虚拟环境
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
  PYTHON="$SCRIPT_DIR/venv/bin/python3"
else
  PYTHON=$(command -v python3 || command -v python)
fi

if [ -z "$PYTHON" ]; then
  echo "错误: 未找到 Python 3"
  exit 1
fi

# Check dependencies
"$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "安装依赖..."
  "$PYTHON" -m pip install -q -r requirements.txt
  if [ $? -ne 0 ]; then
    echo "依赖安装失败，请手动运行: pip install -r requirements.txt"
    exit 1
  fi
  echo "依赖安装完成"
fi

# Start server
PORT=${LOCAL_AGENT_PORT:-8765}
echo ""
echo "=============================================="
echo "  Agent Hub v2.1"
echo "  http://localhost:$PORT"
echo "=============================================="
echo ""

exec "$PYTHON" base/server.py