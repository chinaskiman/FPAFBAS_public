import json

from app.storage import exists_alert, init_db, insert_alert_if_new, list_alerts


def test_insert_alert_dedup(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    init_db()

    alert = {
        "symbol": "BTCUSDT",
        "tf": "15m",
        "type": "break",
        "direction": "long",
        "level": 100.0,
        "time": 1700000000000,
        "entry": 101.0,
        "sl": 99.0,
        "sl_reason": "atr_stop",
        "hwc_bias": "bullish",
        "payload": {"foo": "bar"},
    }
    inserted, row = insert_alert_if_new(alert)
    assert inserted is True
    assert row is not None

    inserted_again, row_again = insert_alert_if_new(alert)
    assert inserted_again is False
    assert row_again is not None

    rows, total = list_alerts(limit=10)
    assert len(rows) == 1
    assert total == 1
    assert rows[0]["symbol"] == "BTCUSDT"


def test_exists_alert(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    init_db()
    assert exists_alert("BTCUSDT", "15m", "break", "long", 100.0, 1700000000000) is False

    alert = {
        "symbol": "BTCUSDT",
        "tf": "15m",
        "type": "break",
        "direction": "long",
        "level": 100.0,
        "time": 1700000000000,
        "entry": 101.0,
        "sl": 99.0,
        "sl_reason": "atr_stop",
        "hwc_bias": "bullish",
        "payload": {"foo": "bar"},
    }
    inserted, _ = insert_alert_if_new(alert)
    assert inserted is True
    assert exists_alert("BTCUSDT", "15m", "break", "long", 100.0, 1700000000000) is True
