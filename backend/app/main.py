from __future__ import annotations

import csv
import io
import json
import logging
import os
import tempfile
import time

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .binance_client import BinanceRestClient
from .config import (
    get_data_dir,
    get_poller_start_paused,
    get_poll_seconds,
    get_watchlist_path,
    load_watchlist,
    save_watchlist,
)
from .ingest_service import IngestService
from .di_peak import (
    DI_PEAK_MIN_DI,
    DI_PEAK_RATIO_THRESHOLD,
    DI_PEAK_SUSTAIN_BARS,
    DI_PEAK_WINDOW_DEFAULT,
    compute_di_peak_flags,
)
from .hwc import compute_hwc_bias
from .volume_filters import compute_pullback_vol_decline, compute_vol_metrics
from .rsi_filters import atr_multiplier_from_rsi, rsi_distance_from_50
from .level_events import detect_level_events
from .setup_candles import detect_setup_candles
from .indicators import sma
from .openings import build_openings
from .levels import HTF_TFS, apply_overrides, build_levels_detailed, compute_levels
from .ops import require_admin
from .poller_lock import PollerFileLock
from .journal import JournalStore
from .storage import alerts_stats, check_db, get_alert, init_db, list_alerts
from .pivots import find_pivot_highs, find_pivot_lows
from .quality_controls import score_signal
from .alert_poller import AlertPoller
from .notifier import TelegramNotifier
from .quality_controls import QualitySettings
from .replay import replay_run, replay_summary


load_dotenv()


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Futures Alert Bot")

cors_origins_env = os.getenv("CORS_ORIGINS")
if cors_origins_env:
    cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    cors_origins = ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    journal = JournalStore()
    journal.init_db()
    app.state.journal = journal
    notifier = TelegramNotifier()
    app.state.notifier = notifier
    poll_seconds = get_poll_seconds()
    start_paused = get_poller_start_paused()
    lock_path = os.getenv("POLLER_LOCK_PATH", str(get_data_dir() / "poller.lock"))
    poller_lock = PollerFileLock(lock_path)
    lock_acquired = poller_lock.acquire(non_blocking=True)
    app.state.poller_lock = poller_lock
    try:
        if os.getenv("DISABLE_INGESTION") == "1":
            logger.info("Ingestion disabled via DISABLE_INGESTION=1")
            app.state.ingest = None
            poller = AlertPoller(
                ingest=None,
                notifier=notifier,
                journal=journal,
                poll_seconds=poll_seconds,
                start_paused=start_paused,
            )
            poller.state.lock_acquired = lock_acquired
            poller.state.lock_path = str(lock_path)
            app.state.poller = poller
            return
        config = load_watchlist()
        logger.info("Watchlist validated at %s", get_watchlist_path())
        enabled_symbols = [symbol.symbol for symbol in config.symbols if symbol.enabled]
        cache_maxlen = int(os.getenv("CACHE_MAXLEN", "1200"))
        ingest = IngestService(rest_client=BinanceRestClient(), cache_maxlen=cache_maxlen, journal_store=journal)
        ingest.bootstrap(enabled_symbols)
        ingest.start_streaming(enabled_symbols)
        app.state.ingest = ingest
        poller = AlertPoller(
            ingest=ingest,
            notifier=notifier,
            journal=journal,
            poll_seconds=poll_seconds,
            start_paused=start_paused,
        )
        poller.state.lock_acquired = lock_acquired
        poller.state.lock_path = str(lock_path)
        if lock_acquired:
            poller.start()
        else:
            logger.warning("Poller lock not acquired at %s; poller not started", lock_path)
        app.state.poller = poller
    except Exception as exc:  # noqa: BLE001 - report config errors clearly
        logger.error("Watchlist validation failed: %s", exc)
        raise


@app.on_event("shutdown")
def on_shutdown() -> None:
    ingest = getattr(app.state, "ingest", None)
    poller = getattr(app.state, "poller", None)
    poller_lock = getattr(app.state, "poller_lock", None)
    if poller:
        poller.stop()
    if ingest:
        ingest.stop()
    if poller_lock:
        poller_lock.release()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "ts": int(time.time() * 1000)}


def _check_watchlist_dir() -> bool:
    path = get_watchlist_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=True, dir=path.parent) as tmp:
            tmp.write("ok")
        return True
    except Exception:  # noqa: BLE001
        return False


