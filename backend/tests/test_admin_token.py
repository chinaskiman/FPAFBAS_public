from fastapi.testclient import TestClient

from app.main import app


def test_admin_token_missing(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with TestClient(app) as client:
        response = client.get("/api/poller/status")
        assert response.status_code == 503
        assert "ADMIN_TOKEN" in response.json().get("detail", "")


def test_admin_token_required(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    with TestClient(app) as client:
        response = client.get("/api/poller/status")
        assert response.status_code == 401

        response = client.get("/api/poller/status", headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401

        response = client.get("/api/poller/status", headers={"Authorization": "Bearer secret"})
        assert response.status_code == 200
