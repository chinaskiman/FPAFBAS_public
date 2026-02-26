# Deployment & Operations

## Local Quickstart (Docker Compose)

```powershell
cp .env.example .env
docker compose up -d --build
```

The app will be available at:
- Web UI: `http://localhost/`
- API: `http://localhost/api/`

## VPS 24/7 Stack (HTTPS + Reverse Proxy)

This repo includes a dedicated production stack:
- `docker-compose.vps.yml` (resource limits + log rotation)
- `deploy/Caddyfile` (automatic Let's Encrypt TLS)

### Prerequisites

1. Point your DNS `A` record to the VPS IP.
2. Open inbound ports `80` and `443` on VPS firewall/security group.
3. Install Docker Engine + Docker Compose plugin on the VPS.

### Configure Environment

```bash
cp .env.example .env
```

Set at minimum in `.env`:
- `ADMIN_TOKEN` (long random value)
- `DOMAIN` (your public hostname)
- `ACME_EMAIL` (certificate registration email)
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (if notifications enabled)

### Start Production Stack

```bash
docker compose -f docker-compose.vps.yml up -d --build
```

The app will be available at:
- Web UI: `https://<DOMAIN>/`
- API: `https://<DOMAIN>/api/`

## Environment Variables

Required for admin/ops:
- `ADMIN_TOKEN` (Bearer token for `/api/poller/*`, `/api/telegram/test`, `/api/alerts/export.csv`)

Common settings:
- `DATA_DIR` (default: `/data`)
- `SQLITE_PATH` (default: `/data/app.db`)
- `WATCHLIST_PATH` (default: `/data/watchlist.json`)
- `POLLER_LOCK_PATH` (default: `/data/poller.lock`)
- `POLL_SECONDS` (default: `15`)
- `CORS_ORIGINS` (comma-separated)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DOMAIN` (for TLS proxy host, used by Caddy)
- `ACME_EMAIL` (for Let's Encrypt account)

## Data Persistence

The Compose file mounts `./data` into the container at `/data`:
- SQLite DB: `/data/app.db`
- Watchlist JSON: `/data/watchlist.json`
- Poller lock: `/data/poller.lock`

For VPS TLS certificates, Caddy stores cert state in the Docker volumes:
- `caddy_data`
- `caddy_config`

## Health Checks

- `GET /healthz` -> process alive
- `GET /readyz` -> DB + watchlist dir OK + poller status

## Safe Updates

1. Update code and rebuild:
   ```bash
   docker compose -f docker-compose.vps.yml up -d --build
   ```
2. Verify readiness:
   ```bash
   curl https://<DOMAIN>/api/readyz
   ```

## Backups and Restore

Linux scripts are included:

```bash
chmod +x scripts/backup_data.sh scripts/restore_data.sh
```

Create a backup (brief API pause for SQLite consistency):
```bash
bash scripts/backup_data.sh
```

Restore from a backup archive:
```bash
bash scripts/restore_data.sh backups/fpafbas-backup-YYYYMMDDTHHMMSSZ.tar.gz
```

## Notes on Poller Lock

Only one poller runs per host thanks to the filesystem lock at `/data/poller.lock`.
Do **not** scale `api` replicas unless you move the poller into a separate service or
add a distributed leader election.