@app.get("/readyz")
def readyz() -> dict:
    db_ok = check_db()
    watchlist_ok = _check_watchlist_dir()
    poller = getattr(app.state, "poller", None)
    lock_acquired = False
    poller_ok = False
    if poller:
        lock_acquired = bool(getattr(poller.state, "lock_acquired", False))
        if not lock_acquired:
            poller_ok = True
        else:
            poller_ok = bool(poller.state.is_running) or getattr(poller, "ingest", None) is None
    ok = db_ok and watchlist_ok and poller_ok
    return {
        "ok": ok,
        "db_ok": db_ok,
        "watchlist_ok": watchlist_ok,
        "poller_ok": poller_ok,
        "lock_acquired": lock_acquired,
        "ts": int(time.time() * 1000),
    }


@app.get("/api/watchlist")
def api_watchlist() -> dict:
    config = load_watchlist()
    return config.model_dump(by_alias=True)

@app.put("/api/watchlist")
async def api_watchlist_put(request: Request) -> dict:
    payload = await request.json()
    try:
        config = save_watchlist(payload)
    except ValidationError as exc:
        details = "; ".join(
            [".".join(map(str, error.get("loc", []))) + f": {error.get('msg')}" for error in exc.errors()]
        )
        raise HTTPException(status_code=400, detail=details or "Invalid watchlist payload") from exc
    return {"status": "ok", "watchlist": config.model_dump(by_alias=True)}


