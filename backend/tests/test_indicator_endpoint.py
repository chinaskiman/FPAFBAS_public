import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.binance_client import parse_klines
from app.ingest_service import IngestService
from app.main import app


class FakeRestClient:
    def __init__(self, candles) -> None:
        self.candles = candles

    def get_klines(self, symbol: str, interval: str, limit: int):
        return list(self.candles)


def test_indicator_endpoint_alignment(monkeypatch) -> None:
    monkeypatch.setenv("DISABLE_INGESTION", "1")

    fixture_path = Path(__file__).parent / "fixtures" / "klines.json"
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    candles = parse_klines(raw)

    ingest = IngestService(rest_client=FakeRestClient(candles), cache_maxlen=10)
    ingest.bootstrap(["BTCUSDT"])
    with TestClient(app) as client:
        app.state.ingest = ingest
        response = client.get("/api/indicators/BTCUSDT/1h?limit=2")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["candles"]) == 2
        assert len(payload["rsi14"]) == 2
        assert len(payload["atr5"]) == 2
        assert len(payload["sma7"]) == 2
        assert len(payload["sma25"]) == 2
        assert len(payload["sma99"]) == 2
        assert len(payload["di_plus"]) == 2
        assert len(payload["di_minus"]) == 2
        assert len(payload["adx14"]) == 2
        assert len(payload["vol_ma10"]) == 2
