import json

from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.main import app


class FakeIngest:
    def __init__(self, cache: CandleCache):
        self._cache = cache

    def get_cache(self, symbol: str, tf: str):
        if symbol.upper() == "BTCUSDT" and tf == "1h":
            return self._cache
        return None


def _make_watchlist(path) -> None:
    payload = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "enabled": True,
                "entry_tfs": ["1h"],
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
                    "overrides": {"add": [], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_forward_test_status_summary_and_mode(tmp_path, monkeypatch) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    db_path = tmp_path / "app.db"
    _make_watchlist(watchlist_path)
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("ADMIN_TOKEN", "dev-token")

    with TestClient(app) as client:
        status = client.get("/api/forward_test/status")
        assert status.status_code == 200
        assert status.json()["enabled"] is True

        summary = client.get("/api/forward_test/summary")
        assert summary.status_code == 200
        assert "metrics" in summary.json()

        pause = client.post(
            "/api/forward_test/mode",
            json={"enabled": False},
            headers={"Authorization": "Bearer dev-token"},
        )
        assert pause.status_code == 200
        assert pause.json()["enabled"] is False

        run = client.post(
            "/api/forward_test/mode",
            json={"enabled": True},
            headers={"Authorization": "Bearer dev-token"},
        )
        assert run.status_code == 200
        assert run.json()["enabled"] is True


def test_forward_test_registers_and_closes_trade(tmp_path, monkeypatch) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    db_path = tmp_path / "app.db"
    _make_watchlist(watchlist_path)
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))
    monkeypatch.setenv("SQLITE_PATH", str(db_path))

    cache = CandleCache(maxlen=20)
    candles = [
        Candle(0, 59_999, 100.0, 101.0, 99.0, 100.0, 1.0),
        Candle(60_000, 119_999, 100.0, 104.5, 99.8, 103.0, 1.0),
        Candle(120_000, 179_999, 103.0, 104.0, 102.0, 103.5, 1.0),
    ]
    cache.extend(candles)
    ingest = FakeIngest(cache)

    with TestClient(app):
        service = app.state.forward_test
        signal = {
            "id": 1,
            "symbol": "BTCUSDT",
            "tf": "1h",
            "type": "break",
            "direction": "long",
            "time": 59_999,
            "entry": 100.0,
            "sl": 99.0,
            "hwc_bias": "bullish",
        }
        created = service.register_signal(signal)
        assert created is not None

        service.process_symbol_tf(ingest, "BTCUSDT", "1h")
        summary = service.get_summary()
        assert summary["metrics"]["total_trades"] >= 1