@app.get("/api/alerts")
def api_alerts(
    symbol: str | None = None,
    tf: str | None = None,
    type: str | None = None,  # noqa: A002
    direction: str | None = None,
    notified: int | None = None,
    since_ms: int | None = None,
    until_ms: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    items, total = list_alerts(
        limit=limit,
        offset=offset,
        symbol=symbol,
        tf=tf,
        alert_type=type,
        direction=direction,
        notified=notified,
        since_ms=since_ms,
        until_ms=until_ms,
        include_payload=True,
    )
    output_items = []
    for item in items:
        payload = item.pop("payload", None)
        if payload:
            score, badges, _ = score_signal(payload)
            item["score"] = score
            item["vol_ok"] = badges.get("vol_ok")
            item["di_ok"] = badges.get("di_ok")
        output_items.append(item)
    return {"items": output_items, "limit": limit, "offset": offset, "total": total}


@app.get("/api/alerts/export.csv", dependencies=[Depends(require_admin)])
def api_alerts_export(
    symbol: str | None = None,
    tf: str | None = None,
    type: str | None = None,  # noqa: A002
    direction: str | None = None,
    notified: int | None = None,
    since_ms: int | None = None,
    until_ms: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Response:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    items, _total = list_alerts(
        limit=limit,
        offset=offset,
        symbol=symbol,
        tf=tf,
        alert_type=type,
        direction=direction,
        notified=notified,
        since_ms=since_ms,
        until_ms=until_ms,
        include_payload=True,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "symbol",
            "tf",
            "type",
            "direction",
            "level",
            "time",
            "entry",
            "sl",
            "sl_reason",
            "hwc_bias",
            "notified",
            "notify_error",
            "score",
            "vol_ok",
            "di_ok",
        ]
    )
    for item in items:
        payload = item.get("payload")
        score = None
        vol_ok = None
        di_ok = None
        if payload:
            score, badges, _ = score_signal(payload)
            vol_ok = badges.get("vol_ok")
            di_ok = badges.get("di_ok")
        writer.writerow(
            [
                item.get("id"),
                item.get("created_at"),
                item.get("symbol"),
                item.get("tf"),
                item.get("type"),
                item.get("direction"),
                item.get("level"),
                item.get("time"),
                item.get("entry"),
                item.get("sl"),
                item.get("sl_reason"),
                item.get("hwc_bias"),
                item.get("notified"),
                item.get("notify_error"),
                score,
                vol_ok,
                di_ok,
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alerts.csv"},
    )


@app.get("/api/alerts/stats")
def api_alerts_stats(since_ms: int | None = None) -> dict:
    stats = alerts_stats(since_ms=since_ms)
    payload = {"since_ms": since_ms, **stats}
    if not stats.get("by_reason"):
        payload.pop("by_reason", None)
    return payload


@app.get("/api/alerts/{alert_id}")
def api_alert(alert_id: int) -> dict:
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@app.get("/api/journal/signals")
def api_journal_signals(
    symbol: str | None = None,
    timeframe: str | None = None,
    from_ms: int | None = None,
    to_ms: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    journal = getattr(app.state, "journal", None)
    if journal is None:
        raise HTTPException(status_code=503, detail="Journal not initialized")
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    items = journal.list_signals(
        symbol=symbol,
        timeframe=timeframe,
        from_ms=from_ms,
        to_ms=to_ms,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "limit": limit, "offset": offset}


@app.get("/api/journal/signals/{signal_id}")
def api_journal_signal(signal_id: str) -> dict:
    journal = getattr(app.state, "journal", None)
    if journal is None:
        raise HTTPException(status_code=503, detail="Journal not initialized")
    record = journal.get_signal(signal_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return record


@app.get("/api/journal/export.jsonl", dependencies=[Depends(require_admin)])
def api_journal_export(
    symbol: str | None = None,
    timeframe: str | None = None,
    from_ms: int | None = None,
    to_ms: int | None = None,
) -> Response:
    journal = getattr(app.state, "journal", None)
    if journal is None:
        raise HTTPException(status_code=503, detail="Journal not initialized")

    def _iter_lines():
        for record in journal.iter_signals(symbol=symbol, timeframe=timeframe, from_ms=from_ms, to_ms=to_ms):
            yield json.dumps(record) + "\n"

    return StreamingResponse(_iter_lines(), media_type="application/x-ndjson")


@app.get("/api/poller/status", dependencies=[Depends(require_admin)])
def api_poller_status() -> dict:
    poller = getattr(app.state, "poller", None)
    if poller is None:
        return {
            "is_running": False,
            "mode": "pause_all",
            "started_at": None,
            "last_tick_at": None,
            "last_scan_at": None,
            "last_scan_count": 0,
            "last_new_alerts": 0,
            "last_suppressed_new_alerts": 0,
            "last_error": "Poller not initialized",
        }
    return poller.state.to_dict()


@app.post("/api/poller/pause", dependencies=[Depends(require_admin)])
def api_poller_pause() -> dict:
    poller = getattr(app.state, "poller", None)
    if poller is None:
        return {
            "is_running": False,
            "mode": "pause_all",
            "started_at": None,
            "last_tick_at": None,
            "last_scan_at": None,
            "last_scan_count": 0,
            "last_new_alerts": 0,
            "last_suppressed_new_alerts": 0,
            "last_error": "Poller not initialized",
        }
    poller.pause()
    return poller.state.to_dict()


@app.post("/api/poller/resume", dependencies=[Depends(require_admin)])
def api_poller_resume() -> dict:
    poller = getattr(app.state, "poller", None)
    if poller is None:
        return {
            "is_running": False,
            "mode": "run",
            "started_at": None,
            "last_tick_at": None,
            "last_scan_at": None,
            "last_scan_count": 0,
            "last_new_alerts": 0,
            "last_suppressed_new_alerts": 0,
            "last_error": "Poller not initialized",
        }
    poller.resume()
    return poller.state.to_dict()


@app.post("/api/poller/mode", dependencies=[Depends(require_admin)])
async def api_poller_mode(request: Request) -> dict:
    poller = getattr(app.state, "poller", None)
    if poller is None:
        raise HTTPException(status_code=503, detail="Poller not initialized")
    payload = await request.json()
    mode = payload.get("mode") if isinstance(payload, dict) else None
    if mode not in {"run", "pause_new", "pause_all"}:
        raise HTTPException(status_code=400, detail="Invalid mode")
    poller.set_mode(mode)
    return poller.state.to_dict()


@app.post("/api/telegram/test", dependencies=[Depends(require_admin)])
async def api_telegram_test(request: Request) -> dict:
    payload = {}
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    text = payload.get("text") if isinstance(payload, dict) else None
    if not text:
        text = "Test alert from Futures Alert Bot"
    notifier = getattr(app.state, "notifier", TelegramNotifier())
    ok, error = notifier.send_telegram(text)
    return {"ok": ok, "error": error, "sent_text": text}


@app.get("/api/quality/settings")
def api_quality_settings() -> dict:
    config = load_watchlist()
    return config.quality.model_dump()


@app.put("/api/quality/settings")
async def api_quality_settings_put(request: Request) -> dict:
    payload = await request.json()
    quality = QualitySettings.model_validate(payload)
    config = load_watchlist()
    data = config.model_dump(by_alias=True)
    data["quality"] = quality.model_dump()
    updated = save_watchlist(data)
    return {"status": "ok", "quality": updated.quality.model_dump()}


@app.get("/api/quality/suppressed")
def api_quality_suppressed(limit: int = 50) -> dict:
    poller = getattr(app.state, "poller", None)
    if poller is None:
        return {"items": []}
    return {"items": poller.list_suppressed(limit=limit)}


@app.get("/api/symbols")
def api_symbols() -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        return {"symbols": []}
    return {"symbols": ingest.list_symbols()}


@app.get("/api/candles/{symbol}/{tf}")
def api_candles(symbol: str, tf: str, limit: int = 500) -> list:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    cache = ingest.get_cache(symbol, tf)
    if cache is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)
    payload = []
    for candle in candles:
        payload.append(
            {
                "time": candle.close_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
        )
    return payload


def _series_points(times: list[int], values: list[float | None]) -> list[dict]:
    points: list[dict] = []
    for idx, value in enumerate(values):
        if value is None:
            continue
        points.append({"time": times[idx], "value": value})
    return points


def _candles_payload(candles: list) -> tuple[list[dict], list[int]]:
    payload = []
    times = []
    for candle in candles:
        ts = candle.close_time // 1000
        times.append(ts)
        payload.append(
            {
                "time": ts,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
        )
    return payload, times


@app.get("/api/chart_bundle/{symbol}/{tf}")
def api_chart_bundle(symbol: str, tf: str, limit: int = 500) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    cache = ingest.get_cache(symbol, tf)
    if cache is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)
    candle_payload, times = _candles_payload(candles)

    indicators = ingest.list_indicators(symbol, tf, limit=limit) or {}
    sma7 = _series_points(times, indicators.get("sma7", []))
    rsi14 = _series_points(times, indicators.get("rsi14", []))
    di_plus = _series_points(times, indicators.get("di_plus", []))
    di_minus = _series_points(times, indicators.get("di_minus", []))
    adx14 = _series_points(times, indicators.get("adx14", []))

    volumes = [candle.volume for candle in candles]
    vol_ma5 = sma(volumes, 5)
    vol_ma10 = indicators.get("vol_ma10", [])
    volume_series = _series_points(times, volumes)
    vol_ma5_series = _series_points(times, vol_ma5)
    vol_ma10_series = _series_points(times, vol_ma10)

    config = load_watchlist()
    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol.upper()),
        None,
    )
    if symbol_config is None:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")

    candles_by_tf = {}
    for htf in HTF_TFS:
        htf_cache = ingest.get_cache(symbol, htf)
        candles_by_tf[htf] = htf_cache.list_all() if htf_cache else []

    auto_levels, _selected, clusters, meta = compute_levels(
        candles_by_tf,
        symbol_config.levels.cluster_tol_pct,
        symbol_config.levels.max_levels,
    )
    tol_pct_used = meta.get("tol_pct_used", symbol_config.levels.cluster_tol_pct)
    overrides = symbol_config.levels.overrides
    merged = apply_overrides(auto_levels, overrides.add, overrides.disable, tol_pct_used)
    final_levels_detailed = build_levels_detailed(
        merged["final_levels"],
        clusters,
        meta.get("last_close_used"),
        tol_pct_used,
    )

    events = detect_level_events(candles, merged["final_levels"])
    setup_items = detect_setup_candles(candles, indicators.get("sma7", []), events, sl_buffer_pct=0.0015)
    try:
        openings = build_openings(ingest, config, symbol, tf, limit=limit)
    except Exception:
        openings = {"signals": []}

    markers: list[dict] = []
    for event in events:
        if event.get("last_break"):
            idx = event["last_break"]["index"]
            if 0 <= idx < len(candles):
                markers.append(
                    {
                        "type": "break",
                        "direction": event.get("direction"),
                        "level": event.get("level"),
                        "time": candles[idx].close_time // 1000,
                        "candle": {
                            "time": candles[idx].close_time // 1000,
                            "open": candles[idx].open,
                            "high": candles[idx].high,
                            "low": candles[idx].low,
                            "close": candles[idx].close,
                            "volume": candles[idx].volume,
                        },
                    }
                )
        if event.get("retest_index") is not None:
            idx = event["retest_index"]
            if 0 <= idx < len(candles):
                markers.append(
                    {
                        "type": "retest",
                        "direction": event.get("direction"),
                        "level": event.get("level"),
                        "time": candles[idx].close_time // 1000,
                        "candle": {
                            "time": candles[idx].close_time // 1000,
                            "open": candles[idx].open,
                            "high": candles[idx].high,
                            "low": candles[idx].low,
                            "close": candles[idx].close,
                            "volume": candles[idx].volume,
                        },
                    }
                )
        if event.get("last_fakeout"):
            idx = event["last_fakeout"]["index"]
            if 0 <= idx < len(candles):
                markers.append(
                    {
                        "type": "fakeout",
                        "direction": event.get("direction"),
                        "level": event.get("level"),
                        "time": candles[idx].close_time // 1000,
                        "candle": {
                            "time": candles[idx].close_time // 1000,
                            "open": candles[idx].open,
                            "high": candles[idx].high,
                            "low": candles[idx].low,
                            "close": candles[idx].close,
                            "volume": candles[idx].volume,
                        },
                    }
                )

    for item in setup_items:
        idx = item.get("setup_index")
        if idx is None or not (0 <= idx < len(candles)):
            continue
        markers.append(
            {
                "type": "setup",
                "direction": item.get("direction"),
                "level": item.get("level"),
                "time": candles[idx].close_time // 1000,
                "candle": {
                    "time": candles[idx].close_time // 1000,
                    "open": candles[idx].open,
                    "high": candles[idx].high,
                    "low": candles[idx].low,
                    "close": candles[idx].close,
                    "volume": candles[idx].volume,
                },
            }
        )

    for signal in openings.get("signals", []):
        candle = signal.get("candle") or {}
        close_time = candle.get("close_time")
        if close_time is None:
            close_time = signal.get("time")
        if close_time is None:
            continue
        markers.append(
            {
                "type": "opening",
                "direction": signal.get("direction"),
                "level": signal.get("level"),
                "time": close_time // 1000,
                "candle": {
                    "time": close_time // 1000,
                    "open": candle.get("open"),
                    "high": candle.get("high"),
                    "low": candle.get("low"),
                    "close": candle.get("close"),
                    "volume": candle.get("volume"),
                },
            }
        )

    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "candles": candle_payload,
        "sma7": sma7,
        "rsi14": rsi14,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "adx14": adx14,
        "volume": volume_series,
        "vol_ma5": vol_ma5_series,
        "vol_ma10": vol_ma10_series,
        "levels": final_levels_detailed,
        "markers": markers,
    }


@app.get("/api/indicators/{symbol}/{tf}")
def api_indicators(symbol: str, tf: str, limit: int = 200) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    payload = ingest.list_indicators(symbol, tf, limit)
    if payload is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    return payload


@app.get("/api/levels/{symbol}")
def api_levels(symbol: str, debug: int = 0) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    config = load_watchlist()
    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol.upper()),
        None,
    )
    if symbol_config is None:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    candles_by_tf = {}
    for tf in HTF_TFS:
        cache = ingest.get_cache(symbol, tf)
        candles_by_tf[tf] = cache.list_all() if cache else []

    auto_levels, _selected, clusters, meta = compute_levels(
        candles_by_tf,
        symbol_config.levels.cluster_tol_pct,
        symbol_config.levels.max_levels,
    )
    last_close_used = meta.get("last_close_used")
    below_count = meta.get("below_count", 0)
    above_count = meta.get("above_count", 0)
    tol_pct_used = meta.get("tol_pct_used", symbol_config.levels.cluster_tol_pct)
    overrides = symbol_config.levels.overrides
    merged = apply_overrides(auto_levels, overrides.add, overrides.disable, tol_pct_used)
    final_levels_detailed = build_levels_detailed(
        merged["final_levels"],
        clusters,
        last_close_used,
        tol_pct_used,
    )
    payload = {
        "symbol": symbol.upper(),
        "cluster_tol_pct": symbol_config.levels.cluster_tol_pct,
        "tol_pct_used": tol_pct_used,
        "max_levels": symbol_config.levels.max_levels,
        "last_close_used": last_close_used,
        "dense_count_near_price": meta.get("dense_count_near_price"),
        "merge_triggered": meta.get("merge_triggered"),
        "merge_tol_pct_used": meta.get("merge_tol_pct_used"),
        "forced_count": meta.get("forced_count"),
        "forced_centers": meta.get("forced_centers"),
        "below_count": below_count,
        "above_count": above_count,
        "auto_levels": auto_levels,
        "pinned_levels": merged["pinned_levels"],
        "disabled_levels": merged["disabled_levels"],
        "final_levels": merged["final_levels"],
        "final_levels_detailed": final_levels_detailed,
    }
    if debug:
        payload["atr5_last_used"] = meta.get("atr5_last_used")
        payload["atr_pct"] = meta.get("atr_pct")
        payload["tol_pct_raw"] = meta.get("tol_pct_raw")
        clusters_debug = []
        for cluster in sorted(
            clusters,
            key=lambda item: (-item.get("strength", 0.0), -item.get("last_touch_index", 0), item["center"]),
        ):
            clusters_debug.append(
                {
                    "center": cluster.get("center"),
                    "touches": cluster.get("touches"),
                    "strength": cluster.get("strength"),
                    "rank_score": cluster.get("rank_score"),
                    "last_touch_index": cluster.get("last_touch_index"),
                    "rejections": cluster.get("rejections"),
                    "last_rejection_index": cluster.get("last_rejection_index"),
                    "flips": cluster.get("flips"),
                    "last_flip_index": cluster.get("last_flip_index"),
                    "score_tf_used": cluster.get("score_tf_used"),
                }
            )
        payload["clusters_debug"] = clusters_debug
    return payload


