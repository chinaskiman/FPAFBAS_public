PRD — Binance USDT Perpetual Futures Alert Bot (Telegram + UI)
v1.0 | Date: 2026-02-03 | Scope: Alert-only (no auto-trading)

1. Overview
Build an always-on alert system that monitors Binance USDT perpetual futures 24/7, detects the user's predefined crypto trading setups on candle close (15m and 1h), and notifies via Telegram. A simple web UI allows watchlist and S/R level management, plus an alert history view. The system must be deterministic and match the agreed rulebook.
2. Goals
•	Detect the agreed setups (Continuation, Retest, Fake-out, Setup Candle) reliably on candle close.
•	Auto-generate Support/Resistance (S/R) from higher timeframes and allow manual overrides.
•	Provide Telegram alerts with consistent, standardized context.
•	Provide a minimal UI to manage symbols/levels and view alerts.
•	Run continuously on a VPS with restart-on-failure.
3. Non-Goals
•	No order placement / auto-trading.
•	No enforcement of daily PnL caps or exposure caps using account data (no private keys, no position tracking).
•	No discretionary/human-drawn chart interpretation beyond the deterministic rules.
4. Target User
A discretionary crypto futures trader who wants 24/7 monitoring and timely alerts, while keeping final execution manual.
5. Key Decisions (Locked)
Market/Data:
•	Exchange: Binance
•	Instrument type: USDT perpetual futures

Timeframes:
•	HWC bias from 1W + 1D
•	MWC context from 1D + 4H (context only)
•	Entry timeframes: 15m and/or 1h; never below 15m

Levels:
•	Auto S/R from 1W/1D/4H pivots (2L/2R) + clustering
•	Editable overrides: add/pin levels, disable auto levels

Setup rules:
•	Break confirmation: any candle close beyond level
•	Volume spike: break candle volume is highest of last 10 candles (entry TF)
•	Continuation: only if volume spike + DI not at peak; otherwise wait retest/setup candle
•	Retest: wick touch is enough; declining pullback volume; entry on close back in direction
•	Fake-out: window = 10 candles; increasing volume rule = (vol > prev) AND (vol > MA10); entry on close back inside; SL beyond fake extreme + 0.15%
•	DI peak: Option 1 (DI S/R zones via DI pivots + clustering) with 3% proximity threshold
•	Notifications: Telegram
•	Hosting: VPS
6. Definitions
•	Pivot (2L/2R): pivot high is higher than previous 2 highs and >= next 2 highs; pivot low is lower than previous 2 lows and <= next 2 lows.
•	HWC direction: computed from Weekly + Daily Dow structure using recent pivots (HH/HL bullish, LL/LH bearish). Mixed/unclear => suppress alerts.
•	Cluster tolerance: levels within X% are grouped; cluster center = mean price.
•	Buffer: 0.15% beyond swing HL/LH (used for stop references in alerts).
7. Data Sources & Ingestion
•	Candles: 1w, 1d, 4h, 1h, 15m.
•	Recommended ingestion:
  - WebSocket kline streams for 15m and 1h to react immediately on candle close.
  - REST bootstrap and periodic refresh for higher TF history (1w/1d/4h).
•	Must handle reconnects and short outages gracefully.
8. Functional Requirements
8.1 Watchlist & Config
•	Configuration stored as JSON (watchlist.json) with per-symbol:
  - enabled flag
  - entry_tfs (15m, 1h)
  - enabled setups (continuation/retest/fakeout/setup candle)
  - level settings: auto on/off, max_levels, cluster_tol_pct, overrides.add, overrides.disable

8.2 Auto S/R Engine (Editable)
•	Generate candidate levels from 1W/1D/4H pivot highs/lows (2L/2R).
•	Cluster candidates using cluster_tol_pct (default 0.30%).
•	Keep top N levels per symbol (default N=12) using TF weights W>D>4H and a touch-count score.
•	Apply overrides:
  - Add/pin levels: always included
  - Disable levels: remove matching auto levels within tolerance

