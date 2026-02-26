from __future__ import annotations


def rsi_distance_from_50(rsi: float) -> float:
    return abs(rsi - 50.0)


def atr_multiplier_from_rsi(rsi: float) -> dict:
    raw = abs(rsi - 50.0) * 3.0 / 20.0
    clamped = min(3.0, max(1.0, raw))
    return {"raw": raw, "clamped": clamped}
