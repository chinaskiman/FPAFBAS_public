from fastapi.testclient import TestClient

from app.di_peak import compute_di_peak_flags, DI_PEAK_WINDOW_DEFAULT
from app.main import app


def test_di_peak_not_peak_with_wider_window() -> None:
    series = [50.0] + [40.0] * 28 + [45.0]
    result = compute_di_peak_flags(series)
    assert result["peak"] == 50.0
    assert result["ratio"] == 45.0 / 50.0
    assert result["is_peak"] is False


def test_di_peak_sustained_near_max() -> None:
    series = [40.0] * (DI_PEAK_WINDOW_DEFAULT - 2) + [39.2, 39.5]
    result = compute_di_peak_flags(series)
    assert result["is_peak"] is True
    assert result["in_peak_zone"] is True


def test_di_peak_below_min_di() -> None:
    series = [20.0] * DI_PEAK_WINDOW_DEFAULT
    result = compute_di_peak_flags(series)
    assert result["peak"] == 20.0
    assert result["is_peak"] is False


class FakeIngest:
    def list_indicators(self, symbol: str, tf: str, limit: int = 10):
        return {
            "candles": [
                {"close_time": 1000},
                {"close_time": 2000},
                {"close_time": 3000},
            ],
            "di_plus": [30.0, 30.0, 30.0],
            "di_minus": [10.0, 10.0, 10.0],
            "adx14": [10.0, 20.0, 30.0],
        }

    def stop(self):
        return None


def test_di_peak_endpoint() -> None:
    with TestClient(app) as client:
        app.state.ingest = FakeIngest()
        resp = client.get("/api/di_peak/BTCUSDT/15m?window=3")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["di_plus"]["is_peak"] is True
        assert payload["di_minus"]["is_peak"] is False
        assert payload["not_at_peak_long"] is True
        assert payload["not_at_peak_short"] is False
        assert payload["adx14_last"] == 30.0
        assert payload["timestamp"] == 3000
