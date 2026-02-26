import json

import pytest
from pydantic import ValidationError

from app.config import WatchlistConfig, get_watchlist_path, load_watchlist


def base_watchlist() -> dict:
    return {
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
                    "overrides": {"add": [42000.0], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }


def test_load_watchlist_success(monkeypatch, tmp_path) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(json.dumps(base_watchlist()), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))
    cfg = load_watchlist(get_watchlist_path())
    assert cfg.symbols
    assert cfg.global_.cooldown_minutes == 60


def test_invalid_entry_tf_rejected() -> None:
    data = base_watchlist()
    data["symbols"][0]["entry_tfs"] = ["5m"]
    with pytest.raises(ValidationError):
        WatchlistConfig.model_validate(data)


def test_invalid_cluster_tol_rejected() -> None:
    data = base_watchlist()
    data["symbols"][0]["levels"]["cluster_tol_pct"] = -0.1
    with pytest.raises(ValidationError):
        WatchlistConfig.model_validate(data)
