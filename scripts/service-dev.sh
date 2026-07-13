#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-up}"
python_bin="${PYTHON_BIN:-python3}"
npx_bin="${APE_NPX_BIN:-}"

if [[ -x "$root/.venv/bin/python" ]]; then
  python_bin="$root/.venv/bin/python"
fi
if [[ -z "$npx_bin" && -x "$HOME/.local/node/bin/npx" ]]; then
  export PATH="$HOME/.local/node/bin:$PATH"
  npx_bin="$HOME/.local/node/bin/npx"
fi
if [[ -z "$npx_bin" ]]; then
  if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "WSL service-dev requires native Node.js 22 at \$HOME/.local/node/bin; refusing a Windows npx fallback." >&2
    exit 1
  fi
  npx_bin="npx"
fi

require_command() {
  command -v "$1" >/dev/null || { echo "$1 is required for service-dev." >&2; exit 1; }
}

compose() {
  docker compose --env-file "$root/.env.service-dev" "$@"
}

cd "$root"
require_command docker
require_command "$npx_bin"
require_command "$python_bin"
if [[ "$npx_bin" == "$HOME/.local/node/bin/npx" ]]; then
  node_version="$($HOME/.local/node/bin/node --version)"
  [[ "$node_version" == v22.* ]] || { echo "WSL service-dev requires Node.js 22 LTS; found $node_version." >&2; exit 1; }
fi
export APE_NPX_BIN="$npx_bin"

case "$action" in
  up)
    "$npx_bin" --yes supabase start --exclude logflare,vector >/dev/null
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
    "$npx_bin" --yes supabase stop >/dev/null
    echo "service-dev is stopped."
    ;;
  *)
    echo "Usage: ./run-service-dev.sh [up|status|down]" >&2
    exit 2
    ;;
esac
