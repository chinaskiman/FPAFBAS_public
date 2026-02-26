# Ops Runbook (Checklist)

## 0) What’s running
- **web**: nginx serving the React build + proxying `/api/*` to the backend
- **api**: FastAPI + background poller (single instance enforced via `/data/poller.lock`)
- **data** persisted in `./data` (bind-mounted to `/data` in containers)

## 1) Required env vars
- `ADMIN_TOKEN` (required for admin endpoints; if missing, admin endpoints return **503**)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optional; alerts still persist even if missing)
- Paths:
  - `DATA_DIR=/data`
  - `SQLITE_PATH=/data/app.db`
  - `WATCHLIST_PATH=/data/watchlist.json`
  - `POLLER_LOCK_PATH=/data/poller.lock`

## 2) Start / Stop / Restart
### Start (first time)
1. `cp .env.example .env` and set:
   - `ADMIN_TOKEN` to a strong secret
   - Telegram vars if you want notifications
2. `mkdir -p data`
3. `docker compose up -d --build`

### Stop
- `docker compose down`

### Restart (safe)
- Prefer a rolling restart:
  - `docker compose restart api`
  - then `docker compose restart web`
- If you’re troubleshooting the poller, restart **api** only:
  - `docker compose restart api`

## 3) Health verification
### Backend liveness
- `curl -fsS http://<host>/api/healthz`

### Backend readiness
- `curl -fsS http://<host>/api/readyz | jq`
Expected:
- `ok: true`
- `db_ok: true`
- `watchlist_ok: true`
- `lock_acquired: true` on the instance that runs the poller
Notes:
- If `lock_acquired: false`, that instance will not run the poller (by design).
- Readiness should still be `ok: true` if the API is otherwise functional.

### Frontend
- Open `http://<host>/` in browser

## 4) Admin endpoints access
All admin endpoints require:
- `Authorization: Bearer <ADMIN_TOKEN>`

Example:
```bash
curl -fsS \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://<host>/api/poller/status
If ADMIN_TOKEN is missing/unset:

admin endpoints return 503 (intentional hard-fail to prevent accidental exposure)

5) Poller operational notes
Single-poller rule
Poller uses a file lock at /data/poller.lock.

If the lock can’t be acquired:

poller does not start

status indicates lock_acquired=false

Pause modes
mode=run: scanning + insert + notify

mode=pause_new: scanning happens; new alerts are suppressed (not inserted/sent); suppressed count increments

mode=pause_all: scan loop does not run

Common poller checks
Status:

/api/poller/status (admin)

Test Telegram:

/api/telegram/test (admin)

6) Logs (where to look)
Docker logs
Backend:

docker compose logs -f api

Frontend/nginx:

docker compose logs -f web

Typical symptoms
Telegram not sending:

check notify_error in alerts table / API payloads

confirm TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

Poller not scanning:

check mode (pause_all)

check lock_acquired

check last_error

7) Backups (SQLite + watchlist)
Data location on host: ./data/

Quick backup (recommended before upgrades)
Put poller in pause_all (admin)

Copy data directory:

tar -czf backup-$(date +%F-%H%M).tgz data/

Resume poller mode (run) if needed

SQLite-only backup (lightweight)
cp data/app.db data/app.db.bak.$(date +%F-%H%M)

Restore
Stop services: docker compose down

Replace data/app.db and/or data/watchlist.json with backups

Start: docker compose up -d

8) Upgrading / deploying a new version
Safe upgrade steps
curl /api/readyz and ensure healthy before starting

Set poller mode to pause_all (admin)

Backup ./data (see Backups)

Pull/build new images:

docker compose build --no-cache (optional)

docker compose up -d --build

Verify:

/api/healthz and /api/readyz

UI loads

Set poller mode back to run (admin)

Schema migrations
If you add/alter SQLite schema in the future:

include a startup migration step OR a one-time migration command

note it explicitly in release notes

9) Security checklist (minimum)
Set a strong ADMIN_TOKEN and keep it secret

Only expose ports 80/443 publicly (nginx)

Consider putting nginx behind HTTPS (Caddy/Traefik or a cloud LB)

Keep /api/* behind nginx (do not publish api container port publicly)

Rotate ADMIN_TOKEN periodically:

update .env, restart api

10) Scaling / HA warning
This setup assumes one host with a shared /data volume.

Do not scale api replicas across multiple hosts unless you implement distributed leader election / shared locking.

On a single host, multiple api containers will respect the same file lock if they share the same /data mount.

## 11) Troubleshooting decision tree

- If **/api/readyz fails** → run `curl -fsS http://<host>/api/readyz | jq` and check `db_ok`, `watchlist_ok`, `lock_acquired`. Typical causes: missing `/data` volume, invalid watchlist JSON, DB path not writable.
- If **admin endpoints return 503** → `ADMIN_TOKEN` is missing. Set it in `.env`, restart api, then call admin endpoints with `curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" http://<host>/api/poller/status`.
- If **no alerts are being created** → check poller status: `curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" http://<host>/api/poller/status`. Ensure `mode=run`, `lock_acquired=true`, and `last_scan_at` is moving. Also verify openings exist: `curl -fsS http://<host>/api/openings/BTCUSDT/15m?limit=10`.
- If **poller says running but last_scan_at is not moving** → check `mode` and `lock_acquired`: `curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" http://<host>/api/poller/status`. Typical causes: `pause_all`, lock not acquired, ingestion disabled, or no enabled symbols.
- If **poller locked (lock_acquired=false)** → another api instance holds `/data/poller.lock` or a different host is using the same volume. Confirm single api container and shared volume; check `curl -fsS http://<host>/api/readyz | jq`.
- If **everything is suppressed (pause_new)** → check mode: `curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" http://<host>/api/poller/status`. Switch back: `curl -fsS -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"mode":"run"}' http://<host>/api/poller/mode`.
- If **alerts exist but Telegram not sending** → check notify_error via `curl -fsS http://<host>/api/alerts?limit=5`, then test Telegram: `curl -fsS -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"text":"test"}' http://<host>/api/telegram/test`. Typical causes: missing `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` or `TELEGRAM_ENABLED=false`.
- If **UI shows blank chart / no candles** → check candles API: `curl -fsS http://<host>/api/candles/BTCUSDT/1h?limit=5`. If empty, ingestion may be disabled (`DISABLE_INGESTION=1`), symbols disabled in watchlist, or WS/REST not running.
