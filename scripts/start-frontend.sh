#!/usr/bin/env bash
# Starts the React dev server on http://localhost:5173 (proxies /api to the backend).
set -euo pipefail
cd "$(dirname "$0")/../frontend"
exec npm run dev
