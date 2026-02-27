from __future__ import annotations

from app.notifier import TelegramNotifier, format_alert_message


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_telegram_disabled_env(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    notifier = TelegramNotifier(token="token", chat_id="chat")
    ok, error = notifier.send_telegram("hello")
    assert ok is False
    assert "Telegram disabled" in str(error)


def test_telegram_retries_on_transient_http_error(monkeypatch) -> None:
    calls = []

    def fake_post(_url, json=None, timeout=None):  # noqa: ANN001
        calls.append({"json": json, "timeout": timeout})
        if len(calls) == 1:
            return _FakeResponse(
                429,
                payload={"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 0}},
            )
        return _FakeResponse(200, payload={"ok": True, "result": {"message_id": 1}})

    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.setattr("app.notifier.requests.post", fake_post)
    notifier = TelegramNotifier(token="token", chat_id="chat", max_retries=1, retry_base_seconds=0)
    ok, error = notifier.send_telegram("hello")
    assert ok is True
    assert error is None
    assert len(calls) == 2


def test_telegram_splits_long_messages(monkeypatch) -> None:
    chunks = []

    def fake_post(_url, json=None, timeout=None):  # noqa: ANN001
        chunks.append((json or {}).get("text"))
        return _FakeResponse(200, payload={"ok": True})

    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.setattr("app.notifier.requests.post", fake_post)
    notifier = TelegramNotifier(token="token", chat_id="chat", max_retries=0)
    long_text = "x" * 5000
    ok, error = notifier.send_telegram(long_text)
    assert ok is True
    assert error is None
    assert len(chunks) == 2
    assert all(chunk is not None and len(chunk) <= 4096 for chunk in chunks)


def test_telegram_surfaces_api_description(monkeypatch) -> None:
    def fake_post(_url, json=None, timeout=None):  # noqa: ANN001
        return _FakeResponse(400, payload={"ok": False, "description": "Bad Request: chat not found"})

    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.setattr("app.notifier.requests.post", fake_post)
    notifier = TelegramNotifier(token="token", chat_id="chat", max_retries=0)
    ok, error = notifier.send_telegram("hello")
    assert ok is False
    assert error is not None
    assert "chat not found" in error


def test_format_alert_message_contains_risk_bias_and_checks() -> None:
    alert = {
        "type": "break",
        "symbol": "BTCUSDT",
        "tf": "15m",
        "direction": "long",
        "level": 67000.0,
        "time": 1700000000000,
        "entry": 67100.0,
        "sl": 66800.0,
        "sl_reason": "atr_stop",
        "hwc_bias": "bullish",
        "context": {
            "weekly_bias": "bullish",
            "daily_bias": "neutral",
            "hwc_bias": "bullish",
            "vol_ma5_slope_ok": True,
            "pullback_vol_decline": False,
            "not_at_peak_long": True,
            "rsi_distance": 8.2,
            "atr_stop_distance": 300.0,
        },
    }
    text = format_alert_message(alert)
    assert "BREAK LONG | BTCUSDT 15m" in text
    assert "Risk (1R): 300.00 (0.45%) | TP@2R: 67700.00" in text
    assert "Bias: W bullish | D neutral | HWC bullish" in text
    assert "Checks: VOL_OK=yes | DI_OK=yes | PULLBACK_VOL=no" in text
    assert "Chart:" not in text
    assert "Exchange:" not in text
