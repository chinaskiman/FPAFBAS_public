# Deployment & Operations

## Local Quickstart

```bash
cp .env.example .env
docker compose up -d --build
```

- Web UI: `http://localhost/`
- API: `http://localhost/api/`

## VPS 24/7 (HTTPS + Public Frontend)

This repo includes:
- `docker-compose.vps.yml` (api + web + caddy, restart policies, limits, log rotation)
- `deploy/Caddyfile` (automatic TLS via Let's Encrypt)
- `scripts/vps_preflight.sh` (checks VPS prerequisites)
- `scripts/vps_deploy.sh` (deploy + health checks)
- `scripts/vps_healthcheck.sh` (post-deploy verification)

### Prerequisites

1. DNS `A` record points `DOMAIN` to your VPS IP.
2. VPS firewall/security group allows inbound `80/tcp` and `443/tcp`.
3. Docker Engine + Docker Compose plugin installed.
4. Repository cloned on VPS.

### First Deploy (Recommended)

```bash
cp .env.example .env
```

Set these in `.env`:
- `ADMIN_TOKEN` (long random value)
- `DOMAIN` (example: `bot.example.com`)
- `ACME_EMAIL` (Let's Encrypt email)
- `CORS_ORIGINS=https://<DOMAIN>`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional)

Then run:

```bash
chmod +x scripts/vps_preflight.sh scripts/vps_deploy.sh scripts/vps_healthcheck.sh
bash scripts/vps_deploy.sh
```

After success:
- Frontend: `https://<DOMAIN>/`
- API ready check: `https://<DOMAIN>/api/readyz`
- Forward test status: `https://<DOMAIN>/api/forward_test/status`

### Ongoing Updates

```bash
git pull
bash scripts/vps_deploy.sh
```

If image rebuild is not needed:

```bash
bash scripts/vps_deploy.sh --no-build
```

## Environment Variables

Required for admin/ops:
- `ADMIN_TOKEN` (Bearer token for `/api/poller/*`, `/api/telegram/test`, CSV exports, forward-test mode)

Core runtime:
- `DATA_DIR` (default: `/data`)
- `SQLITE_PATH` (default: `/data/app.db`)
- `WATCHLIST_PATH` (default: `/data/watchlist.json`)
- `POLLER_LOCK_PATH` (default: `/data/poller.lock`)
- `POLL_SECONDS` (default: `15`)
- `CORS_ORIGINS` (comma-separated origins)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DOMAIN` (TLS host for Caddy)
- `ACME_EMAIL` (Let's Encrypt account email)

Forward test:
- `FT_STARTING_EQUITY` (default `10000`)
- `FT_LEVERAGE` (default `20`)
- `FT_RISK_PCT` (default `0.01`)
- `FT_MAX_POSITIONS` (default `3`)
- `FT_FEE_RATE` (default `0.001`)
- `FT_TP_R` (default `2.0`)
- `FT_CANCEL_AFTER_CANDLES` (default `3`)
- `FT_RISK_FREE_RATE` (default `0.02`)
- `FT_TIMEZONE` (default `Europe/Berlin`)

## Data Persistence

Bind mount:
- Host `./data` -> container `/data`

Persisted files:
- SQLite: `/data/app.db`
- Watchlist: `/data/watchlist.json`
- Poller lock: `/data/poller.lock`

Caddy cert/state volumes:
- `caddy_data`
- `caddy_config`

## Health Checks

- Liveness: `GET /healthz`
- Readiness: `GET /readyz`
- Forward test runtime: `GET /api/forward_test/status`
- Combined check script:
  ```bash
  bash scripts/vps_healthcheck.sh
  ```

## Backups and Restore

```bash
chmod +x scripts/backup_data.sh scripts/restore_data.sh
bash scripts/backup_data.sh
bash scripts/restore_data.sh backups/fpafbas-backup-YYYYMMDDTHHMMSSZ.tar.gz
```

## Poller Lock Note

Only one poller runs per host through `/data/poller.lock`.
Do not scale `api` replicas unless you introduce distributed leader election.