8.3 DI Peak Filter (Option 1)
•	Compute DI+/DI-.
•	Find DI pivot highs (2L/2R), cluster into DI peak zones.
•	'DI at peak' if current DI within 3% of a DI peak zone.
•	For LONG check DI+; for SHORT check DI-.

8.4 Setup Detection (entry TF on candle close)
•	Continuation:
  - HWC aligned
  - Close breaks level
  - Break candle volume is highest of last 10
  - DI not at peak
•	Retest:
  - Wick tags level
  - Pullback volume declining
  - Alert on close back in direction
•	Fake-out:
  - Break against HWC
  - Within 10 candles: retest volume increasing (vol>prev and vol>MA10)
  - Close back inside => alert
  - Include SL note: beyond fake extreme + 0.15%
•	Setup candle:
  - SMA 7/25/99
  - Wick >= 1.5× body (directional)
  - SMA7 behind candle body (per agreed definition)
  - Alert on close; include SL note: other side of candle

8.5 Telegram Alerts
•	Standard message fields:
  - symbol, timeframe, setup type, direction
  - trigger level and close price
  - 'why' fields (volume spike, DI peak pass, etc.)
  - TradingView link

8.6 Web UI (Minimal)
•	Dashboard: enabled symbols + last alerts.
•	Watchlist: enable/disable symbols; choose entry TFs; toggle setups.
•	Levels editor: add/pin; disable; view current overrides.
•	Alerts log: filter/search by symbol/setup/TF/date.
9. Reliability, Performance, and Security
Reliability
•	Automatic reconnect on WebSocket disconnect.
•	Restart on crash (process manager / Docker).
•	Persist alert history to SQLite (or equivalent) to survive restarts.

Performance
•	Support at least 50 symbols × 2 entry TFs on a small VPS.
•	Prefer WS-first ingestion to avoid REST rate limits.

Security
•	No trading keys required.
•	Telegram token and chat_id stored in environment variables (.env), not in the repo.
•	Optional: basic auth for UI if exposed publicly.
10. Acceptance Criteria (Must Pass)
Core signal correctness
1) Given a fixed watchlist.json and the same historical candle stream, alerts are deterministic.
2) Continuation alert triggers only when: break-close + vol highest(10) + DI not at peak + HWC aligned.
3) Retest alert requires wick tag + declining volume + close back in direction.
4) Fake-out alert triggers only within 10 candles, with increasing volume condition, and closes back inside.
5) Setup candle alert triggers on candle close when wick/body and SMA7-behind rules match.

Ops
6) The bot resumes operation after a WebSocket disconnect (auto-reconnect).
7) Alert history survives restart (storage persistence).
8) UI edits to pinned/disabled levels are reflected in subsequent alerts (after recompute/restart as designed).
9) Telegram messages send successfully and include required fields.
11. Edge Cases & Handling
•	Mixed/unclear HWC structure: suppress all alerts.
•	Insufficient candles for pivots/indicators: suppress alerts for that symbol/TF until warm.
•	Whipsaw around a level: enforce per-symbol cooldown + max alerts/day (spam control).
•	Multiple levels broken in one candle: allow multiple alerts, but cap per symbol/day.
•	Restart behavior: on restart, bootstrap history, recompute levels, then continue live scanning.
•	Binance maintenance/outage: bot should retry with backoff and recover automatically.
12. Test Plan (Concrete Scenarios)
Unit tests
•	Pivot detection (2L/2R) on synthetic series.
•	Level clustering and override application.
•	Volume highest(10) logic.
•	DI peak zone construction + proximity check.
•	Setup candle wick/body + SMA7-behind logic.

Integration tests
•	Replay historical klines for 15m/1h and verify alert timestamps.
•	Simulate WS disconnect (force close) and confirm reconnect.
•	UI edits: add/disable levels and verify effective levels update.

User acceptance
•	Provide 5–10 historical examples per setup; bot must match expected triggers on candle close using the same levels.
