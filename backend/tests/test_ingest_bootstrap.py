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
