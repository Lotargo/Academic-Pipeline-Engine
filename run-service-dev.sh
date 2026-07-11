#!/usr/bin/env bash
set -euo pipefail

container="${APE_DEV_DB_CONTAINER:-ape-dev-postgres}"
port="${APE_DEV_DB_PORT:-54329}"
export APE_DATABASE_SYNC_URL="${APE_DATABASE_SYNC_URL:-postgresql+psycopg://ape:ape_dev_password@127.0.0.1:${port}/ape}"
export APE_DATABASE_ASYNC_URL="${APE_DATABASE_ASYNC_URL:-postgresql+asyncpg://ape:ape_dev_password@127.0.0.1:${port}/ape}"
export APE_AUTH_JWT_SECRET="${APE_AUTH_JWT_SECRET:-local-development-auth-secret-2026-minimum-32-chars}"
python_bin="${PYTHON_BIN:-python3}"
[ -x .venv/bin/python ] && python_bin=.venv/bin/python

command -v docker >/dev/null || { echo "Docker is required for service-dev."; exit 1; }
if ! docker inspect "$container" >/dev/null 2>&1; then
  docker run --name "$container" -e POSTGRES_USER=ape -e POSTGRES_PASSWORD=ape_dev_password -e POSTGRES_DB=ape -p "${port}:5432" -d postgres:16-alpine
else
  docker start "$container" >/dev/null
fi
for _ in $(seq 1 30); do docker exec "$container" pg_isready -U ape -d ape >/dev/null 2>&1 && break; sleep 1; done
docker exec "$container" pg_isready -U ape -d ape >/dev/null || { echo "PostgreSQL did not become ready."; exit 1; }

"$python_bin" -c 'import asyncpg, fastapi, psycopg, uvicorn' >/dev/null 2>&1 || "$python_bin" -m pip install -e .
"$python_bin" -m alembic upgrade head
"$python_bin" -m uvicorn academic_pe.server:app --reload --host 127.0.0.1 --port 8000 &
backend_pid=$!
(cd ui && { command -v pnpm >/dev/null && pnpm run dev || npm run dev; }) &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
echo "service-dev: http://localhost:3000 (authenticated mode)"
wait