@app.get("/api/debug/levels/{symbol}")
def api_debug_levels(symbol: str) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    config = load_watchlist()
    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol.upper()),
        None,
    )
    if symbol_config is None:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    candles_by_tf = {}
    for tf in HTF_TFS:
        cache = ingest.get_cache(symbol, tf)
        candles_by_tf[tf] = cache.list_all() if cache else []

    _, selected, clusters, _meta = compute_levels(
        candles_by_tf,
        symbol_config.levels.cluster_tol_pct,
        symbol_config.levels.max_levels,
    )
    return {
        "symbol": symbol.upper(),
        "clusters": clusters,
        "selected": selected,
    }


@app.get("/api/hwc/{symbol}")
def api_hwc(symbol: str) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    weekly_cache = ingest.get_cache(symbol, "1w")
    daily_cache = ingest.get_cache(symbol, "1d")
    if weekly_cache is None or daily_cache is None:
        raise HTTPException(status_code=404, detail="Missing weekly or daily cache")
    hwc = compute_hwc_bias(weekly_cache.list_all(), daily_cache.list_all())
    return {"symbol": symbol.upper(), **hwc}


@app.get("/api/di_peak/{symbol}/{tf}")
def api_di_peak(
    symbol: str,
    tf: str,
    window: int = DI_PEAK_WINDOW_DEFAULT,
    ratio_threshold: float = DI_PEAK_RATIO_THRESHOLD,
    min_di: float = DI_PEAK_MIN_DI,
    sustain: int = DI_PEAK_SUSTAIN_BARS,
) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    data = ingest.list_indicators(symbol, tf, limit=max(window, 1))
    if data is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    di_plus = compute_di_peak_flags(
        data.get("di_plus", []),
        window=window,
        ratio_threshold=ratio_threshold,
        min_di=min_di,
        sustain_bars=sustain,
    )
    di_minus = compute_di_peak_flags(
        data.get("di_minus", []),
        window=window,
        ratio_threshold=ratio_threshold,
        min_di=min_di,
        sustain_bars=sustain,
    )
    adx_series = data.get("adx14", [])
    adx_last = adx_series[-1] if adx_series else None
    candles = data.get("candles", [])
    timestamp = candles[-1]["close_time"] if candles else None
    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "window": window,
        "ratio_threshold": ratio_threshold,
        "min_di": min_di,
        "sustain_bars": sustain,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "not_at_peak_long": not di_minus["is_peak"],
        "not_at_peak_short": not di_plus["is_peak"],
        "adx14_last": adx_last,
        "timestamp": timestamp,
    }


