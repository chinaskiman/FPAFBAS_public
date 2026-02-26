from fastapi.testclient import TestClient

from app.main import app
from app.storage import init_db, insert_alert_if_new


def test_alert_get_by_id(tmp_path, monkeypatch) -> None:
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
        "payload": {"context": {"vol_ma5_slope_ok": True}},
    }
    inserted, row = insert_alert_if_new(alert)
    assert inserted is True
    assert row is not None

    with TestClient(app) as client:
        response = client.get(f"/api/alerts/{row['id']}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == row["id"]
        assert "payload" in payload
