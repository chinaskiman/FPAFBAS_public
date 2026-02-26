import json

from fastapi.testclient import TestClient

from app.main import app


def test_healthz_readyz(monkeypatch, tmp_path) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(
        json.dumps(
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
                            "max_levels": 12,
                            "cluster_tol_pct": 0.003,
                            "overrides": {"add": [], "disable": []},
                        },
                    }
                ],
                "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
            }
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))
    monkeypatch.setenv("SQLITE_PATH", str(db_path))

    with TestClient(app) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["ok"] is True

        ready = client.get("/readyz")
        assert ready.status_code == 200
        payload = ready.json()
        assert payload["db_ok"] is True
        assert payload["watchlist_ok"] is True