@app.get("/api/volume/{symbol}/{tf}")
def api_volume(symbol: str, tf: str, k: int = 3) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    data = ingest.list_indicators(symbol, tf, limit=max(k, 10, 6))
    if data is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = data.get("candles", [])
    volumes = [item["volume"] for item in candles]
    metrics = compute_vol_metrics(volumes, window_ma=10, window_ma5=5)
    pullback = compute_pullback_vol_decline(volumes, k=k)
    timestamp = candles[-1]["close_time"] if candles else None
    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "vol_last": metrics["vol_last"],
        "vol_ma10_last": metrics["vol_ma10_last"],
        "vol_ratio": metrics["vol_ratio"],
        "vol_ma5_last": metrics["vol_ma5_last"],
        "vol_ma5_slope_pct": metrics["vol_ma5_slope_pct"],
        "vol_ma5_slope_ok": metrics["vol_ma5_slope_ok"],
        "pullback_vol_decline": pullback,
        "k": k,
        "timestamp": timestamp,
    }


@app.get("/api/rsi/{symbol}/{tf}")
def api_rsi(symbol: str, tf: str) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    data = ingest.list_indicators(symbol, tf, limit=20)
    if data is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    rsi_series = data.get("rsi14", [])
    atr_series = data.get("atr5", [])
    rsi_last = rsi_series[-1] if rsi_series else None
    atr_last = atr_series[-1] if atr_series else None
    candles = data.get("candles", [])
    timestamp = candles[-1]["close_time"] if candles else None

    rsi_distance = rsi_distance_from_50(rsi_last) if rsi_last is not None else None
    atr_mult_raw = None
    atr_mult = None
    if rsi_last is not None:
        mult = atr_multiplier_from_rsi(rsi_last)
        atr_mult_raw = mult["raw"]
        atr_mult = mult["clamped"]
    atr_stop_distance = atr_last * atr_mult if atr_last is not None and atr_mult is not None else None

    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "rsi14_last": rsi_last,
        "rsi_distance": rsi_distance,
        "atr5_last": atr_last,
        "atr_mult_raw": atr_mult_raw,
        "atr_mult": atr_mult,
        "atr_stop_distance": atr_stop_distance,
        "timestamp": timestamp,
    }


