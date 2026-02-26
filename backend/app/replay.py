from __future__ import annotations

import bisect
import time
from typing import Dict, List, Optional, Tuple

from .candle_cache import Candle
from .di_peak import DI_PEAK_WINDOW_DEFAULT, compute_di_peak_flags
from .hwc import compute_hwc_bias
from .indicators import atr, dmi_adx, rsi, sma
from .level_events import detect_level_events
from .levels import HTF_TFS, apply_overrides, compute_levels
from .rsi_filters import atr_multiplier_from_rsi, rsi_distance_from_50
from .setup_candles import detect_setup_candles
from .volume_filters import compute_pullback_vol_decline, compute_vol_metrics


def replay_run(
    ingest,
    config,
    symbol: str,
    tf: str,
    from_ms: int,
    to_ms: int,
    step: int = 1,
    warmup: int = 300,
    include_debug: bool = False,
) -> dict:
    symbol_upper = symbol.upper()
    cache = ingest.get_cache(symbol_upper, tf)
    if cache is None:
        raise ValueError("Symbol or timeframe not tracked")
    all_candles = cache.list_all()
    if not all_candles:
        return _empty_replay(symbol_upper, tf, from_ms, to_ms, step)

    times = [candle.close_time for candle in all_candles]
    start_idx = bisect.bisect_left(times, from_ms)
    end_idx = bisect.bisect_right(times, to_ms) - 1
    if start_idx >= len(all_candles) or end_idx < start_idx:
        return _empty_replay(symbol_upper, tf, from_ms, to_ms, step)

    warmup_start = max(0, start_idx - max(warmup, 0))
    candles = all_candles[warmup_start : end_idx + 1]
    start_offset = start_idx - warmup_start

    htf_all: Dict[str, List[Candle]] = {}
    htf_times: Dict[str, List[int]] = {}
    for htf in HTF_TFS:
        htf_cache = ingest.get_cache(symbol_upper, htf)
        series = htf_cache.list_all() if htf_cache else []
        htf_all[htf] = series
        htf_times[htf] = [candle.close_time for candle in series]

    symbol_config = next(
        (item for item in config.symbols if item.symbol.upper() == symbol_upper),
        None,
    )
    if symbol_config is None:
        raise ValueError("Symbol not found in watchlist")

    items: List[dict] = []
    for idx in range(start_offset, len(candles), max(step, 1)):
        window = candles[: idx + 1]
        last = window[-1]
        last_time = last.close_time

        candles_by_tf = {}
        for htf, series in htf_all.items():
            if not series:
                candles_by_tf[htf] = []
                continue
            end = bisect.bisect_right(htf_times[htf], last_time)
            candles_by_tf[htf] = series[:end]

        auto_levels, _selected, _clusters, meta = compute_levels(
            candles_by_tf,
            symbol_config.levels.cluster_tol_pct,
            symbol_config.levels.max_levels,
        )
        tol_pct_used = meta.get("tol_pct_used", symbol_config.levels.cluster_tol_pct)
        overrides = symbol_config.levels.overrides
        merged = apply_overrides(auto_levels, overrides.add, overrides.disable, tol_pct_used)
        final_levels = merged["final_levels"]

        events = detect_level_events(window, final_levels)

        closes = [candle.close for candle in window]
        highs = [candle.high for candle in window]
        lows = [candle.low for candle in window]
        volumes = [candle.volume for candle in window]

        sma7 = sma(closes, 7)
        setup_items = detect_setup_candles(window, sma7, events, sl_buffer_pct=0.0015)

        rsi_series = rsi(closes, 14)
        atr_series = atr(highs, lows, closes, 5)
        di_plus, di_minus, adx14 = dmi_adx(highs, lows, closes, 14)

        di_plus_flags = compute_di_peak_flags(di_plus, window=DI_PEAK_WINDOW_DEFAULT)
        di_minus_flags = compute_di_peak_flags(di_minus, window=DI_PEAK_WINDOW_DEFAULT)
        not_at_peak_long = not di_minus_flags["is_peak"]
        not_at_peak_short = not di_plus_flags["is_peak"]

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

        weekly = candles_by_tf.get("1w", [])
        daily = candles_by_tf.get("1d", [])
        hwc = compute_hwc_bias(weekly, daily)
        hwc_bias = hwc["hwc_bias"]

        signals = _build_openings_from_window(
            window,
            events,
            setup_items,
            hwc_bias,
            context,
            atr_stop_distance,
        )

        item = {
            "index": idx,
            "time": last_time,
            "candle": {
                "open": last.open,
                "high": last.high,
                "low": last.low,
                "close": last.close,
                "volume": last.volume,
            },
            "levels": final_levels,
            "tol_pct_used": tol_pct_used,
            "level_events": events,
            "setup_candles": setup_items,
            "signals": signals,
            "hwc_bias": hwc_bias,
            "filters": {
                "vol_ok": vol_metrics["vol_ma5_slope_ok"],
                "di_ok": not_at_peak_long and not_at_peak_short,
                "rsi_ok": rsi_distance is not None,
                "atr_ok": atr_stop_distance is not None,
            },
        }
        items.append(item)

    return {
        "symbol": symbol_upper,
        "tf": tf,
        "from_ms": from_ms,
        "to_ms": to_ms,
        "step": step,
        "items": items,
        "last_candle_time": items[-1]["time"] if items else None,
        "timestamp": int(time.time() * 1000),
    }


