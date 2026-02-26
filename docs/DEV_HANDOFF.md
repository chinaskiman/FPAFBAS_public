Developer Handoff — Binance USDT Perpetual Futures Alert Bot (Telegram + UI)
v1.0 | Date: 2026-02-03 | Alert-only, deterministic strategy checks (no auto-trading)

1) System Overview
Always-on service on a VPS that monitors Binance USDT perpetual futures. Signals are evaluated deterministically on candle close for 15m and 1h. Alerts are sent to Telegram and logged. A minimal web UI edits watchlist and levels overrides.
2) Architecture Diagram
                ┌──────────────────────────────┐
                │         Binance (Futures)    │
                │   WS: 15m/1h klines close    │
                │   REST: bootstrap 1w/1d/4h   │
                └──────────────┬───────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                         Data Layer                             │
│  - Candle cache per (symbol, tf)                                │
│  - Derived series: RSI, ATR(5), DI+/DI-, SMA(7/25/99), volume    │
└──────────────┬────────────────────────────────────────┬────────┘
               │                                        │
               ▼                                        ▼
┌──────────────────────────────┐           ┌──────────────────────────────┐
│      Levels Engine (S/R)      │           │       Strategy Engine        │
│  - pivots 2L/2R on 1w/1d/4h   │           │  - HWC bias (1w+1d)          │
│  - clustering tol%            │           │  - continuation/retest/...   │
│  - overrides: add/disable     │           │  - DI peak zones (Option 1)  │
└──────────────┬───────────────┘           └──────────────┬───────────────┘
               │                                          │
               └───────────────┬──────────────────────────┘
                               ▼
                    ┌───────────────────────┐
                    │   Alert Orchestrator   │
                    │  - cooldown / daily cap│
                    │  - format payload      │
                    └─────────┬─────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
      ┌──────────────────┐        ┌───────────────────────┐
      │ Telegram Notifier │        │ Storage (SQLite/JSON)  │
      │  sendMessage      │        │ alerts + audit trail   │
      └──────────────────┘        └───────────┬───────────┘
                                              │
                                              ▼
                                   ┌───────────────────────┐
                                   │        Web UI          │
                                   │ watchlist + levels +   │
                                   │ alerts log (read)      │
                                   └───────────────────────┘