@app.get("/api/level_events/{symbol}/{tf}")
def api_level_events(
    symbol: str,
    tf: str,
    limit: int = 300,
    max_retest_bars: int = 20,
    max_fakeout_bars: int = 10,
) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    config = load_watchlist()
    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol.upper()),
        None,
    )
    if symbol_config is None:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    cache = ingest.get_cache(symbol, tf)
    if cache is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)

    candles_by_tf = {}
    for htf in HTF_TFS:
        htf_cache = ingest.get_cache(symbol, htf)
        candles_by_tf[htf] = htf_cache.list_all() if htf_cache else []
    auto_levels, _selected, _clusters, meta = compute_levels(
        candles_by_tf,
        symbol_config.levels.cluster_tol_pct,
        symbol_config.levels.max_levels,
    )
    tol_pct_used = meta.get("tol_pct_used", symbol_config.levels.cluster_tol_pct)
    overrides = symbol_config.levels.overrides
    merged = apply_overrides(auto_levels, overrides.add, overrides.disable, tol_pct_used)
    final_levels = merged["final_levels"]

    events = detect_level_events(
        candles,
        final_levels,
        max_retest_bars=max_retest_bars,
        max_fakeout_bars=max_fakeout_bars,
    )
    timestamp = candles[-1].close_time if candles else None
    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "limit": limit,
        "max_retest_bars": max_retest_bars,
        "max_fakeout_bars": max_fakeout_bars,
        "levels": final_levels,
        "events": events,
        "timestamp": timestamp,
    }


