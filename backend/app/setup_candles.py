from __future__ import annotations

from typing import List, Optional

from .candle_cache import Candle


def detect_setup_candles(
    candles: List[Candle],
    sma7: List[Optional[float]],
    level_events: List[dict],
    sl_buffer_pct: float = 0.0015,
) -> List[dict]:
    items: List[dict] = []
    if not candles:
        return items

    for event in level_events:
        level = event.get("level")
        direction = event.get("direction")
        last_break = event.get("last_break")
        retest_index = event.get("retest_index")
        last_fakeout = event.get("last_fakeout")

        if level is None or direction is None:
            continue
        if not last_break or retest_index is None:
            continue
        if last_fakeout and last_fakeout.get("index", -1) > last_break.get("index", -1):
            continue

        last_setup = None
        start_idx = retest_index + 1
        for idx in range(start_idx, len(candles)):
            if idx - 1 < 0:
                continue
            if idx >= len(sma7) or idx - 1 >= len(sma7):
                continue
            if sma7[idx] is None or sma7[idx - 1] is None:
                continue

            candle = candles[idx]
            prev_candle = candles[idx - 1]

            if direction == "up":
                if candle.close <= level:
                    continue
                if candle.close <= sma7[idx]:
                    continue
                reclaim = prev_candle.close <= sma7[idx - 1] or candle.low <= sma7[idx]
                if not reclaim:
                    continue
                entry = candle.close
                sl = candle.low * (1 - sl_buffer_pct)
                last_setup = {
                    "level": level,
                    "direction": "long",
                    "setup_index": idx,
                    "time": candle.close_time,
                    "entry": entry,
                    "sl": sl,
                    "sma7": sma7[idx],
                    "level_event": {
                        "break_index": last_break.get("index") if last_break else None,
                        "retest_index": retest_index,
                        "fakeout_index": last_fakeout.get("index") if last_fakeout else None,
                    },
                }
            elif direction == "down":
                if candle.close >= level:
                    continue
                if candle.close >= sma7[idx]:
                    continue
                reclaim = prev_candle.close >= sma7[idx - 1] or candle.high >= sma7[idx]
                if not reclaim:
                    continue
                entry = candle.close
                sl = candle.high * (1 + sl_buffer_pct)
                last_setup = {
                    "level": level,
                    "direction": "short",
                    "setup_index": idx,
                    "time": candle.close_time,
                    "entry": entry,
                    "sl": sl,
                    "sma7": sma7[idx],
                    "level_event": {
                        "break_index": last_break.get("index") if last_break else None,
                        "retest_index": retest_index,
                        "fakeout_index": last_fakeout.get("index") if last_fakeout else None,
                    },
                }

        if last_setup:
            items.append(last_setup)

    return items
