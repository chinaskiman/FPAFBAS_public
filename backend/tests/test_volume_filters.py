from fastapi.testclient import TestClient

from app.main import app
from app.volume_filters import compute_pullback_vol_decline, compute_vol_metrics


def test_volume_ratio_math() -> None:
    volumes = [10, 10, 10, 10, 10, 10, 10, 10, 10, 20]
    metrics = compute_vol_metrics(volumes, window_ma=10, window_ma5=5)
    assert metrics["vol_last"] == 20
    assert metrics["vol_ma10_last"] == 11
    assert metrics["vol_ratio"] == 20 / 11


def test_vol_ma5_slope() -> None:
    volumes = [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2]
    metrics = compute_vol_metrics(volumes, window_ma=10, window_ma5=5)
    assert metrics["vol_ma5_slope_pct"] is not None
    assert metrics["vol_ma5_slope_pct"] > 0


def test_vol_ma5_slope_insufficient() -> None:
    volumes = [1, 2, 3, 4, 5]
    metrics = compute_vol_metrics(volumes, window_ma=10, window_ma5=5)
    assert metrics["vol_ma5_slope_pct"] is None
    assert metrics["vol_ma5_slope_ok"] is False


def test_vol_ma5_slope_prev_zero() -> None:
    volumes = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
    metrics = compute_vol_metrics(volumes, window_ma=10, window_ma5=5)
    assert metrics["vol_ma5_slope_pct"] is None
    assert metrics["vol_ma5_slope_ok"] is False


def test_pullback_decline_true() -> None:
    volumes = [10, 9, 8, 7]
    assert compute_pullback_vol_decline(volumes, k=3) is True


def test_pullback_decline_false() -> None:
    volumes = [10, 9, 9, 7]
    assert compute_pullback_vol_decline(volumes, k=3) is False


class FakeIngest:
    def list_indicators(self, symbol: str, tf: str, limit: int = 10):
        return {
            "candles": [
                {"close_time": 1000, "volume": 10},
                {"close_time": 2000, "volume": 9},
                {"close_time": 3000, "volume": 8},
                {"close_time": 4000, "volume": 7},
                {"close_time": 5000, "volume": 6},
                {"close_time": 6000, "volume": 5},
                {"close_time": 7000, "volume": 4},
                {"close_time": 8000, "volume": 3},
                {"close_time": 9000, "volume": 2},
                {"close_time": 10000, "volume": 1},
            ]
        }

    def stop(self):
        return None


def test_volume_endpoint() -> None:
    with TestClient(app) as client:
        app.state.ingest = FakeIngest()
        resp = client.get("/api/volume/BTCUSDT/15m?k=3")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["symbol"] == "BTCUSDT"
        assert payload["tf"] == "15m"
        assert "vol_ratio" in payload
        assert "vol_ma5_slope_pct" in payload
        assert "pullback_vol_decline" in payload
