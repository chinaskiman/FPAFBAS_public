#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
DATA_DIR="${REPO_ROOT}/data"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.vps.yml"

log() {
  printf '%s\n' "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

read_env_value() {
  local key="$1"
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo ""
    return 0
  fi
  local raw
  raw="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 || true)"
  raw="${raw#*=}"
  raw="${raw%\"}"
  raw="${raw#\"}"
  echo "${raw}"
}

check_port_free() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn "( sport = :${port} )" | tail -n +2 | grep -q .; then
      fail "Port ${port} is already in use."
    fi
  elif command -v lsof >/dev/null 2>&1; then
    if lsof -i TCP:"${port}" -sTCP:LISTEN -nP >/dev/null 2>&1; then
      fail "Port ${port} is already in use."
    fi
  fi
}

is_existing_stack_running() {
  if [[ ! -f "${COMPOSE_FILE}" ]]; then
    return 1
  fi
  if docker compose -f "${COMPOSE_FILE}" ps -q caddy 2>/dev/null | grep -q .; then
    return 0
  fi
  return 1
}

log "Running VPS preflight checks from ${REPO_ROOT}"

command -v docker >/dev/null 2>&1 || fail "docker is not installed."
docker info >/dev/null 2>&1 || fail "docker daemon is not reachable."
docker compose version >/dev/null 2>&1 || fail "docker compose plugin is not installed."

[[ -f "${ENV_FILE}" ]] || fail ".env not found at ${ENV_FILE}. Copy from .env.example first."

ADMIN_TOKEN="$(read_env_value "ADMIN_TOKEN")"
DOMAIN="$(read_env_value "DOMAIN")"
ACME_EMAIL="$(read_env_value "ACME_EMAIL")"

[[ -n "${ADMIN_TOKEN}" && "${ADMIN_TOKEN}" != "change-me-with-a-long-random-token" ]] || fail "Set a strong ADMIN_TOKEN in .env."
[[ -n "${DOMAIN}" && "${DOMAIN}" != "example.com" ]] || fail "Set DOMAIN in .env to your real hostname."
[[ -n "${ACME_EMAIL}" && "${ACME_EMAIL}" != "admin@example.com" ]] || fail "Set ACME_EMAIL in .env."

if is_existing_stack_running; then
  log "Existing stack detected; skipping host port checks."
else
  check_port_free 80
  check_port_free 443
fi

if command -v getent >/dev/null 2>&1; then
  if ! getent ahostsv4 "${DOMAIN}" >/dev/null 2>&1; then
    fail "DOMAIN=${DOMAIN} does not resolve yet. Add DNS A record first."
  fi
fi

mkdir -p "${DATA_DIR}"
[[ -f "${DATA_DIR}/watchlist.json" ]] || fail "Missing ${DATA_DIR}/watchlist.json. Create it or copy from repository defaults."

log "Preflight checks passed."
log "DOMAIN=${DOMAIN}"
