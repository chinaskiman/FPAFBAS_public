from __future__ import annotations

from typing import Iterable, Optional

from .indicators import sma


def compute_vol_metrics(volumes: Iterable[float], window_ma: int = 10, window_ma5: int = 5) -> dict:
    series = list(volumes)
    if not series:
        return {
            "vol_last": None,
            "vol_ma10_last": None,
            "vol_ratio": None,
            "vol_ma5_last": None,
            "vol_ma5_slope_pct": None,
            "vol_ma5_slope_ok": False,
        }
    vol_last = series[-1]
    vol_ma10 = sma(series, window_ma)
    vol_ma5 = sma(series, window_ma5)
    vol_ma10_last = vol_ma10[-1] if vol_ma10 else None
    vol_ma5_last = vol_ma5[-1] if vol_ma5 else None

    vol_ratio = None
    if vol_ma10_last not in (None, 0):
        vol_ratio = vol_last / vol_ma10_last

    vol_ma5_slope_pct = None
    if len(vol_ma5) >= 6 and vol_ma5[-1] is not None and vol_ma5[-6] is not None:
        prev = vol_ma5[-6]
        if prev != 0:
            vol_ma5_slope_pct = ((vol_ma5[-1] - prev) / prev) * 100

    vol_ma5_slope_ok = vol_ma5_slope_pct is not None and vol_ma5_slope_pct > 1.8

    return {
        "vol_last": vol_last,
        "vol_ma10_last": vol_ma10_last,
        "vol_ratio": vol_ratio,
        "vol_ma5_last": vol_ma5_last,
        "vol_ma5_slope_pct": vol_ma5_slope_pct,
        "vol_ma5_slope_ok": vol_ma5_slope_ok,
    }


def compute_pullback_vol_decline(volumes: Iterable[float], k: int = 3) -> bool:
    series = list(volumes)
    if k <= 1:
        raise ValueError("k must be >= 2")
    if len(series) < k:
        return False
    window = series[-k:]
    return all(window[idx] < window[idx - 1] for idx in range(1, len(window)))
