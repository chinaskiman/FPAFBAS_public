from __future__ import annotations

from typing import Iterable, Optional


DI_PEAK_WINDOW_DEFAULT = 30
DI_PEAK_RATIO_THRESHOLD = 0.98
DI_PEAK_MIN_DI = 25.0
DI_PEAK_SUSTAIN_BARS = 2


def compute_di_peak_flags(
    di_series: Iterable[Optional[float]],
    window: int = DI_PEAK_WINDOW_DEFAULT,
    ratio_threshold: float = DI_PEAK_RATIO_THRESHOLD,
    min_di: float = DI_PEAK_MIN_DI,
    sustain_bars: int = DI_PEAK_SUSTAIN_BARS,
) -> dict:
    if window < 1:
        raise ValueError("window must be >= 1")
    if sustain_bars < 1:
        raise ValueError("sustain_bars must be >= 1")
    series = list(di_series)
    if not series:
        return {
            "last": None,
            "peak": None,
            "ratio": None,
            "in_peak_zone": False,
            "is_peak": False,
        }
    last = series[-1]
    window_slice = series[-window:] if window <= len(series) else series
    numeric_window = [value for value in window_slice if value is not None]
    peak = max(numeric_window) if numeric_window else None
    ratio = None
    if last is not None and peak not in (None, 0):
        ratio = last / peak
    in_peak_zone = ratio is not None and ratio >= ratio_threshold and last is not None and last >= min_di

    sustain_slice = series[-sustain_bars:] if sustain_bars <= len(series) else series
    sustain_count = 0
    if peak not in (None, 0):
        for value in sustain_slice:
            if value is None:
                continue
            if value >= min_di and (value / peak) >= ratio_threshold:
                sustain_count += 1
    is_peak = sustain_count == sustain_bars

    return {
        "last": last,
        "peak": peak,
        "ratio": ratio,
        "in_peak_zone": in_peak_zone,
        "is_peak": is_peak,
    }