def replay_summary(result: dict) -> dict:
    items = result.get("items", [])
    total_steps = len(items)
    signals_total = 0
    by_type = {"break": 0, "setup": 0, "fakeout": 0}
    by_direction = {"long": 0, "short": 0}
    filter_pass = {"vol_ok_true": 0, "di_ok_true": 0, "rsi_ok_true": 0, "atr_ok_true": 0}
    by_day: Dict[str, int] = {}

    for item in items:
        filters = item.get("filters") or {}
        if filters.get("vol_ok"):
            filter_pass["vol_ok_true"] += 1
        if filters.get("di_ok"):
            filter_pass["di_ok_true"] += 1
        if filters.get("rsi_ok"):
            filter_pass["rsi_ok_true"] += 1
        if filters.get("atr_ok"):
            filter_pass["atr_ok_true"] += 1

        for signal in item.get("signals", []):
            signals_total += 1
            signal_type = signal.get("type")
            if signal_type in by_type:
                by_type[signal_type] += 1
            direction = signal.get("direction")
            if direction in by_direction:
                by_direction[direction] += 1
            time_ms = signal.get("time")
            if time_ms:
                day = time.strftime("%Y-%m-%d", time.gmtime(time_ms / 1000))
                by_day[day] = by_day.get(day, 0) + 1

    return {
        "total_steps": total_steps,
        "signals_total": signals_total,
        "by_type": by_type,
        "by_direction": by_direction,
        "filter_pass": filter_pass,
        "by_day": [{"day": day, "signals": count} for day, count in sorted(by_day.items())],
    }


def _build_openings_from_window(
    candles: List[Candle],
    events: List[dict],
    setup_items: List[dict],
    hwc_bias: str,
    context: dict,
    atr_stop_distance: Optional[float],
) -> List[dict]:
    last_candle_time = candles[-1].close_time if candles else None
    if not candles or hwc_bias == "neutral":
        return []
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
        if not context.get("vol_ma5_slope_ok"):
            continue
        di_ok = context.get("not_at_peak_long") if direction == "long" else context.get("not_at_peak_short")
        if not di_ok:
            continue
        break_index = last_break.get("index")
        candle = candles[break_index] if break_index is not None and break_index < len(candles) else None
        entry = last_break["close"]
        sl = None
        if atr_stop_distance is not None:
            sl = entry - atr_stop_distance if direction == "long" else entry + atr_stop_distance
        signals.append(
            _signal_payload(
                {
                    "type": "break",
                    "level": event.get("level"),
                    "direction": direction,
                    "time": last_break["time"],
                    "entry": entry,
                    "sl": sl,
                    "sl_reason": "atr_stop",
                },
                candle,
                {
                    "break_index": break_index,
                    "retest_index": event.get("retest_index"),
                    "fakeout_index": event.get("last_fakeout", {}).get("index") if event.get("last_fakeout") else None,
                },
                None,
                context,
            )
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
            _signal_payload(
                {
                    "type": "setup",
                    "level": item.get("level"),
                    "direction": item.get("direction"),
                    "time": item.get("time"),
                    "entry": item.get("entry"),
                    "sl": item.get("sl"),
                    "sl_reason": "setup_candle",
                },
                candle,
                {
                    "break_index": level_event.get("break_index"),
                    "retest_index": level_event.get("retest_index"),
                    "fakeout_index": level_event.get("fakeout_index"),
                },
                setup_index,
                context,
            )
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
            _signal_payload(
                {
                    "type": "fakeout",
                    "level": event.get("level"),
                    "direction": direction,
                    "time": last_fakeout.get("time"),
                    "entry": last_fakeout.get("close"),
                    "sl": sl,
                    "sl_reason": "fakeout_extreme",
                },
                candle,
                {
                    "break_index": event.get("last_break", {}).get("index") if event.get("last_break") else None,
                    "retest_index": event.get("retest_index"),
                    "fakeout_index": idx,
                },
                None,
                context,
            )
        )

    return signals


def _signal_payload(
    base: dict,
    candle: Optional[Candle],
    level_event: dict,
    setup_index: Optional[int],
    context: dict,
) -> dict:
    trigger = None
    if candle is not None:
        trigger = {
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
    return {
        **base,
        "candle": candle.to_dict() if candle else None,
        "level_event": level_event,
        "context": context,
        "trigger_candle": trigger,
        "level_event_indices": level_event,
        "setup_index": setup_index,
    }


def _empty_replay(symbol: str, tf: str, from_ms: int, to_ms: int, step: int) -> dict:
    return {
        "symbol": symbol,
        "tf": tf,
        "from_ms": from_ms,
        "to_ms": to_ms,
        "step": step,
        "items": [],
        "last_candle_time": None,
        "timestamp": int(time.time() * 1000),
    }
