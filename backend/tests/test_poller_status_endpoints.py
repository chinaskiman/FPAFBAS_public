from fastapi.testclient import TestClient

from app.main import app


def test_poller_status_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        response = client.get("/api/poller/status", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        for key in (
            "is_running",
            "mode",
            "started_at",
            "last_tick_at",
            "last_scan_at",
            "last_scan_count",
            "last_new_alerts",
            "last_suppressed_new_alerts",
            "last_error",
        ):
            assert key in payload

        pause = client.post("/api/poller/pause", headers=headers)
        assert pause.status_code == 200
        assert pause.json()["mode"] == "pause_all"

        resume = client.post("/api/poller/resume", headers=headers)
        assert resume.status_code == 200
        assert resume.json()["mode"] == "run"

        mode = client.post("/api/poller/mode", json={"mode": "pause_new"}, headers=headers)
        assert mode.status_code == 200
        assert mode.json()["mode"] == "pause_new"
