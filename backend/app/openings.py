from __future__ import annotations

from typing import Dict, List, Optional

from .di_peak import DI_PEAK_WINDOW_DEFAULT, compute_di_peak_flags
from .hwc import compute_hwc_bias
from .indicators import sma
from .level_events import detect_level_events
from .levels import HTF_TFS, apply_overrides, compute_levels
from .rsi_filters import atr_multiplier_from_rsi, rsi_distance_from_50
from .setup_candles import detect_setup_candles
from .volume_filters import compute_pullback_vol_decline, compute_vol_metrics


def build_openings(ingest, config, symbol: str, tf: str, limit: int = 300) -> dict:
    symbol_upper = symbol.upper()
    cache = ingest.get_cache(symbol_upper, tf)
    if cache is None:
        raise ValueError("Symbol or timeframe not tracked")
    candles = cache.list_recent(limit)
    last_candle_time = candles[-1].close_time if candles else None

    weekly_cache = ingest.get_cache(symbol_upper, "1w")
    daily_cache = ingest.get_cache(symbol_upper, "1d")
    weekly = weekly_cache.list_all() if weekly_cache else []
    daily = daily_cache.list_all() if daily_cache else []
    hwc = compute_hwc_bias(weekly, daily)
    hwc_bias = hwc["hwc_bias"]

    if not candles:
        return {
            "symbol": symbol_upper,
            "tf": tf,
            "hwc_bias": hwc_bias,
            "last_candle_time": None,
            "signals": [],
        }

    indicator_data = ingest.list_indicators(symbol_upper, tf, limit=len(candles))
    rsi_series = indicator_data.get("rsi14", [])
    atr_series = indicator_data.get("atr5", [])
    di_plus = indicator_data.get("di_plus", [])
    di_minus = indicator_data.get("di_minus", [])
    sma7 = indicator_data.get("sma7")
    if sma7 is None:
        sma7 = sma([candle.close for candle in candles], 7)

    di_plus_flags = compute_di_peak_flags(di_plus, window=DI_PEAK_WINDOW_DEFAULT)
    di_minus_flags = compute_di_peak_flags(di_minus, window=DI_PEAK_WINDOW_DEFAULT)
    not_at_peak_long = not di_minus_flags["is_peak"]
    not_at_peak_short = not di_plus_flags["is_peak"]

    volumes = [candle.volume for candle in candles]
    vol_metrics = compute_vol_metrics(volumes, window_ma=10, window_ma5=5)
    pullback_decline = compute_pullback_vol_decline(volumes, k=3)

    rsi_last = rsi_series[-1] if rsi_series else None
    atr_last = atr_series[-1] if atr_series else None
    rsi_distance = rsi_distance_from_50(rsi_last) if rsi_last is not None else None
    atr_mult_raw = None
    atr_mult = None
    if rsi_last is not None:
        mult = atr_multiplier_from_rsi(rsi_last)
        atr_mult_raw = mult["raw"]
        atr_mult = mult["clamped"]
    atr_stop_distance = atr_last * atr_mult if atr_last is not None and atr_mult is not None else None

    context = {
        "vol_ma5_slope_ok": vol_metrics["vol_ma5_slope_ok"],
        "pullback_vol_decline": pullback_decline,
        "not_at_peak_long": not_at_peak_long,
        "not_at_peak_short": not_at_peak_short,
        "rsi_distance": rsi_distance,
        "atr_mult": atr_mult,
        "atr_stop_distance": atr_stop_distance,
    }

    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol_upper),
        None,
    )
    if symbol_config is None:
        raise ValueError("Symbol not found in watchlist")

    candles_by_tf = {}
    for htf in HTF_TFS:
        htf_cache = ingest.get_cache(symbol_upper, htf)
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
    setup_items = detect_setup_candles(candles, sma7, events, sl_buffer_pct=0.0015)

    if hwc_bias == "neutral":
        return {
            "symbol": symbol_upper,
            "tf": tf,
            "hwc_bias": hwc_bias,
            "last_candle_time": last_candle_time,
            "signals": [],
        }

    allowed_direction = "long" if hwc_bias == "bullish" else "short"

    signals: List[dict] = []
    break_levels = set()
    for event in events:
        last_break = event.get("last_break")
        if not last_break or last_break.get("time") != last_candle_time:
            continue
        if event.get("direction") == "up":
            direction = "long"
        elif event.get("direction") == "down":
            direction = "short"
        else:
            continue
        if direction != allowed_direction:
            continue
        if not vol_metrics["vol_ma5_slope_ok"]:
            continue
        di_ok = not_at_peak_long if direction == "long" else not_at_peak_short
        if not di_ok:
            continue
        break_index = last_break.get("index")
        candle = candles[break_index] if break_index is not None and break_index < len(candles) else None
        entry = last_break["close"]
        sl = None
        if atr_stop_distance is not None:
            sl = entry - atr_stop_distance if direction == "long" else entry + atr_stop_distance
        signals.append(
            {
                "type": "break",
                "level": event.get("level"),
                "direction": direction,
                "time": last_break["time"],
                "entry": entry,
                "sl": sl,
                "sl_reason": "atr_stop",
                "candle": candle.to_dict() if candle else None,
                "level_event": {
                    "break_index": break_index,
                    "retest_index": event.get("retest_index"),
                    "fakeout_index": event.get("last_fakeout", {}).get("index") if event.get("last_fakeout") else None,
                },
                "context": context,
            }
        )
        break_levels.add(event.get("level"))

    for item in setup_items:
        if item.get("time") != last_candle_time:
            continue
        if item.get("direction") != allowed_direction:
            continue
        if item.get("level") in break_levels:
            continue
        setup_index = item.get("setup_index")
        candle = candles[setup_index] if setup_index is not None and setup_index < len(candles) else None
        level_event = item.get("level_event") or {}
        signals.append(
            {
                "type": "setup",
                "level": item.get("level"),
                "direction": item.get("direction"),
                "time": item.get("time"),
                "entry": item.get("entry"),
                "sl": item.get("sl"),
                "sl_reason": "setup_candle",
                "candle": candle.to_dict() if candle else None,
                "level_event": {
                    "break_index": level_event.get("break_index"),
                    "retest_index": level_event.get("retest_index"),
                    "fakeout_index": level_event.get("fakeout_index"),
                },
                "context": context,
            }
        )

    for event in events:
        last_fakeout = event.get("last_fakeout")
        if not last_fakeout or last_fakeout.get("time") != last_candle_time:
            continue
        break_direction = event.get("direction")
        if break_direction == "up":
            direction = "short"
        elif break_direction == "down":
            direction = "long"
        else:
            continue
        if direction != allowed_direction:
            continue
        idx = last_fakeout.get("index")
        if idx is None or idx >= len(candles):
            continue
        candle = candles[idx]
        if direction == "short":
            sl = candle.high * (1 + 0.0015)
        else:
            sl = candle.low * (1 - 0.0015)
        signals.append(
            {
                "type": "fakeout",
                "level": event.get("level"),
                "direction": direction,
                "time": last_fakeout.get("time"),
                "entry": last_fakeout.get("close"),
                "sl": sl,
                "sl_reason": "fakeout_extreme",
                "candle": candle.to_dict(),
                "level_event": {
                    "break_index": event.get("last_break", {}).get("index") if event.get("last_break") else None,
                    "retest_index": event.get("retest_index"),
                    "fakeout_index": idx,
                },
                "context": context,
            }
        )

    return {
        "symbol": symbol_upper,
        "tf": tf,
        "hwc_bias": hwc_bias,
        "last_candle_time": last_candle_time,
        "signals": signals,
    }
