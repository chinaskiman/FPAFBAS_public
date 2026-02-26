import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.indicators import sma
from app.main import app
from app.setup_candles import detect_setup_candles


def _make_candle(idx: int, close: float, high: float | None = None, low: float | None = None) -> Candle:
    open_time = idx * 60_000
    close_time = open_time + 59_999
    high = high if high is not None else close + 1
    low = low if low is not None else close - 1
    return Candle(
        open_time=open_time,
        close_time=close_time,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def test_setup_candle_long() -> None:
    closes = [90, 92, 94, 96, 98, 100, 102, 104, 106, 108]
    candles = []
    for idx, close in enumerate(closes):
        low = close - 1
        if idx == 7:
            low = 97
        candles.append(_make_candle(idx, close, high=close + 2, low=low))

    sma7 = sma([c.close for c in candles], 7)
    events = [
        {
            "level": 100.0,
            "direction": "up",
            "last_break": {"index": 4},
            "retest_index": 6,
            "last_fakeout": None,
        }
    ]
    items = detect_setup_candles(candles, sma7, events, sl_buffer_pct=0.0015)
    assert len(items) == 1
    item = items[0]
    assert item["direction"] == "long"
    assert item["setup_index"] == 7
    assert item["entry"] == candles[7].close
    assert item["sl"] == candles[7].low * (1 - 0.0015)


def test_setup_candle_short() -> None:
    closes = [110, 108, 106, 104, 102, 100, 98, 96, 94, 92]
    candles = []
    for idx, close in enumerate(closes):
        high = close + 1
        if idx == 7:
            high = 110
        candles.append(_make_candle(idx, close, high=high, low=close - 2))

    sma7 = sma([c.close for c in candles], 7)
    events = [
        {
            "level": 100.0,
            "direction": "down",
            "last_break": {"index": 4},
            "retest_index": 6,
            "last_fakeout": None,
        }
    ]
    items = detect_setup_candles(candles, sma7, events, sl_buffer_pct=0.0015)
    assert len(items) == 1
    item = items[0]
    assert item["direction"] == "short"
    assert item["setup_index"] == 7
    assert item["entry"] == candles[7].close
    assert item["sl"] == candles[7].high * (1 + 0.0015)


def test_setup_candle_blocked_by_fakeout() -> None:
    closes = [90, 92, 94, 96, 98, 100, 102, 104]
    candles = [_make_candle(idx, close) for idx, close in enumerate(closes)]
    sma7 = sma([c.close for c in candles], 7)
    events = [
        {
            "level": 100.0,
            "direction": "up",
            "last_break": {"index": 4},
            "retest_index": 6,
            "last_fakeout": {"index": 7},
        }
    ]
    items = detect_setup_candles(candles, sma7, events, sl_buffer_pct=0.0015)
    assert items == []


class FakeIngest:
    def __init__(self, tf_cache: CandleCache, htf_cache: CandleCache):
        self._caches = {
            ("BTCUSDT", "1h"): tf_cache,
            ("BTCUSDT", "1w"): htf_cache,
            ("BTCUSDT", "1d"): htf_cache,
            ("BTCUSDT", "4h"): htf_cache,
        }

    def get_cache(self, symbol, tf):
        return self._caches.get((symbol.upper(), tf))

    def stop(self):
        return None


def test_setup_candles_endpoint(tmp_path, monkeypatch) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    watchlist = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "enabled": True,
                "entry_tfs": ["15m", "1h"],
                "setups": {
                    "continuation": True,
                    "retest": True,
                    "fakeout": True,
                    "setup_candle": True,
                },
                "levels": {
                    "auto": True,
                    "max_levels": 5,
                    "cluster_tol_pct": 0.01,
                    "overrides": {"add": [100.0], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }
    watchlist_path.write_text(json.dumps(watchlist), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))

    closes = [90, 92, 94, 96, 98, 100, 102, 104, 106, 108]
    tf_cache = CandleCache(maxlen=2000)
    tf_cache.extend(
        [_make_candle(idx, close, high=close + 2, low=close - 1) for idx, close in enumerate(closes)]
    )
    htf_cache = CandleCache(maxlen=2000)
    htf_cache.extend(
        [_make_candle(idx, close + 200, high=close + 202, low=close + 198) for idx, close in enumerate(closes)]
    )
    with TestClient(app) as client:
        app.state.ingest = FakeIngest(tf_cache, htf_cache)
        resp = client.get("/api/setup_candles/BTCUSDT/1h?limit=50")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["symbol"] == "BTCUSDT"
        assert payload["tf"] == "1h"
        assert "items" in payload
