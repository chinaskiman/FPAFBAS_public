import json

from fastapi.testclient import TestClient

from app.main import app


def _base_watchlist():
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "enabled": True,
                "entry_tfs": ["15m", "1h"],
                "setups": {"continuation": True, "retest": True, "fakeout": True, "setup_candle": True},
                "levels": {
                    "auto": True,
                    "max_levels": 12,
                    "cluster_tol_pct": 0.003,
                    "overrides": {"add": [], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }


def test_watchlist_put_add_update_remove(monkeypatch, tmp_path):
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(json.dumps(_base_watchlist()), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))

    with TestClient(app) as client:
        payload = _base_watchlist()
        payload["symbols"].append(
            {
                "symbol": "ethusdt",
                "enabled": True,
                "entry_tfs": ["15m", "4h"],
                "setups": {"continuation": True, "retest": True, "fakeout": True, "setup_candle": True},
                "levels": {
                    "auto": True,
                    "max_levels": 12,
                    "cluster_tol_pct": 0.003,
                    "overrides": {"add": [], "disable": []},
                },
            }
        )
        resp = client.put("/api/watchlist", json=payload)
        assert resp.status_code == 200
        data = client.get("/api/watchlist").json()
        symbols = [item["symbol"] for item in data["symbols"]]
        assert "ETHUSDT" in symbols

        payload = data
        for item in payload["symbols"]:
            if item["symbol"] == "ETHUSDT":
                item["entry_tfs"] = ["1h", "4h"]
        resp = client.put("/api/watchlist", json=payload)
        assert resp.status_code == 200
        data = client.get("/api/watchlist").json()
        eth = next(item for item in data["symbols"] if item["symbol"] == "ETHUSDT")
        assert eth["entry_tfs"] == ["1h", "4h"]

        payload = data
        payload["symbols"] = [item for item in payload["symbols"] if item["symbol"] != "ETHUSDT"]
        resp = client.put("/api/watchlist", json=payload)
        assert resp.status_code == 200
        data = client.get("/api/watchlist").json()
        symbols = [item["symbol"] for item in data["symbols"]]
        assert "ETHUSDT" not in symbols


def test_watchlist_put_invalid_symbol(monkeypatch, tmp_path):
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(json.dumps(_base_watchlist()), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))

    with TestClient(app) as client:
        payload = _base_watchlist()
        payload["symbols"].append(
            {
                "symbol": "ETH-USD",
                "enabled": True,
                "entry_tfs": ["15m"],
                "setups": {"continuation": True, "retest": True, "fakeout": True, "setup_candle": True},
                "levels": {
                    "auto": True,
                    "max_levels": 12,
                    "cluster_tol_pct": 0.003,
                    "overrides": {"add": [], "disable": []},
                },
            }
        )
        resp = client.put("/api/watchlist", json=payload)
        assert resp.status_code == 400
        assert "symbol" in resp.json().get("detail", "")
