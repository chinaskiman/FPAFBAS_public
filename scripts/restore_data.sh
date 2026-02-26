#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-archive.tar.gz>"
  exit 1
fi

ARCHIVE_PATH="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.vps.yml}"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Backup archive not found: $ARCHIVE_PATH"
  exit 1
fi

cd "$ROOT_DIR"

echo "[1/4] Stopping stack..."
docker compose -f "$COMPOSE_FILE" down

echo "[2/4] Restoring files from archive..."
tar -xzf "$ARCHIVE_PATH" -C "$ROOT_DIR"

echo "[3/4] Starting stack..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "[4/4] Done"
