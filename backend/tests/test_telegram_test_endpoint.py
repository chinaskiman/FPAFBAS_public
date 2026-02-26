from fastapi.testclient import TestClient

from app.main import app


class FakeNotifier:
    def __init__(self) -> None:
        self.sent_text = None

    def send_telegram(self, text: str):
        self.sent_text = text
        return True, None


def test_telegram_test_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    with TestClient(app) as client:
        fake = FakeNotifier()
        app.state.notifier = fake
        response = client.post("/api/telegram/test", json={"text": "hello"}, headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["sent_text"] == "hello"
        assert fake.sent_text == "hello"
