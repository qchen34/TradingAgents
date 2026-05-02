#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] 启动 FastAPI: http://127.0.0.1:8000"
(
  cd "$ROOT_DIR"
  python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
) &
API_PID=$!

echo "[2/3] 启动 Next.js: http://127.0.0.1:3000"
(
  cd "$ROOT_DIR/frontend"
  npm run dev
) &
WEB_PID=$!

echo "[3/3] 保留 Streamlit: http://127.0.0.1:8501"
(
  cd "$ROOT_DIR"
  streamlit run app.py
) &
ST_PID=$!

cleanup() {
  echo "Shutting down..."
  kill "$API_PID" "$WEB_PID" "$ST_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM
wait

