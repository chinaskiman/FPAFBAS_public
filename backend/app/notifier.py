import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_MAX_MESSAGE_CHARS = 4096


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _split_message(text: str, max_chars: int = _MAX_MESSAGE_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for idx in range(0, len(line), max_chars):
                chunks.append(line[idx : idx + max_chars])
            continue
        if len(current) + len(line) > max_chars:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


def _extract_retry_after_seconds(payload: object) -> Optional[float]:
    if not isinstance(payload, dict):
        return None
    params = payload.get("parameters")
    if not isinstance(params, dict):
        return None
    value = params.get("retry_after")
    try:
        retry_after = float(value)
    except (TypeError, ValueError):
        return None
    if retry_after < 0:
        return None
    return retry_after


def _to_float(value: object) -> Optional[float]:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN check
        return None
    return num


def _fmt_num(value: object, digits: int = 2) -> str:
    num = _to_float(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def _fmt_pct(value: object, digits: int = 2) -> str:
    num = _to_float(value)
    if num is None:
        return "-"
    return f"{num * 100:.{digits}f}%"


def _fmt_bool(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "-"


def _fmt_time_ms(value: object) -> str:
    ms = _to_float(value)
    if ms is None:
        return "-"
    try:
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return str(int(ms))
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} UTC ({int(ms)})"


class TelegramNotifier:
    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_base_seconds: Optional[float] = None,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: Optional[bool] = None,
        message_thread_id: Optional[int] = None,
    ) -> None:
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        enabled_flag = os.getenv("TELEGRAM_ENABLED")
        if enabled_flag is None:
            self.enabled = bool(self.token and self.chat_id)
        else:
            self.enabled = enabled_flag.strip().lower() in {"1", "true", "yes", "on"}
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else _env_float("TELEGRAM_TIMEOUT_SECONDS", 10.0)
        )
        retries = max_retries if max_retries is not None else _env_int("TELEGRAM_MAX_RETRIES", 2)
        self.max_retries = max(0, retries)
        backoff = retry_base_seconds if retry_base_seconds is not None else _env_float("TELEGRAM_RETRY_BASE_SECONDS", 1.0)
        self.retry_base_seconds = max(0.0, backoff)
        self.retry_max_seconds = max(0.0, _env_float("TELEGRAM_RETRY_MAX_SECONDS", 30.0))
        parse_mode_env = os.getenv("TELEGRAM_PARSE_MODE", "").strip()
        parse_mode_value = parse_mode if parse_mode is not None else parse_mode_env
        self.parse_mode = parse_mode_value or None
        if disable_web_page_preview is None:
            preview_default = _env_bool("TELEGRAM_DISABLE_WEB_PAGE_PREVIEW", True)
            self.disable_web_page_preview = preview_default
        else:
            self.disable_web_page_preview = disable_web_page_preview
        if message_thread_id is not None:
            self.message_thread_id = message_thread_id
        else:
            raw_thread = os.getenv("TELEGRAM_MESSAGE_THREAD_ID")
            try:
                self.message_thread_id = int(raw_thread) if raw_thread else None
            except ValueError:
                self.message_thread_id = None

    def send_alert(self, alert: dict) -> Tuple[bool, Optional[str]]:
        message = format_alert_message(alert)
        return self.send_telegram(message)

    def send_telegram(self, text: str) -> Tuple[bool, Optional[str]]:
        if not self.enabled:
            return False, "Telegram disabled (TELEGRAM_ENABLED=false)"
        if not self.token or not self.chat_id:
            return False, "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
        clean_text = str(text or "").strip()
        if not clean_text:
            return False, "Message text is empty"
        chunks = _split_message(clean_text)
        for idx, chunk in enumerate(chunks):
            ok, error = self._send_chunk(chunk)
            if not ok:
                if len(chunks) > 1 and error:
                    return False, f"chunk {idx + 1}/{len(chunks)} failed: {error}"
                return False, error
        return True, None

    def _send_chunk(self, text: str) -> Tuple[bool, Optional[str]]:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        attempts = self.max_retries + 1
        last_error: Optional[str] = None

        for attempt in range(1, attempts + 1):
            payload = {"chat_id": self.chat_id, "text": text}
            if self.parse_mode:
                payload["parse_mode"] = self.parse_mode
            payload["disable_web_page_preview"] = self.disable_web_page_preview
            if self.message_thread_id is not None:
                payload["message_thread_id"] = self.message_thread_id
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.Timeout as exc:
                last_error = f"telegram_timeout: {exc}"
                if attempt < attempts:
                    self._sleep_backoff(attempt)
                    continue
                logger.error("Telegram send failed: %s", last_error)
                return False, last_error
            except requests.RequestException as exc:
                last_error = f"telegram_request_error: {exc}"
                if attempt < attempts:
                    self._sleep_backoff(attempt)
                    continue
                logger.error("Telegram send failed: %s", last_error)
                return False, last_error

            ok, error, retry_after = self._handle_response(response)
            if ok:
                return True, None

            last_error = error or "Telegram send failed"
            retryable = response.status_code in _RETRYABLE_STATUS_CODES
            if retryable and attempt < attempts:
                if retry_after is not None:
                    self._sleep_seconds(retry_after)
                else:
                    self._sleep_backoff(attempt)
                continue
            logger.error("Telegram send failed: %s", last_error)
            return False, last_error

        logger.error("Telegram send failed: %s", last_error)
        return False, last_error or "Telegram send failed"

    def _sleep_backoff(self, attempt: int) -> None:
        seconds = self.retry_base_seconds * (2 ** max(0, attempt - 1))
        if self.retry_max_seconds > 0:
            seconds = min(seconds, self.retry_max_seconds)
        self._sleep_seconds(seconds)

    @staticmethod
    def _sleep_seconds(seconds: float) -> None:
        if seconds <= 0:
            return
        time.sleep(seconds)

    @staticmethod
    def _handle_response(response: requests.Response) -> Tuple[bool, Optional[str], Optional[float]]:
        payload = None
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if 200 <= response.status_code < 300:
            if isinstance(payload, dict) and payload.get("ok") is False:
                description = str(payload.get("description") or "Telegram API error")
                retry_after = _extract_retry_after_seconds(payload)
                return False, f"telegram_api_error: {description}", retry_after
            return True, None, None

        description = None
        if isinstance(payload, dict):
            description = payload.get("description")
        if not description:
            description = (response.text or "").strip() or f"HTTP {response.status_code}"
        retry_after = _extract_retry_after_seconds(payload)
        return False, f"telegram_http_{response.status_code}: {description}", retry_after


