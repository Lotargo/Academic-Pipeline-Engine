#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON_BIN:-python3}"
[ -x .venv/bin/python ] && python_bin=.venv/bin/python
"$python_bin" -c 'import fastapi, uvicorn' >/dev/null 2>&1 || "$python_bin" -m pip install -e .
"$python_bin" -m uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000 &
backend_pid=$!
(cd ui && { command -v pnpm >/dev/null && pnpm run dev || npm run dev; }) &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
echo "local-first: http://localhost:3000 (account login is unavailable)"
wait
