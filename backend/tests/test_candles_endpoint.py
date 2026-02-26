from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.main import app


class FakeIngest:
    def __init__(self, cache):
        self._cache = cache

    def get_cache(self, symbol, tf):
        if symbol.upper() == "BTCUSDT" and tf == "1h":
            return self._cache
        return None

    def stop(self):
        return None


def _make_candle(idx: int) -> Candle:
    open_time = idx * 60_000
    close_time = open_time + 59_999
    return Candle(
        open_time=open_time,
        close_time=close_time,
        open=100 + idx,
        high=101 + idx,
        low=99 + idx,
        close=100 + idx,
        volume=10 + idx,
    )


def test_candles_endpoint_shape_and_order(monkeypatch) -> None:
    monkeypatch.setenv("DISABLE_INGESTION", "1")
    cache = CandleCache(maxlen=10)
    cache.extend([_make_candle(0), _make_candle(1), _make_candle(2)])
    with TestClient(app) as client:
        app.state.ingest = FakeIngest(cache)
        resp = client.get("/api/candles/BTCUSDT/1h?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["time"] < data[1]["time"]
        assert data[0]["time"] == cache.list_recent(2)[0].close_time
        for item in data:
            assert set(item.keys()) == {"time", "open", "high", "low", "close", "volume"}
