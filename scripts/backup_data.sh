#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.vps.yml}"
BACKUP_DIR="${1:-$ROOT_DIR/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_PATH="$BACKUP_DIR/fpafbas-backup-$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"
cd "$ROOT_DIR"

echo "[1/4] Stopping api for a consistent SQLite snapshot..."
docker compose -f "$COMPOSE_FILE" stop api

echo "[2/4] Building archive..."
include_paths=("data" "docker-compose.vps.yml" "deploy/Caddyfile")
if [[ -f ".env" ]]; then
  include_paths+=(".env")
fi
tar -czf "$ARCHIVE_PATH" "${include_paths[@]}"

echo "[3/4] Starting api..."
docker compose -f "$COMPOSE_FILE" start api

echo "[4/4] Done"
echo "$ARCHIVE_PATH"
