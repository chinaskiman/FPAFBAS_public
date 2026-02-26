import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.level_events import detect_level_events
from app.main import app


def _make_candle(idx: int, close: float, high: float, low: float, volume: float = 1.0) -> Candle:
    open_time = idx * 60_000
    close_time = open_time + 59_999
    return Candle(
        open_time=open_time,
        close_time=close_time,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_break_retest_up() -> None:
    level = 100.0
    candles = [
        _make_candle(0, 98, 99, 97),
        _make_candle(1, 99, 100, 98),
        _make_candle(2, 101, 102, 100),  # break up
        _make_candle(3, 102, 103, 99),   # retest wick
        _make_candle(4, 103, 104, 101),
    ]
    slope_ok = [False] * len(candles)
    events = detect_level_events(candles, [level], slope_ok_series=slope_ok)
    event = events[0]
    assert event["direction"] == "up"
    assert event["last_break"]["index"] == 2
    assert event["retest_touched"] is True
    assert event["last_fakeout"] is None


def test_fakeout_up_requires_slope() -> None:
    level = 100.0
    candles = [
        _make_candle(0, 98, 99, 97),
        _make_candle(1, 99, 100, 98),
        _make_candle(2, 101, 102, 100),  # break up
        _make_candle(3, 102, 103, 99),   # retest wick
        _make_candle(4, 99, 100, 98),    # back inside
    ]
    slope_ok = [False, False, False, False, True]
    events = detect_level_events(candles, [level], slope_ok_series=slope_ok)
    event = events[0]
    assert event["last_fakeout"] is not None
    assert event["last_fakeout"]["index"] == 4


def test_break_down_retest() -> None:
    level = 100.0
    candles = [
        _make_candle(0, 102, 103, 101),
        _make_candle(1, 101, 102, 100),
        _make_candle(2, 99, 100, 98),   # break down
        _make_candle(3, 98, 101, 97),   # retest wick high
    ]
    slope_ok = [False] * len(candles)
    events = detect_level_events(candles, [level], slope_ok_series=slope_ok)
    event = events[0]
    assert event["direction"] == "down"
    assert event["last_break"]["index"] == 2
    assert event["retest_touched"] is True


def test_fakeout_window_expired() -> None:
    level = 100.0
    candles = [
        _make_candle(0, 98, 99, 97),
        _make_candle(1, 99, 100, 98),
        _make_candle(2, 101, 102, 100),  # break up
        _make_candle(3, 102, 103, 99),   # retest wick
        _make_candle(4, 105, 106, 104),
        _make_candle(5, 106, 107, 105),
        _make_candle(6, 99, 100, 98),    # back inside but too late
    ]
    slope_ok = [False, False, False, False, True, True, True]
    events = detect_level_events(candles, [level], slope_ok_series=slope_ok, max_fakeout_bars=2)
    event = events[0]
    assert event["last_fakeout"] is None


class FakeIngest:
    def __init__(self, candles):
        self._caches = {
            ("BTCUSDT", "1h"): candles,
            ("BTCUSDT", "1w"): CandleCache(maxlen=2000),
            ("BTCUSDT", "1d"): CandleCache(maxlen=2000),
            ("BTCUSDT", "4h"): CandleCache(maxlen=2000),
        }

    def get_cache(self, symbol, tf):
        return self._caches.get((symbol.upper(), tf))

    def stop(self):
        return None


def test_level_events_api(tmp_path, monkeypatch) -> None:
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

    candle_cache = CandleCache(maxlen=2000)
    candle_cache.extend(
        [
            _make_candle(0, 98, 99, 97),
            _make_candle(1, 99, 100, 98),
            _make_candle(2, 101, 102, 100),
        ]
    )
    with TestClient(app) as client:
        app.state.ingest = FakeIngest(candle_cache)
        resp = client.get("/api/level_events/BTCUSDT/1h?limit=50")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["symbol"] == "BTCUSDT"
        assert payload["tf"] == "1h"
        assert payload["levels"] == [100.0]
        assert isinstance(payload["events"], list)