@app.get("/api/debug/swings/{symbol}/{tf}")
def api_debug_swings(symbol: str, tf: str, limit: int = 500) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    cache = ingest.get_cache(symbol, tf)
    if cache is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    times = [candle.close_time for candle in candles]
    pivot_high = find_pivot_highs(highs, 2, 2)
    pivot_low = find_pivot_lows(lows, 2, 2)
    high_points = [
        {"index": idx, "time": times[idx], "price": highs[idx]}
        for idx, flag in enumerate(pivot_high)
        if flag
    ]
    low_points = [
        {"index": idx, "time": times[idx], "price": lows[idx]}
        for idx, flag in enumerate(pivot_low)
        if flag
    ]
    return {"symbol": symbol.upper(), "tf": tf, "highs": high_points, "lows": low_points}


@app.get("/api/setup_candles/{symbol}/{tf}")
def api_setup_candles(symbol: str, tf: str, limit: int = 300) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    config = load_watchlist()
    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol.upper()),
        None,
    )
    if symbol_config is None:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    cache = ingest.get_cache(symbol, tf)
    if cache is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)
    closes = [candle.close for candle in candles]
    sma7 = sma(closes, 7)

    candles_by_tf = {}
    for htf in HTF_TFS:
        htf_cache = ingest.get_cache(symbol, htf)
        candles_by_tf[htf] = htf_cache.list_all() if htf_cache else []
    auto_levels, _, _, meta = compute_levels(
        candles_by_tf,
        symbol_config.levels.cluster_tol_pct,
        symbol_config.levels.max_levels,
    )
    tol_pct_used = meta.get("tol_pct_used", symbol_config.levels.cluster_tol_pct)
    overrides = symbol_config.levels.overrides
    merged = apply_overrides(auto_levels, overrides.add, overrides.disable, tol_pct_used)
    final_levels = merged["final_levels"]

    events = detect_level_events(candles, final_levels)
    items = detect_setup_candles(candles, sma7, events, sl_buffer_pct=0.0015)
    timestamp = candles[-1].close_time if candles else None
    return {
        "symbol": symbol.upper(),
        "tf": tf,
        "limit": limit,
        "sl_buffer_pct": 0.0015,
        "items": items,
        "timestamp": timestamp,
    }


