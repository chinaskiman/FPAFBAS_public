#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.vps.yml"
ENV_FILE="${REPO_ROOT}/.env"

NO_BUILD=0
SKIP_PREFLIGHT=0

for arg in "$@"; do
  case "${arg}" in
    --no-build)
      NO_BUILD=1
      ;;
    --skip-preflight)
      SKIP_PREFLIGHT=1
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      echo "Usage: $0 [--no-build] [--skip-preflight]" >&2
      exit 1
      ;;
  esac
done

read_env_value() {
  local key="$1"
  local raw
  raw="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 || true)"
  raw="${raw#*=}"
  raw="${raw%\"}"
  raw="${raw#\"}"
  echo "${raw}"
}

if [[ ${SKIP_PREFLIGHT} -eq 0 ]]; then
  "${SCRIPT_DIR}/vps_preflight.sh"
fi

cd "${REPO_ROOT}"
if [[ ${NO_BUILD} -eq 1 ]]; then
  docker compose -f "${COMPOSE_FILE}" up -d
else
  docker compose -f "${COMPOSE_FILE}" up -d --build
fi

"${SCRIPT_DIR}/vps_healthcheck.sh"

DOMAIN="$(read_env_value "DOMAIN")"
echo "Deploy complete."
echo "Frontend: https://${DOMAIN}/"
echo "API ready: https://${DOMAIN}/api/readyz"
