import time

from app.storage import count_alerts, count_alerts_global, init_db, insert_alert_if_new, last_alert_time


def _make_alert(symbol: str, tf: str, alert_type: str, direction: str, level: float, time_ms: int) -> dict:
    return {
        "symbol": symbol,
        "tf": tf,
        "type": alert_type,
        "direction": direction,
        "level": level,
        "time": time_ms,
        "entry": level + 1,
        "sl": level - 1,
        "sl_reason": "atr_stop",
        "hwc_bias": "bullish",
        "payload": {"type": alert_type},
    }


def test_cooldown_and_rate_limit(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    init_db()

    base_time = 1700000000000
    alert = _make_alert("BTCUSDT", "15m", "break", "long", 100.0, base_time)
    inserted, _ = insert_alert_if_new(alert)
    assert inserted is True

    last_time = last_alert_time("BTCUSDT", "15m", "break", "long", 100.0)
    assert last_time == base_time
    cooldown_ms = 60 * 60 * 1000
    assert (base_time + 10 * 60 * 1000 - last_time) < cooldown_ms

    now_ms = int(time.time() * 1000)
    since_ms = now_ms - 60 * 60 * 1000
    for idx in range(6):
        insert_alert_if_new(_make_alert("ETHUSDT", "15m", "setup", "long", 200.0 + idx, base_time + idx + 1))

    assert count_alerts("ETHUSDT", since_ms) >= 6
    assert count_alerts_global(since_ms) >= 7
