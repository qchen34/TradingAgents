#!/usr/bin/env bash
# 先释放 3000 端口上的旧 next dev，再删 .next，最后启动开发服务器
set -e
PORT="${PORT:-3000}"

if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti ":${PORT}" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "→ 停止占用端口 ${PORT} 的进程: ${PIDS}"
    kill $PIDS 2>/dev/null || kill -9 $PIDS 2>/dev/null || true
    sleep 1
  fi
fi

echo "→ 删除 .next 缓存"
rm -rf .next

echo "→ 启动 next dev (port ${PORT})"
exec npx next dev -p "${PORT}"
