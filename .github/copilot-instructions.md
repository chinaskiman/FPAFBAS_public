# Futures Alert Bot - Copilot Instructions

## Architecture Overview

**Futures Alert Bot** scans Binance USDT perpetuals for technical signals on 15m/1h/4h/1d timeframes:
- **Backend** (FastAPI FastAPI + background poller): Candle ingestion (REST bootstrap + WS), multi-indicator analysis, level/pivot detection, signal generation, SQLite persistence, Telegram notifications
- **Frontend** (React/Vite): Dashboard, chart workspace, replay/backtest UI, watchlist editor, journal review
- **Single-Poller Design**: File lock at `/data/poller.lock` ensures only one instance scans; multiple API servers can share a data volume
- **Zero Lookahead**: Replay mode runs same signal pipeline candle-by-candle for accurate backtesting

## Signal Detection Flow (Core Logic)

### Step 1: Indicator & Context Computation (`build_openings()` → `openings.py`)
For each (symbol, timeframe), fetch candles and compute 6 context metrics fed to every signal detector:
- **vol_ma5_slope_ok**: Volume MA5 slope > 1.8% (last 5 bars vs 5 bars prior)
- **pullback_vol_decline**: Last 3 bars declining volume (mean weighted toward recency)
- **not_at_peak_long/short**: DI+ or DI- at 20-bar peak (ADX context; prevents over-extension)
- **rsi_distance**: Distance of RSI(14) from 50 (clamped magnitude: useful for trend strength)
- **atr_mult**: ATR(5) multiplier clamped by RSI (high RSI → lower stop-loss distance)

Indicators cached per (symbol, tf) via `DerivedSeries`; recomputed on-demand, not persisted.

### Step 2: Multi-Timeframe Level Discovery (`compute_levels()` → `levels.py`)
- Fetch 1w/1d/4h candles; cluster swing highs/lows into S/R levels using DBSCAN (configurable `cluster_tol_pct`)
- Apply watchlist overrides (manual add/disable)
- Return sorted final levels for current timeframe

### Step 3: Level Event Detection (`detect_level_events()` → `level_events.py`)
For each level, scan candles looking for 3-part sequence:
1. **Break**: `prev_close ≤ level < close` (long) or `prev_close ≥ level > close` (short)
2. **Retest**: Within 20 bars, price touches level again → `{break_index, retest_index, retest_time}`
3. **Fakeout** (optional): Within 10 bars after retest, rejection candle with slope_ok → `{last_fakeout, fakeout_index}`
- Emits dict with: `level`, `direction` (up/down), `last_break`, `retest_index`, `last_fakeout`, plus context flags

### Step 4: Setup Candle Detection (`detect_setup_candles()` → `setup_candles.py`)
From validated level events (break + retest + no fakeout), scan forward for entry:
- **Long setup**: `candle.close > level AND close > SMA7 AND (prev.close ≤ SMA7 OR low ≤ SMA7)`
- **Short setup**: `candle.close < level AND close < SMA7 AND (prev.close ≥ SMA7 OR high ≥ SMA7)`
- Emits: `{level, direction, setup_index, entry, sl (via 0.15% buffer), sma7}`

### Step 5: Signal Scoring (`score_signal()` → `quality_controls.py`)
Each signal (from level_events or setup_candles) scored 0–100:
- vol_ma5_slope_ok → +25pts
- pullback_vol_decline → +15pts  
- di_not_at_peak → +25pts
- rsi_distance (0–20ppm) → +0–20pts
- **Minimum thresholds by type**: break=60, setup=55, fakeout=55 (configurable)

### Step 6: Suppression Filters (`AlertPoller.run_once()` → `alert_poller.py`)
After scoring, apply in sequence (first match suppresses):
1. **Min score**: Compare `score_signal()` vs `settings.min_score_by_type[alert_type]`
2. **Type cooldown**: Check `last_alert_time()` for (symbol, tf, type, direction, level); skip if recent
3. **Symbol rate limit**: `count_alerts(symbol, 1h) >= max_alerts_per_symbol_per_hour` (default 6)
4. **Global rate limit**: `count_alerts_global(1h) >= max_alerts_global_per_hour` (default 30)
5. **Pause modes**: `mode=pause_new` suppresses new alerts but keeps existing dedup; `mode=pause_all` skips scan
6. **Quiet hours**: Optional time filter (e.g., 23:00–07:00 CET) suppresses notifications only
7. **De-duplication**: `exists_alert()` checks (symbol, tf, type, direction, level) in last 60 min window

If passes all filters → insert to SQLite, mark for Telegram notify, record to journal

## Configuration & Env Vars

