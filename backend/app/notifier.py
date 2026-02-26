import logging
import os
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def send_alert(self, alert: dict) -> Tuple[bool, Optional[str]]:
        message = format_alert_message(alert)
        return self.send_telegram(message)

    def send_telegram(self, text: str) -> Tuple[bool, Optional[str]]:
        if not self.token or not self.chat_id:
            return False, "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            )
            response.raise_for_status()
            return True, None
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram send failed: %s", exc)
            return False, str(exc)


def format_alert_message(alert: dict) -> str:
    parts = []
    parts.append(
        f"[{alert.get('type', '').upper()}] {alert.get('symbol')} {alert.get('tf')} {alert.get('direction')}"
    )
    if alert.get("level") is not None:
        parts.append(f"Level: {alert.get('level')}")
    parts.append(f"Entry: {alert.get('entry')}  SL: {alert.get('sl')} ({alert.get('sl_reason')})")
    if alert.get("time") is not None:
        parts.append(f"Time: {alert.get('time')}")
    if alert.get("hwc_bias") is not None:
        parts.append(f"HWC: {alert.get('hwc_bias')}")
    context = alert.get("context") or {}
    badges = []
    if context.get("vol_ma5_slope_ok") is True:
        badges.append("VOL_OK")
    if alert.get("direction") == "long" and context.get("not_at_peak_long") is True:
        badges.append("DI_OK")
    if alert.get("direction") == "short" and context.get("not_at_peak_short") is True:
        badges.append("DI_OK")
    if badges:
        parts.append(" ".join(badges))
    return "\n".join(parts)
