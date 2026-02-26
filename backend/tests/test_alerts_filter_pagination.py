import json

from fastapi.testclient import TestClient

from app.main import app
from app.storage import init_db, insert_alert_if_new


def _make_alert(symbol: str, alert_type: str, direction: str, level: float, time_ms: int) -> dict:
    return {
        "symbol": symbol,
        "tf": "15m",
        "type": alert_type,
        "direction": direction,
        "level": level,
        "time": time_ms,
        "entry": level + 1,
        "sl": level - 1,
        "sl_reason": "atr_stop",
        "hwc_bias": "bullish",
        "payload": {"type": alert_type, "context": {"vol_ma5_slope_ok": True}},
    }


def test_alerts_filter_pagination(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    init_db()

    insert_alert_if_new(_make_alert("BTCUSDT", "break", "long", 100.0, 1700000000000))
    insert_alert_if_new(_make_alert("ETHUSDT", "setup", "short", 200.0, 1700000000001))
    insert_alert_if_new(_make_alert("BTCUSDT", "fakeout", "long", 110.0, 1700000000002))

    with TestClient(app) as client:
        response = client.get("/api/alerts?symbol=BTCUSDT")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 2
        assert len(payload["items"]) == 2

        response = client.get("/api/alerts?type=setup")
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["symbol"] == "ETHUSDT"

        response = client.get("/api/alerts?limit=1&offset=1")
        payload = response.json()
        assert payload["total"] == 3
        assert len(payload["items"]) == 1
