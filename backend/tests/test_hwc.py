from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.hwc import classify_bias, compute_hwc_bias, extract_swings
from app.main import app


def _candles_from_series(highs, lows):
    candles = []
    for idx, (high, low) in enumerate(zip(highs, lows)):
        open_time = idx * 60_000
        close_time = open_time + 59_999
        candles.append(
            Candle(
                open_time=open_time,
                close_time=close_time,
                open=low,
                high=high,
                low=low,
                close=high,
                volume=1.0,
            )
        )
    return candles


def test_classify_bias_bullish() -> None:
    highs = [1, 2, 3, 6, 4, 3, 2, 7, 4, 3, 2]
    lows = [6, 5, 4, 2, 3, 4, 5, 3, 4, 5, 6]
    candles = _candles_from_series(highs, lows)
    high_points, low_points = extract_swings(candles)
    assert classify_bias(high_points, low_points) == "bullish"


def test_classify_bias_bearish() -> None:
    highs = [8, 7, 6, 9, 6, 5, 7, 4, 3, 5, 2]
    lows = [5, 4, 3, 4, 2, 1, 3, 2, 0.5, 2, 3]
    candles = _candles_from_series(highs, lows)
    high_points, low_points = extract_swings(candles)
    assert classify_bias(high_points, low_points) == "bearish"


def test_classify_bias_neutral_insufficient() -> None:
    highs = [1, 2, 3, 2]
    lows = [3, 2, 1, 2]
    candles = _candles_from_series(highs, lows)
    high_points, low_points = extract_swings(candles)
    assert classify_bias(high_points, low_points) == "neutral"


def test_hwc_bias_combination() -> None:
    weekly = _candles_from_series(
        [1, 2, 3, 6, 4, 3, 2, 7, 4, 3, 2],
        [6, 5, 4, 2, 3, 4, 5, 3, 4, 5, 6],
    )
    daily = _candles_from_series(
        [1, 2, 3, 6, 4, 3, 2, 7, 4, 3, 2],
        [6, 5, 4, 2, 3, 4, 5, 3, 4, 5, 6],
    )
    hwc = compute_hwc_bias(weekly, daily)
    assert hwc["hwc_bias"] == "bullish"


class FakeIngest:
    def __init__(self, weekly, daily):
        self._caches = {
            ("BTCUSDT", "1w"): weekly,
            ("BTCUSDT", "1d"): daily,
        }

    def get_cache(self, symbol, tf):
        return self._caches.get((symbol.upper(), tf))

    def stop(self):
        return None


def test_hwc_endpoint() -> None:
    weekly = CandleCache(maxlen=2000)
    daily = CandleCache(maxlen=2000)
    weekly.extend(
        _candles_from_series(
            [1, 2, 3, 6, 4, 3, 2, 7, 4, 3, 2],
            [6, 5, 4, 2, 3, 4, 5, 3, 4, 5, 6],
        )
    )
    daily.extend(
        _candles_from_series(
            [1, 2, 3, 6, 4, 3, 2, 7, 4, 3, 2],
            [6, 5, 4, 2, 3, 4, 5, 3, 4, 5, 6],
        )
    )
    with TestClient(app) as client:
        app.state.ingest = FakeIngest(weekly, daily)
        resp = client.get("/api/hwc/BTCUSDT")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["hwc_bias"] == "bullish"
