from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.config import WatchlistConfig
from app.main import app
from app.replay import replay_run


class FakeIngest:
    def __init__(self, candles_by_tf):
        self._caches = {}
        for tf, candles in candles_by_tf.items():
            cache = CandleCache(maxlen=2000)
            cache.extend(candles)
            self._caches[("BTCUSDT", tf)] = cache

    def get_cache(self, symbol, tf):
        return self._caches.get((symbol.upper(), tf))

    def get_cached_range(self, symbol, tf, from_ms, to_ms, limit=None):
        cache = self.get_cache(symbol, tf)
        if cache is None:
            return []
        candles = [c for c in cache.list_all() if from_ms <= c.close_time <= to_ms]
        if limit is not None and limit > 0:
            candles = candles[-limit:]
        return candles

    def stop(self):
        return None


def _make_candle(idx: int, close: float, high: float, low: float) -> Candle:
    open_time = idx * 60_000
    close_time = open_time + 59_999
    return Candle(
        open_time=open_time,
        close_time=close_time,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def _make_watchlist(pinned=None) -> WatchlistConfig:
    return WatchlistConfig.model_validate(
        {
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
                        "max_levels": 6,
                        "cluster_tol_pct": 0.05,
                        "overrides": {"add": pinned or [], "disable": []},
                    },
                }
            ],
            "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
        }
    )


def test_replay_no_lookahead_pivot() -> None:
    highs = [1.0, 2.0, 5.0, 2.0, 1.0]
    lows = [0.5] * len(highs)
    candles = [_make_candle(i, close=highs[i], high=highs[i], low=lows[i]) for i in range(len(highs))]
    ingest = FakeIngest({"4h": candles})
    config = _make_watchlist()
    result = replay_run(
        ingest,
        config,
        "BTCUSDT",
        "4h",
        from_ms=candles[0].close_time,
        to_ms=candles[-1].close_time,
        warmup=0,
    )
    items = result["items"]
    assert len(items) == len(candles)
    levels_before = items[2]["levels"]
    levels_after = items[4]["levels"]
    assert not any(abs(level - 5.0) < 1e-6 for level in levels_before)
    assert any(abs(level - 5.0) < 1e-6 for level in levels_after)


def test_replay_setup_sequence_triggers() -> None:
    level = 100.0
    candles = [
        _make_candle(0, 98, 99, 97),
        _make_candle(1, 99, 100, 98),
        _make_candle(2, 101, 102, 100),  # break
        _make_candle(3, 102, 103, 99),   # retest wick
        _make_candle(4, 103, 104, 102),
        _make_candle(5, 104, 105, 103),
        _make_candle(6, 104, 105, 103),
        _make_candle(7, 105, 106, 101),  # setup candle
    ]
    ingest = FakeIngest({"1h": candles, "4h": candles, "1d": candles, "1w": candles})
    config = _make_watchlist(pinned=[level])
    result = replay_run(
        ingest,
        config,
        "BTCUSDT",
        "1h",
        from_ms=candles[0].close_time,
        to_ms=candles[-1].close_time,
        warmup=0,
        include_debug=True,
    )
    last_item = result["items"][-1]
    setups = last_item.get("setup_candles") or []
    assert any(item.get("setup_index") == 7 for item in setups)


def test_replay_output_stable() -> None:
    candles = [_make_candle(i, 100 + i, 101 + i, 99 + i) for i in range(5)]
    ingest = FakeIngest({"1h": candles, "4h": candles, "1d": candles, "1w": candles})
    config = _make_watchlist()
    result1 = replay_run(
        ingest,
        config,
        "BTCUSDT",
        "1h",
        from_ms=candles[0].close_time,
        to_ms=candles[-1].close_time,
        warmup=0,
    )
    result2 = replay_run(
        ingest,
        config,
        "BTCUSDT",
        "1h",
        from_ms=candles[0].close_time,
        to_ms=candles[-1].close_time,
        warmup=0,
    )
    assert result1["items"] == result2["items"]
