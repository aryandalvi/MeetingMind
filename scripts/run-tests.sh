#!/usr/bin/env bash
# Runs backend tests (pytest), frontend tests (vitest), the TypeScript check and the evaluation.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then PY="$PWD/.venv/bin/python"; else PY="$PWD/.venv/Scripts/python.exe"; fi
(cd backend && "$PY" -m pytest && "$PY" -m evaluation.evaluate)   # pytest -m "not slow" skips the 1.2 GB model test
(cd frontend && npm test && npx tsc -b)
