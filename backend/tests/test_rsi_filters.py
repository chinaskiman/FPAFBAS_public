from fastapi.testclient import TestClient

from app.main import app
from app.rsi_filters import atr_multiplier_from_rsi, rsi_distance_from_50


def test_rsi_distance() -> None:
    assert rsi_distance_from_50(60) == 10
    assert rsi_distance_from_50(40) == 10


def test_atr_multiplier_raw() -> None:
    result = atr_multiplier_from_rsi(70)
    assert result["raw"] == 3.0


def test_atr_multiplier_clamp_low() -> None:
    result = atr_multiplier_from_rsi(50)
    assert result["raw"] == 0.0
    assert result["clamped"] == 1.0


def test_atr_multiplier_clamp_high() -> None:
    result = atr_multiplier_from_rsi(100)
    assert result["raw"] == 7.5
    assert result["clamped"] == 3.0


class FakeIngest:
    def list_indicators(self, symbol: str, tf: str, limit: int = 10):
        return {
            "candles": [
                {"close_time": 1000},
                {"close_time": 2000},
            ],
            "rsi14": [55.0, 60.0],
            "atr5": [1.5, 2.0],
        }

    def stop(self):
        return None


def test_rsi_endpoint() -> None:
    with TestClient(app) as client:
        app.state.ingest = FakeIngest()
        resp = client.get("/api/rsi/BTCUSDT/15m")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["symbol"] == "BTCUSDT"
        assert payload["tf"] == "15m"
        assert payload["rsi14_last"] == 60.0
        assert payload["atr5_last"] == 2.0
        assert "atr_mult" in payload
