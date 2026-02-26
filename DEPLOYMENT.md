# Deployment & Operations

## Quickstart (Docker Compose)

```powershell
cp .env.example .env
docker compose up -d --build
```

The app will be available at:
- Web UI: `http://localhost/`
- API: `http://localhost/api/`

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

## Data Persistence

The Compose file mounts `./data` into the container at `/data`:
- SQLite DB: `/data/app.db`
- Watchlist JSON: `/data/watchlist.json`
- Poller lock: `/data/poller.lock`

## Health Checks

- `GET /healthz` -> process alive
- `GET /readyz` -> DB + watchlist dir OK + poller status

## Safe Updates

1. Update code and rebuild:
   ```powershell
   docker compose up -d --build
   ```
2. Verify readiness:
   ```powershell
   curl http://localhost/api/readyz
   ```

## Notes on Poller Lock

Only one poller runs per host thanks to the filesystem lock at `/data/poller.lock`.
Do **not** scale `api` replicas unless you move the poller into a separate service or
add a distributed leader election.