def format_alert_message(alert: dict) -> str:
    payload = alert.get("payload") or {}
    context = alert.get("context") or payload.get("context") or {}

    signal_type = str(alert.get("type") or payload.get("type") or "-").upper()
    symbol = str(alert.get("symbol") or payload.get("symbol") or "-")
    tf = str(alert.get("tf") or payload.get("tf") or "-")
    direction = str(alert.get("direction") or payload.get("direction") or "-").lower()
    direction_tag = direction.upper() if direction in {"long", "short"} else "-"

    level = alert.get("level", payload.get("level"))
    entry = _to_float(alert.get("entry", payload.get("entry")))
    sl = _to_float(alert.get("sl", payload.get("sl")))
    sl_reason = str(alert.get("sl_reason", payload.get("sl_reason")) or "-")
    time_ms = alert.get("time", payload.get("time"))

    weekly_bias = str(context.get("weekly_bias") or alert.get("weekly_bias") or payload.get("weekly_bias") or "-")
    daily_bias = str(context.get("daily_bias") or alert.get("daily_bias") or payload.get("daily_bias") or "-")
    hwc_bias = str(context.get("hwc_bias") or alert.get("hwc_bias") or payload.get("hwc_bias") or "-")

    if direction == "long":
        di_ok = context.get("not_at_peak_long")
    elif direction == "short":
        di_ok = context.get("not_at_peak_short")
    else:
        di_ok = None
    vol_ok = context.get("vol_ma5_slope_ok")
    pullback_ok = context.get("pullback_vol_decline")
    rsi_distance = context.get("rsi_distance")
    atr_stop_distance = context.get("atr_stop_distance")

    risk = abs(entry - sl) if entry is not None and sl is not None else None
    risk_pct = (risk / abs(entry)) if risk is not None and entry not in (None, 0.0) else None
    rr2 = None
    if entry is not None and risk is not None:
        if direction == "long":
            rr2 = entry + risk * 2
        elif direction == "short":
            rr2 = entry - risk * 2

    parts = []
    parts.append(f"{signal_type} {direction_tag} | {symbol} {tf}")
    parts.append(f"Time: {_fmt_time_ms(time_ms)}")
    if level is not None:
        parts.append(f"Level: {_fmt_num(level)}")

    price_bits = [f"Entry: {_fmt_num(entry)}", f"SL: {_fmt_num(sl)}", f"SL reason: {sl_reason}"]
    parts.append(" | ".join(price_bits))

    if risk is not None:
        parts.append(f"Risk (1R): {_fmt_num(risk)} ({_fmt_pct(risk_pct)}) | TP@2R: {_fmt_num(rr2)}")
    else:
        parts.append("Risk (1R): - | TP@2R: -")

    parts.append(f"Bias: W {weekly_bias} | D {daily_bias} | HWC {hwc_bias}")
    parts.append(
        "Checks: "
        f"VOL_OK={_fmt_bool(vol_ok)} | "
        f"DI_OK={_fmt_bool(di_ok)} | "
        f"PULLBACK_VOL={_fmt_bool(pullback_ok)}"
    )

    indicator_bits = []
    if _to_float(rsi_distance) is not None:
        indicator_bits.append(f"RSI distance: {_fmt_num(rsi_distance)}")
    if _to_float(atr_stop_distance) is not None:
        indicator_bits.append(f"ATR stop distance: {_fmt_num(atr_stop_distance)}")
    if indicator_bits:
        parts.append("Indicators: " + " | ".join(indicator_bits))

    return "\n".join(parts)
