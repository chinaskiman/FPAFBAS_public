from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from .config import load_watchlist
from .openings import build_openings
from .quality_controls import score_signal, should_suppress_due_to_quiet_hours
from .journal import build_journal_record
from .notifier import format_alert_message
from .storage import (
    count_alerts,
    count_alerts_global,
    exists_alert,
    insert_alert_if_new,
    last_alert_time,
    mark_notified,
)

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class PollerState:
    is_running: bool = False
    mode: str = "run"
    started_at: Optional[int] = None
    last_tick_at: Optional[int] = None
    last_scan_at: Optional[int] = None
    last_scan_count: int = 0
    last_new_alerts: int = 0
    last_suppressed_new_alerts: int = 0
    last_error: Optional[str] = None
    lock_acquired: bool = False
    lock_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "is_running": self.is_running,
            "mode": self.mode,
            "started_at": self.started_at,
            "last_tick_at": self.last_tick_at,
            "last_scan_at": self.last_scan_at,
            "last_scan_count": self.last_scan_count,
            "last_new_alerts": self.last_new_alerts,
            "last_suppressed_new_alerts": self.last_suppressed_new_alerts,
            "last_error": self.last_error,
            "lock_acquired": self.lock_acquired,
            "lock_path": self.lock_path,
        }


class AlertPoller:
    def __init__(
        self,
        ingest,
        notifier,
        journal=None,
        forward_tester=None,
        poll_seconds: int = 15,
        start_paused: bool = False,
        start_mode: str | None = None,
    ) -> None:
        self.ingest = ingest
        self.notifier = notifier
        self.journal = journal
        self.forward_tester = forward_tester
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        if start_mode:
            mode = start_mode
        else:
            mode = "pause_all" if start_paused else "run"
        if mode not in {"run", "pause_new", "pause_all"}:
            mode = "run"
        self.state = PollerState(mode=mode)
        self._suppressed_log: deque[dict] = deque(maxlen=200)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.state.started_at = _now_ms()
        self.state.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="alert-poller")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.state.is_running = False

    def pause(self) -> None:
        self.set_mode("pause_all")

    def resume(self) -> None:
        self.set_mode("run")

    def set_mode(self, mode: str) -> None:
        if mode not in {"run", "pause_new", "pause_all"}:
            raise ValueError("Invalid poller mode")
        self.state.mode = mode

    def list_suppressed(self, limit: int = 50) -> list[dict]:
        if limit <= 0:
            return []
        items = list(self._suppressed_log)
        return items[-limit:]

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.state.last_tick_at = _now_ms()
            if self.state.mode == "pause_all":
                self._process_forward_only()
                self._stop_event.wait(self.poll_seconds)
                continue
            try:
                scan_count, new_alerts, suppressed_new, last_error = self.run_once(mode=self.state.mode)
                self.state.last_scan_at = _now_ms()
                self.state.last_scan_count = scan_count
                self.state.last_new_alerts = new_alerts
                self.state.last_suppressed_new_alerts = suppressed_new
                self.state.last_error = last_error
            except Exception as exc:  # noqa: BLE001
                logger.exception("Alert poller tick failed: %s", exc)
                self.state.last_error = str(exc)
            self._stop_event.wait(self.poll_seconds)
        self.state.is_running = False

    def _process_forward_only(self) -> None:
        if self.ingest is None or self.forward_tester is None:
            return
        try:
            config = load_watchlist()
        except Exception as exc:  # noqa: BLE001
            logger.error("Forward tester watchlist load failed: %s", exc)
            return
        for symbol_cfg in config.symbols:
            if not symbol_cfg.enabled:
                continue
            for tf in symbol_cfg.entry_tfs:
                try:
                    self.forward_tester.process_symbol_tf(self.ingest, symbol_cfg.symbol, tf)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Forward tester processing failed for %s %s: %s", symbol_cfg.symbol, tf, exc)

    def run_once(self, mode: str = "run") -> tuple[int, int, int, Optional[str]]:
        if self.ingest is None:
            return 0, 0, 0, "Ingest service not initialized"
        config = load_watchlist()
        settings = config.quality
        now_ms = _now_ms()
        window_start = now_ms - 60 * 60 * 1000
        scan_count = 0
        new_alerts = 0
        suppressed_new = 0
        last_error: Optional[str] = None
        seen_keys = set()
        symbol_counts = {}
        global_count = count_alerts_global(window_start)
        for symbol_cfg in config.symbols:
            if not symbol_cfg.enabled:
                continue
            symbol = symbol_cfg.symbol
            if symbol not in symbol_counts:
                symbol_counts[symbol] = count_alerts(symbol, window_start)
            for tf in symbol_cfg.entry_tfs:
                if self.forward_tester is not None:
                    try:
                        self.forward_tester.process_symbol_tf(self.ingest, symbol, tf)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Forward tester processing failed for %s %s: %s", symbol, tf, exc)
                scan_count += 1
                try:
                    openings = build_openings(self.ingest, config, symbol, tf, limit=300)
                except Exception as exc:  # noqa: BLE001
                    last_error = f"Openings build failed for {symbol} {tf}: {exc}"
                    logger.error(last_error)
                    continue
                for signal in openings.get("signals", []):
                    alert = _signal_to_alert(openings, signal)
                    key = (
                        alert["symbol"],
                        alert["tf"],
                        alert["type"],
                        alert["direction"],
                        alert.get("level"),
                        alert["time"],
                    )
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    score, _badges, reasons = score_signal(signal)
                    min_score = settings.min_score_by_type.get(alert["type"], 0)
                    if score < min_score:
                        self._record_suppressed(
                            now_ms,
                            alert,
                            score,
                            "min_score",
                            reasons + [f"min_required={min_score}"],
                        )
                        continue
                    cooldown_minutes = settings.cooldown_minutes_by_type.get(alert["type"], 0)
                    if cooldown_minutes > 0:
                        last_time = last_alert_time(
                            alert["symbol"],
                            alert["tf"],
                            alert["type"],
                            alert["direction"],
                            alert.get("level"),
                        )
                        if last_time is not None and (alert["time"] - last_time) < cooldown_minutes * 60 * 1000:
                            self._record_suppressed(
                                now_ms,
                                alert,
                                score,
                                "cooldown",
                                reasons + [f"last_time={last_time}"],
                            )
                            continue
                    if symbol_counts[symbol] >= settings.max_alerts_per_symbol_per_hour:
                        self._record_suppressed(
                            now_ms,
                            alert,
                            score,
                            "symbol_rate_limit",
                            reasons + [f"count={symbol_counts[symbol]}"],
                        )
                        continue
                    if global_count >= settings.max_alerts_global_per_hour:
                        self._record_suppressed(
                            now_ms,
                            alert,
                            score,
                            "global_rate_limit",
                            reasons + [f"count={global_count}"],
                        )
                        continue
                    if mode == "pause_new":
                        if not exists_alert(*key):
                            suppressed_new += 1
                            self._record_suppressed(
                                now_ms,
                                alert,
                                score,
                                "pause_new",
                                reasons,
                            )
                        continue
                    inserted, row = insert_alert_if_new(alert)
                    if not inserted or not row:
                        continue
                    if self.forward_tester is not None:
                        try:
                            alert_for_forward = {**alert, "id": row["id"]}
                            self.forward_tester.register_signal(alert_for_forward, signal_payload=signal)
                        except Exception as exc:  # noqa: BLE001
                            logger.error("Forward tester signal registration failed: %s", exc)
                    self._journal_signal(openings, signal, alert)
                    new_alerts += 1
                    symbol_counts[symbol] += 1
                    global_count += 1
                    if should_suppress_due_to_quiet_hours(now_ms, settings):
                        mark_notified(row["id"], False, "suppressed:quiet_hours")
                        self._record_suppressed(
                            now_ms,
                            alert,
                            score,
                            "quiet_hours",
                            reasons,
                        )
                        continue
                    ok, error = self.notifier.send_alert(alert)
                    if not ok:
                        last_error = error or "Telegram send failed"
                    mark_notified(row["id"], ok, error)
        return scan_count, new_alerts, suppressed_new, last_error

    def _journal_signal(self, openings: dict, signal: dict, alert: dict) -> None:
        if self.journal is None or self.ingest is None:
            return
        try:
            cache = self.ingest.get_cache(alert["symbol"], alert["tf"])
            candles = cache.list_all() if cache else []
            signal_time = signal.get("time")
            if signal_time:
                candles = [candle for candle in candles if candle.close_time <= signal_time]
            notification = {
                "channel": "telegram",
                "message": format_alert_message(alert),
            }
            strategy_id = os.getenv("STRATEGY_ID", "default")
            strategy_version = os.getenv("STRATEGY_VERSION", "1")
            record = build_journal_record(
                openings=openings,
                signal=signal,
                candles=candles,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                notification=notification,
                now_ms=_now_ms(),
            )
            self.journal.insert_record(record)
        except Exception as exc:  # noqa: BLE001
            logger.error("Journal write failed: %s", exc)

    def _record_suppressed(
        self, now_ms: int, alert: dict, score: int, reason: str, details: list[str]
    ) -> None:
        self._suppressed_log.append(
            {
                "time": now_ms,
                "symbol": alert.get("symbol"),
                "tf": alert.get("tf"),
                "type": alert.get("type"),
                "direction": alert.get("direction"),
                "level": alert.get("level"),
                "signal_time": alert.get("time"),
                "score": score,
                "reason": reason,
                "details": details,
            }
        )


def _signal_to_alert(openings: dict, signal: dict) -> dict:
    return {
        "symbol": openings["symbol"],
        "tf": openings["tf"],
        "type": signal["type"],
        "direction": signal["direction"],
        "level": signal.get("level"),
        "time": signal["time"],
        "entry": signal.get("entry"),
        "sl": signal.get("sl"),
        "sl_reason": signal.get("sl_reason"),
        "hwc_bias": openings.get("hwc_bias"),
        "context": signal.get("context"),
        "payload": signal,
    }