The watchlist `WATCHLIST_PATH` (`/data/watchlist.json`) defines enabled symbols + per-symbol:
- `entry_tfs`: Timeframes to scan (15m, 1h, 4h, 1d)
- `setups`: Boolean toggles for signal types (break, retest, fakeout, setup_candle)
- `levels`: Auto-level config (cluster tolerance %, max # levels) + manual overrides (add/disable prices)

Watchlist validated at startup via Pydantic; invalid config returns 503. Reloaded per API watchlist update.

Key env vars:
```
ADMIN_TOKEN                     # Bearer auth for /api/poller/* & /api/alerts/export.csv
POLL_SECONDS=15                 # AlertPoller tick interval
POLLER_START_PAUSED=false       # Start in pause_new mode
CACHE_MAXLEN=1200               # Max candles per (symbol, tf) cache
DISABLE_INGESTION=1             # Skip Binance in unit tests (auto set by conftest.py)
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID    # Optional; alerts still persist if missing
CORS_ORIGINS="http://localhost:5173"    # Frontend origin (comma-separated)
```

Storage: SQLite `app.db` (single table: `alerts`; no migrations). Journal: separate `journal.db`.

## Key Design Patterns

**Thread-Safe Caching**: `CandleCache` + `DerivedSeries` use `threading.Lock()` for all access; AlertPoller reads snapshots under lock.

**Alert De-Duplication** (`insert_alert_if_new()` in `storage.py`): Checks (symbol, tf, type, direction, level) + 60-min lookback before inserting; re-test on same level > 60 min later is treated as new.

**Configuration Validation** (Pydantic in `config.py`): Watchlist JSON validated on load; invalid config fails fast with 503. Symbol normalization: uppercase, regex check `[A-Z0-9]{6,}`.

**Admin Protection** (`@require_admin` in `ops.py`): Missing `ADMIN_TOKEN` → 503 on admin endpoints (intentional hard-fail).

**Single-Instance Poller** (`PollerFileLock` in `poller_lock.py`): Non-blocking acquire at startup. If lock fails, `lock_acquired=false`; API still responds but poller inactive. Essential for multi-pod; use distributed leader election (etcd/Redis) for scale beyond single host.

## Testing & Development

**Test Setup**: `conftest.py` auto-disables ingestion via `DISABLE_INGESTION=1` env var. Use `monkeypatch` for env vars, mock Binance clients. Import fixtures from `fixtures/klines.json`.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest                                # All tests
pytest tests/test_alert_polling_logic.py -v  # Single file
```

**Local Backend** (auto-reload):
```powershell
ADMIN_TOKEN=dev-token uvicorn app.main:app --reload --port 8000
```
Uses `data/watchlist.json` and `data/app.db` by default.

**Local Frontend** (proxies /api to backend):
```powershell
npm install && npm run dev  # Runs :5173
```

**Docker Compose** (production-like):
```powershell
cp .env.example .env  # Edit ADMIN_TOKEN, Telegram vars
mkdir -p data && docker compose up -d --build
curl -fsS http://localhost/api/readyz | jq
```

**Replay/Backtest**: `POST /api/replay` runs signal pipeline candle-by-candle (zero lookahead). See `backend/app/replay.py`.

## Extension Patterns

**Adding Signal Detector**: (1) Implement function returning list of `OutputSignal` in `backend/app/`. (2) Call in `AlertPoller.tick()` (~line 200 in `alert_poller.py`). (3) Add test in `tests/test_<detector>.py`. (4) If user-configurable, add toggle to `SetupsConfig` in `config.py`.

**Modifying Watchlist Schema**: (1) Edit `SymbolConfig` Pydantic model in `config.py`. (2) Add field validators if needed. (3) Update `data/watchlist.json` and `.env.example`. (4) Test: `pytest tests/test_config.py -v`.

**Poller State**: `PollerState` dataclass (`alert_poller.py` line 40+) tracked by `GET /api/poller/status`. Modes (run, pause_new, pause_all) mutable via `PUT /api/poller/mode`.

**Telegram**: `TelegramNotifier` sends formatted messages with retry. Alerts marked as notified in DB. Silent if token missing (alerts still persist). See `notifier.py`.

**Database**: Single `alerts` table, no migrations. For schema changes: export CSV → script → re-import, or manual SQLite migration.

## File Structure Reference

| Path | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, startup/shutdown, endpoints |
| `backend/app/alert_poller.py` | Background poller, state machine, suppression filters |
| `backend/app/openings.py` | Orchestrates signal pipeline (`build_openings()`) |
| `backend/app/level_events.py`, `setup_candles.py` | Signal detectors (break/retest/fakeout, setup candles) |
| `backend/app/levels.py`, `pivots.py`, `indicators.py` | Analysis modules (clustering, DI+/-, SMA/RSI/ATR) |
| `backend/app/config.py` | Pydantic models, watchlist loading, validation |
| `backend/app/storage.py` | SQLite CRUD, alert de-dup logic |
| `backend/app/ingest_service.py` | Binance REST bootstrap + WebSocket streams |
| `backend/tests/conftest.py` | Pytest fixtures, auto-disable ingestion |
| `frontend/src/pages/*.jsx` | Dashboard, Journal, Replay, OpsPage, etc. |

## Runbook Essentials

- **Health check**: `curl -fsS http://localhost/api/readyz`
- **Poller status**: `curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost/api/poller/status`
- **Pause alerts**: `curl -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"mode":"pause_new"}' http://localhost/api/poller/mode`
- **Export alerts**: `curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost/api/alerts/export.csv > alerts.csv`

See `DEPLOYMENT.md` and `runbook.md` for full ops details.
