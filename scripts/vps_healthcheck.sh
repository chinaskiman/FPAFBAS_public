#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.vps.yml"

read_env_value() {
  local key="$1"
  local raw
  raw="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 || true)"
  raw="${raw#*=}"
  raw="${raw%\"}"
  raw="${raw#\"}"
  echo "${raw}"
}

[[ -f "${ENV_FILE}" ]] || {
  echo ".env not found at ${ENV_FILE}" >&2
  exit 1
}

DOMAIN="$(read_env_value "DOMAIN")"
[[ -n "${DOMAIN}" ]] || {
  echo "DOMAIN is not set in .env" >&2
  exit 1
}

BASE_URL="https://${DOMAIN}"

cd "${REPO_ROOT}"
docker compose -f "${COMPOSE_FILE}" ps

curl -fsS "${BASE_URL}/" >/dev/null
curl -fsS "${BASE_URL}/api/healthz" >/dev/null
curl -fsS "${BASE_URL}/api/readyz" >/dev/null
curl -fsS "${BASE_URL}/api/forward_test/status" >/dev/null

echo "Health checks passed for ${BASE_URL}"
