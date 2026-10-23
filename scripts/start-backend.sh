#!/usr/bin/env bash
# Starts the FastAPI backend on http://127.0.0.1:8000 (API docs at /docs).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY="$PWD/.venv/bin/python"; else PY="$PWD/.venv/Scripts/python.exe"; fi
[ -e "$PY" ] || { echo "No .venv found. Run scripts/setup.sh first."; exit 1; }
cd backend
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
