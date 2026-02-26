from __future__ import annotations

from typing import Iterable, List, Optional


def sma(values: Iterable[float], period: int) -> List[Optional[float]]:
    data = list(values)
    size = len(data)
    if period <= 0:
        raise ValueError("period must be positive")
    result: List[Optional[float]] = [None] * size
    if size < period:
        return result
    window_sum = sum(data[:period])
    result[period - 1] = window_sum / period
    for idx in range(period, size):
        window_sum += data[idx] - data[idx - period]
        result[idx] = window_sum / period
    return result


def rsi(values: Iterable[float], period: int = 14) -> List[Optional[float]]:
    data = list(values)
    size = len(data)
    if period <= 0:
        raise ValueError("period must be positive")
    result: List[Optional[float]] = [None] * size
    if size <= period:
        return result

    gains = []
    losses = []
    for idx in range(1, period + 1):
        delta = data[idx] - data[idx - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    result[period] = _rsi_from_avgs(avg_gain, avg_loss)

    for idx in range(period + 1, size):
        delta = data[idx] - data[idx - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        result[idx] = _rsi_from_avgs(avg_gain, avg_loss)

    return result


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(highs: Iterable[float], lows: Iterable[float], closes: Iterable[float], period: int = 5) -> List[Optional[float]]:
    high_list = list(highs)
    low_list = list(lows)
    close_list = list(closes)
    size = len(high_list)
    if period <= 0:
        raise ValueError("period must be positive")
    result: List[Optional[float]] = [None] * size
    if size == 0:
        return result

    tr: List[float] = []
    for idx in range(size):
        if idx == 0:
            tr.append(high_list[idx] - low_list[idx])
            continue
        tr_val = max(
            high_list[idx] - low_list[idx],
            abs(high_list[idx] - close_list[idx - 1]),
            abs(low_list[idx] - close_list[idx - 1]),
        )
        tr.append(tr_val)

    if size < period:
        return result

    atr_val = sum(tr[:period]) / period
    result[period - 1] = atr_val
    for idx in range(period, size):
        atr_val = (atr_val * (period - 1) + tr[idx]) / period
        result[idx] = atr_val
    return result


def dmi_adx(
    highs: Iterable[float],
    lows: Iterable[float],
    closes: Iterable[float],
    period: int = 14,
) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    high_list = list(highs)
    low_list = list(lows)
    close_list = list(closes)
    size = len(high_list)
    if period <= 0:
        raise ValueError("period must be positive")

    di_plus: List[Optional[float]] = [None] * size
    di_minus: List[Optional[float]] = [None] * size
    adx: List[Optional[float]] = [None] * size
    if size < period + 1:
        return di_plus, di_minus, adx

    tr: List[float] = [0.0] * size
    plus_dm: List[float] = [0.0] * size
    minus_dm: List[float] = [0.0] * size

    for idx in range(1, size):
        up_move = high_list[idx] - high_list[idx - 1]
        down_move = low_list[idx - 1] - low_list[idx]
        plus_dm[idx] = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm[idx] = down_move if down_move > up_move and down_move > 0 else 0.0

        tr[idx] = max(
            high_list[idx] - low_list[idx],
            abs(high_list[idx] - close_list[idx - 1]),
            abs(low_list[idx] - close_list[idx - 1]),
        )

    tr_smooth = sum(tr[1 : period + 1])
    plus_smooth = sum(plus_dm[1 : period + 1])
    minus_smooth = sum(minus_dm[1 : period + 1])

    for idx in range(period, size):
        if idx > period:
            tr_smooth = tr_smooth - (tr_smooth / period) + tr[idx]
            plus_smooth = plus_smooth - (plus_smooth / period) + plus_dm[idx]
            minus_smooth = minus_smooth - (minus_smooth / period) + minus_dm[idx]

        if tr_smooth == 0:
            di_plus[idx] = 0.0
            di_minus[idx] = 0.0
        else:
            di_plus[idx] = 100.0 * (plus_smooth / tr_smooth)
            di_minus[idx] = 100.0 * (minus_smooth / tr_smooth)

    dx: List[Optional[float]] = [None] * size
    for idx in range(period, size):
        plus_val = di_plus[idx]
        minus_val = di_minus[idx]
        if plus_val is None or minus_val is None:
            continue
        denom = plus_val + minus_val
        if denom == 0:
            dx[idx] = 0.0
        else:
            dx[idx] = 100.0 * abs(plus_val - minus_val) / denom

    if size < period * 2:
        return di_plus, di_minus, adx

    first_adx_index = period * 2 - 1
    initial_dx = [value for value in dx[period:first_adx_index + 1] if value is not None]
    if len(initial_dx) == period:
        adx_val = sum(initial_dx) / period
        adx[first_adx_index] = adx_val
        for idx in range(first_adx_index + 1, size):
            if dx[idx] is None:
                continue
            adx_val = (adx_val * (period - 1) + dx[idx]) / period
            adx[idx] = adx_val

    return di_plus, di_minus, adx
