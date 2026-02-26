from fastapi.testclient import TestClient

from app.main import app
from app.storage import init_db, insert_alert_if_new


def test_alerts_export_csv(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
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
    insert_alert_if_new(alert)

    with TestClient(app) as client:
        response = client.get("/api/alerts/export.csv?limit=10", headers=headers)
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        lines = response.text.strip().splitlines()
        assert len(lines) >= 2
