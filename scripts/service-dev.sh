#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-up}"
python_bin="${PYTHON_BIN:-python3}"

if [[ -x "$root/.venv/bin/python" ]]; then
  python_bin="$root/.venv/bin/python"
fi

require_command() {
  command -v "$1" >/dev/null || { echo "$1 is required for service-dev." >&2; exit 1; }
}

compose() {
  docker compose --env-file "$root/.env.service-dev" -f "$root/docker-compose.service-dev.yml" "$@"
}

cd "$root"
require_command docker
require_command npx
require_command "$python_bin"

case "$action" in
  up)
    npx --yes supabase start --exclude logflare,vector >/dev/null
    "$python_bin" "$root/scripts/write_service_dev_env.py"
    compose up --build --detach --wait
    echo "service-dev is ready: http://localhost:3000 (API: http://localhost:8000)"
    ;;
  status)
    if [[ ! -f "$root/.env.service-dev" ]]; then
      echo "service-dev has not been initialized. Run ./run-service-dev.sh first." >&2
      exit 1
    fi
    compose ps
    ;;
  down)
    if [[ -f "$root/.env.service-dev" ]]; then
      compose down
    fi
    npx --yes supabase stop >/dev/null
    echo "service-dev is stopped."
    ;;
  *)
    echo "Usage: ./run-service-dev.sh [up|status|down]" >&2
    exit 2
    ;;
esac
