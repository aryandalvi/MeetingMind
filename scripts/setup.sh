#!/usr/bin/env bash
# MeetingMind one-time setup (macOS / Linux / Git Bash). Run from anywhere: bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
[ -d .venv ] || "$PYTHON" -m venv .venv
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi
"$PY" -m pip install --upgrade pip
# CPU build of PyTorch unless torch is already available (avoids a multi-GB CUDA download).
"$PY" -c "import torch" 2>/dev/null || "$PY" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
"$PY" -m pip install -r backend/requirements-dev.txt
"$PY" -m spacy download en_core_web_sm
(cd frontend && npm install)
echo
echo "Setup complete. Start the app with:"
echo "  bash scripts/start-backend.sh    # terminal 1"
echo "  bash scripts/start-frontend.sh   # terminal 2"