@app.get("/api/openings/{symbol}/{tf}")
def api_openings(symbol: str, tf: str, limit: int = 300) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    config = load_watchlist()
    try:
        result = build_openings(ingest, config, symbol, tf, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@app.get("/api/replay/{symbol}/{tf}")
def api_replay(
    symbol: str,
    tf: str,
    from_ms: int,
    to_ms: int,
    step: int = 1,
    warmup: int = 300,
    debug: int = 0,
) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    if from_ms >= to_ms:
        raise HTTPException(status_code=400, detail="from_ms must be < to_ms")
    config = load_watchlist()
    try:
        result = replay_run(
            ingest,
            config,
            symbol,
            tf,
            from_ms=from_ms,
            to_ms=to_ms,
            step=step,
            warmup=warmup,
            include_debug=bool(debug),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@app.get("/api/replay_summary/{symbol}/{tf}")
def api_replay_summary(
    symbol: str,
    tf: str,
    from_ms: int,
    to_ms: int,
    step: int = 1,
    warmup: int = 300,
    debug: int = 0,
) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    if from_ms >= to_ms:
        raise HTTPException(status_code=400, detail="from_ms must be < to_ms")
    config = load_watchlist()
    try:
        result = replay_run(
            ingest,
            config,
            symbol,
            tf,
            from_ms=from_ms,
            to_ms=to_ms,
            step=step,
            warmup=warmup,
            include_debug=bool(debug),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    summary = replay_summary(result)
    summary.update(
        {
            "symbol": symbol.upper(),
            "tf": tf,
            "from_ms": from_ms,
            "to_ms": to_ms,
            "step": step,
        }
    )
    return summary


@app.get("/api/debug/pivots/{symbol}/{tf}")
def api_debug_pivots(symbol: str, tf: str, limit: int = 200) -> dict:
    ingest = getattr(app.state, "ingest", None)
    if ingest is None:
        raise HTTPException(status_code=503, detail="Ingestion not initialized")
    cache = ingest.get_cache(symbol, tf)
    if cache is None:
        raise HTTPException(status_code=404, detail="Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    pivot_high = find_pivot_highs(highs, 2, 2)
    pivot_low = find_pivot_lows(lows, 2, 2)
    return {
        "candles": [candle.to_dict() for candle in candles],
        "pivot_high": pivot_high,
        "pivot_low": pivot_low,
    }
