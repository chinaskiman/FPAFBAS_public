# Futures Alert Bot

Alert-only Binance USDT perpetual futures scanner with:
- `backend/`: FastAPI service, Binance ingestion (REST bootstrap + WS closed candles), indicators, S/R levels, openings, alert persistence, Telegram notifications, replay/backtest.
- `frontend/`: Vite + React dashboard with watchlist management, TradingView-style chart workspace, replay UI, and alert review.

Production deployment: see `DEPLOYMENT.md`.

## Quickstart

### Backend
Requirements: Python 3.11+

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload --port 8000
```

### Frontend
Requirements: Node 18+

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` and `/health` to `http://localhost:8000`.

## Docker (Production)

```powershell
cp .env.example .env
docker compose up -d --build
```

The web UI will be at `http://localhost/`.

## Environment (.env)

The backend loads env vars from `backend/.env` (if present) via `python-dotenv`.
For Docker Compose, use the repo-root `.env`.
If `/data` does not exist (local dev), the backend falls back to the repo `data/` directory.
You can also set them in your shell.

Common settings:
- `DATA_DIR` (default: `/data`)
- `SQLITE_PATH` (default: `/data/app.db`)
- `WATCHLIST_PATH` (default: `/data/watchlist.json`)
- `POLLER_LOCK_PATH` (default: `/data/poller.lock`)
- `LOG_LEVEL` (default: `INFO`)
- `BINANCE_FAPI_REST` (default: `https://fapi.binance.com`)
- `BINANCE_FAPI_WS` (default: `wss://fstream.binance.com`)
- `CACHE_MAXLEN` (default: `1200`)
- `DISABLE_INGESTION=1` to skip Binance bootstrap/WS during tests
- `POLL_SECONDS` (default: `15`) poller interval
- `POLLER_START_PAUSED` (`true|false`, default: `false`)
- `TELEGRAM_ENABLED` (`true|false`, default: auto-enabled if token+chat_id present)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ADMIN_TOKEN` (required for operator endpoints)
- `CORS_ORIGINS` (comma-separated, default: `http://localhost:5173`)

Example `backend/.env`:
```env
TELEGRAM_BOT_TOKEN=123456789:abcd-your-token
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ENABLED=true
POLL_SECONDS=15
ADMIN_TOKEN=change-me
CORS_ORIGINS=http://localhost,http://127.0.0.1
```

## How It Works

- On startup, backend bootstraps klines from Binance REST and opens WS streams for closed 15m/1h candles.
- Candle caches feed indicators, pivots, levels, and signal detection.
- Alerts are persisted to SQLite and de-duplicated before notifying Telegram.
- Replay mode runs the same pipeline candle-by-candle without lookahead.

## Key Endpoints

Core:
- `GET /health` (legacy)
- `GET /healthz`
- `GET /readyz`
- `GET /api/watchlist` / `PUT /api/watchlist`
- `GET /api/candles/{symbol}/{tf}?limit=500` (time in ms)
- `GET /api/levels/{symbol}?debug=1`
- `GET /api/openings/{symbol}/{tf}?limit=300`
- `GET /api/alerts?limit=100&offset=0` / `GET /api/alerts/{id}`

Signals & filters:
- `GET /api/level_events/{symbol}/{tf}?limit=300`
- `GET /api/setup_candles/{symbol}/{tf}?limit=300`
- `GET /api/di_peak/{symbol}/{tf}`
- `GET /api/volume/{symbol}/{tf}`
- `GET /api/rsi/{symbol}/{tf}`
- `GET /api/hwc/{symbol}`

Operator:
- `GET /api/poller/status` (requires `Authorization: Bearer <ADMIN_TOKEN>`)
- `POST /api/poller/mode` `{ "mode": "run|pause_new|pause_all" }` (admin)
- `POST /api/telegram/test` (admin)
- `GET /api/alerts/export.csv` (admin)

Replay:
- `GET /api/replay/{symbol}/{tf}?from_ms=...&to_ms=...&step=...&warmup=...`
- `GET /api/replay_summary/{symbol}/{tf}?from_ms=...&to_ms=...&step=...&warmup=...`

## Frontend Highlights

- Watchlist management (add/remove symbols, edit entry TFs).
- Chart Workspace with candlesticks, SMA7, S/R zones, and signal markers.
- Replay UI with scrubber + signal details.
- Alert review with filtering/pagination and Telegram message preview.
- Journal page with filters, detail drawer, and JSONL export (admin token required).

## Auto Journal

Every notified signal is journaled with:
- 100-candle lookback (including signal candle)
- indicators (ATR/RSI/DI/ADX + existing series)
- planned entry = next candle open

Env vars:
- `JOURNAL_DB_URL` (optional; if unset, uses `data/journal.db`)
- `JOURNAL_INTRACANDLE_MODEL` (reserved for outcome tracking; default `worst_case`)
- `ADMIN_TOKEN` (required for `/api/journal/export.jsonl`)

UI:
- Open the **Journal** section in the dashboard to browse entries.
- Export JSONL prompts for `ADMIN_TOKEN` (stored in memory only).

## Notes

- Candle timestamps are epoch **milliseconds** in the backend and API.
- The frontend chart converts ms -> seconds for `lightweight-charts`.