3) Components & Responsibilities
•	Binance Ingest: Subscribe to 15m/1h kline close events (WebSocket). Bootstrap higher TF history (REST). Reconnect with backoff.
•	Candle Cache: In-memory ring buffer per (symbol, tf) storing OHLCV + timestamps. Persisting raw candles is optional.
•	Indicators: Compute RSI(14), ATR(5), SMA(7/25/99), DI+/DI-, ADX(14), volume stats. Calculations run after candle close.
•	Levels Engine: Auto S/R from 1W/1D/4H pivot highs/lows (2L/2R) + clustering. Apply overrides (add/pin, disable).
•	DI Peak Engine (Option 1): Build DI peak zones from DI pivot highs (2L/2R) + clustering; flag DI 'at peak' if within 3% of a zone.
•	Strategy Engine: Implements HWC bias filter + setup detection (Continuation/Retest/Fake-out/Setup candle). Outputs alert candidates.
•	Alert Orchestrator: Spam control (cooldown + daily cap). Formats Telegram message + structured JSON payload.
•	Notifier: Send Telegram alerts.
•	Storage: Log alerts to SQLite (recommended) for audit and UI history.
•	Web UI: CRUD for watchlist and level overrides; read alert history.
4) Deterministic Strategy Logic (Locked Rules)
Trend filter (HWC):
•	Compute Dow structure on 1W and 1D using pivot swings (2L/2R).
•	Bullish if latest swings show HH + HL. Bearish if LL + LH. Mixed/unclear => suppress all alerts.
•	Trade direction = HWC direction only.
Levels (S/R):
•	Detect pivot highs/lows on 1W/1D/4H using 2L/2R.
•	Cluster candidate prices within cluster_tol_pct (default 0.30%).
•	Keep top N levels (default 12) using TF weights W>D>4H and touch count scoring.
•	Apply overrides: add/pin levels always included; disable removes matching auto levels within tolerance.
Setups (evaluated on entry TF candle close):
•	Continuation (strong momentum only): candle closes beyond a level in HWC direction AND volume is highest of last 10 candles AND DI not at peak.
•	Retest: wick tags the level; pullback volume is declining; alert triggers on close back in trend direction.
•	Fake-out (within 10 candles): break against HWC direction; retest volume increasing (vol > prev AND vol > MA10); candle closes back inside => alert. Include SL note: beyond fake extreme + 0.15%.
•	Setup Candle (SMA7): SMA(7/25/99) present; wick >= 1.5× body (directional); SMA7 behind candle body; alert on close; SL other side of candle.
5) Data Contracts
watchlist.json example (dev contract):
{
  "symbols": [
    {
      "symbol": "BTCUSDT",
      "enabled": true,
      "entry_tfs": [
        "15m",
        "1h"
      ],
      "setups": {
        "continuation": true,
        "retest": true,
        "fakeout": true,
        "setup_candle": true
      },
      "levels": {
        "auto": true,
        "max_levels": 12,
        "cluster_tol_pct": 0.003,
        "overrides": {
          "add": [
            42000.0,
            43850.0
          ],
          "disable": [
            41520.0
          ]
        }
      }
    }
  ],
  "global": {
    "max_alerts_per_symbol_per_day": 6,
    "cooldown_minutes": 60
  }
}
Environment variables (.env):
•	TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
•	BINANCE_FAPI_REST=https://fapi.binance.com
•	BINANCE_FAPI_WS=wss://fstream.binance.com/ws
•	SQLITE_PATH=...
•	DI_PEAK_PROX_PCT=0.03, FAKEOUT_WINDOW_CANDLES=10
•	ALERT_COOLDOWN_MINUTES=60, MAX_ALERTS_PER_SYMBOL_PER_DAY=6
6) Web UI + API Endpoints
Minimal UI routes (server-rendered or SPA):
•	GET / : dashboard (enabled symbols + last alerts)
•	GET /watchlist : list symbols and toggles
•	GET /levels/{symbol} : manage pinned/disabled levels
•	GET /alerts : searchable alert log
Minimal API endpoints (JSON):
•	GET /api/alerts?limit=100 : recent alerts
•	GET /api/watchlist : fetch watchlist.json
•	PUT /api/watchlist : replace watchlist.json (validated)
•	POST /api/levels/{symbol}/add : add pinned level
•	POST /api/levels/{symbol}/disable : disable level
•	POST /api/levels/{symbol}/enable : re-enable disabled level
7) Alert Payload & Telegram Message Format
Telegram message fields:
•	symbol | tf | setup | direction
•	price close
•	level (if applicable)
•	why (volume spike / DI pass / wick tag / fake-out conditions)
•	TradingView link (optional)
•	Notes (SL reference reminders)
Structured payload (stored in DB) should include:
•	ts (unix seconds), symbol, tf, setup, direction, level, close_price
•	details: { why, vol_stat, di_stat, window_remaining, etc. }
•	links: { tradingview }
•	version string for strategy rules
8) Spam Control & Safety
•	Cooldown: suppress new alerts for (symbol, tf) for N minutes (default 60).
•	Daily cap: max alerts per symbol per day (default 6).
•	No trading keys. Alert-only.
•	Optional: Basic auth on UI if exposed to internet.
9) Deployment (VPS)
•	Run as a single service (Docker recommended) with restart policy.
•	Persist data volume for watchlist.json + SQLite DB.
•	Health endpoint recommended: GET /health returning ok + WS status.
•	Logging: structured logs (timestamp, symbol, tf, setup, errors).
10) Testing Checklist (Quick)
•	Replay historical klines to validate each setup triggers at correct candle close.
•	Validate pivot detection and clustering with unit tests.
•	Disconnect WS to ensure auto reconnect.
•	Edit levels in UI and confirm they affect alerts.
