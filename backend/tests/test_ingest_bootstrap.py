import json
from pathlib import Path

from app.binance_client import parse_klines
from app.ingest_service import BOOTSTRAP_LIMITS, BOOTSTRAP_TFS, IngestService


class FakeRestClient:
    def __init__(self, candles) -> None:
        self.candles = candles
        self.calls = []

    def get_klines(self, symbol: str, interval: str, limit: int):
        self.calls.append((symbol, interval, limit))
        return list(self.candles)


def test_bootstrap_populates_caches() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "klines.json"
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    candles = parse_klines(raw)

    client = FakeRestClient(candles)
    service = IngestService(rest_client=client, cache_maxlen=10)

    service.bootstrap(["BTCUSDT"])

    for tf in BOOTSTRAP_TFS:
        cache = service.get_cache("BTCUSDT", tf)
        assert cache is not None
        assert len(cache) == len(candles)

    expected_calls = {( "BTCUSDT", tf, BOOTSTRAP_LIMITS[tf]) for tf in BOOTSTRAP_TFS}
    assert set(client.calls) == expected_calls


def test_sync_symbols_bootstraps_new_and_drops_removed(monkeypatch) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "klines.json"
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    candles = parse_klines(raw)

    client = FakeRestClient(candles)
    service = IngestService(rest_client=client, cache_maxlen=10)
    service.bootstrap(["BTCUSDT"])

    stream_calls: list[list[str]] = []

    def _fake_start_streaming(symbols):
        stream_calls.append(sorted({symbol.upper() for symbol in symbols}))

    monkeypatch.setattr(service, "start_streaming", _fake_start_streaming)

    first = service.sync_symbols(["BTCUSDT", "ETHUSDT"])
    assert first["added"] == ["ETHUSDT"]
    assert first["removed"] == []
    assert first["streaming"] == ["BTCUSDT", "ETHUSDT"]
    for tf in BOOTSTRAP_TFS:
        assert service.get_cache("ETHUSDT", tf) is not None

    eth_calls = {(symbol, tf, limit) for symbol, tf, limit in client.calls if symbol == "ETHUSDT"}
    expected_eth_calls = {("ETHUSDT", tf, BOOTSTRAP_LIMITS[tf]) for tf in BOOTSTRAP_TFS}
    assert eth_calls == expected_eth_calls
    assert stream_calls[-1] == ["BTCUSDT", "ETHUSDT"]

    second = service.sync_symbols(["ETHUSDT"])
    assert second["added"] == []
    assert second["removed"] == ["BTCUSDT"]
    assert second["streaming"] == ["ETHUSDT"]
    assert service.get_cache("BTCUSDT", "15m") is None
    assert stream_calls[-1] == ["ETHUSDT"]
