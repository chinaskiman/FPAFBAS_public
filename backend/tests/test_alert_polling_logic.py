import json

from app.alert_poller import AlertPoller
from app.storage import init_db, list_alerts


class FakeIngest:
    pass


class FakeNotifier:
    def __init__(self) -> None:
        self.calls = []

    def send_alert(self, alert: dict):
        self.calls.append(alert)
        return True, None


def test_alert_polling_dedup(tmp_path, monkeypatch) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    watchlist = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "enabled": True,
                "entry_tfs": ["15m"],
                "setups": {
                    "continuation": True,
                    "retest": True,
                    "fakeout": True,
                    "setup_candle": True,
                },
                "levels": {
                    "auto": True,
                    "max_levels": 5,
                    "cluster_tol_pct": 0.01,
                    "overrides": {"add": [100.0], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }
    watchlist_path.write_text(json.dumps(watchlist), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))

    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    init_db()

    def fake_build_openings(_ingest, _config, _symbol, _tf, limit=300):
        return {
            "symbol": "BTCUSDT",
            "tf": "15m",
            "hwc_bias": "bullish",
            "last_candle_time": 1700000000000,
            "signals": [
                {
                    "type": "break",
                    "level": 100.0,
                    "direction": "long",
                    "time": 1700000000000,
                    "entry": 101.0,
                    "sl": 99.0,
                    "sl_reason": "atr_stop",
                    "context": {
                        "vol_ma5_slope_ok": True,
                        "pullback_vol_decline": True,
                        "not_at_peak_long": True,
                        "rsi_distance": 20.0,
                    },
                }
            ],
        }

    monkeypatch.setattr("app.alert_poller.build_openings", fake_build_openings)

    notifier = FakeNotifier()
    poller = AlertPoller(ingest=FakeIngest(), notifier=notifier, poll_seconds=1)

    scan_count, new_alerts, suppressed_new, last_error = poller.run_once()
    assert scan_count == 1
    assert new_alerts == 1
    assert suppressed_new == 0
    assert last_error is None

    scan_count, new_alerts, suppressed_new, last_error = poller.run_once()
    assert scan_count == 1
    assert new_alerts == 0
    assert suppressed_new == 0

    rows, total = list_alerts(limit=10)
    assert len(rows) == 1
    assert total == 1
    assert len(notifier.calls) == 1
