from __future__ import annotations

import csv
import io
import math
import os
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests

from .storage import get_db_path

DEFAULT_STARTING_EQUITY = float(os.getenv("FT_STARTING_EQUITY", "10000"))
DEFAULT_LEVERAGE = float(os.getenv("FT_LEVERAGE", "20"))
DEFAULT_RISK_PCT = float(os.getenv("FT_RISK_PCT", "0.01"))
DEFAULT_MAX_POSITIONS = int(os.getenv("FT_MAX_POSITIONS", "3"))
DEFAULT_FEE_RATE = float(os.getenv("FT_FEE_RATE", "0.001"))
DEFAULT_TP_R = float(os.getenv("FT_TP_R", "2.0"))
DEFAULT_CANCEL_AFTER_CANDLES = int(os.getenv("FT_CANCEL_AFTER_CANDLES", "3"))
DEFAULT_RISK_FREE_RATE = float(os.getenv("FT_RISK_FREE_RATE", "0.02"))
DEFAULT_TIMEZONE = os.getenv("FT_TIMEZONE", "Europe/Berlin")
DEFAULT_REST_BASE = os.getenv("BINANCE_FAPI_REST", "https://fapi.binance.com")
DEFAULT_MAINT_MARGIN_RATE = float(os.getenv("FT_MAINT_MARGIN_RATE", "0.004"))

ALLOWED_SIGNAL_TYPES = {"break", "setup", "fakeout"}
TRENDING_BIASES = {"bullish", "bearish"}
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS forward_test_run (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    start_time INTEGER NOT NULL,
    starting_equity REAL NOT NULL,
    cash_balance REAL NOT NULL,
    peak_equity REAL NOT NULL,
    leverage REAL NOT NULL,
    risk_pct REAL NOT NULL,
    max_positions INTEGER NOT NULL,
    fee_rate REAL NOT NULL,
    tp_r REAL NOT NULL,
    cancel_after_candles INTEGER NOT NULL,
    risk_free_rate REAL NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forward_test_cursor (
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    last_candle_time INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, tf)
);

CREATE TABLE IF NOT EXISTS forward_test_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NOT NULL,
    alert_id INTEGER,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    bias TEXT,
    regime TEXT NOT NULL,
    signal_time INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    sl_price REAL NOT NULL,
    tp_price REAL NOT NULL,
    risk_amount REAL NOT NULL,
    quantity REAL NOT NULL,
    notional REAL NOT NULL,
    margin_required REAL NOT NULL,
    leverage REAL NOT NULL,
    candles_waited INTEGER NOT NULL DEFAULT 0,
    cancel_after_candles INTEGER NOT NULL,
    status TEXT NOT NULL,
    status_reason TEXT,
    filled_at INTEGER,
    filled_price REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_forward_test_orders_alert_id
ON forward_test_orders(alert_id)
WHERE alert_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_forward_test_orders_status
ON forward_test_orders(status, symbol, tf);

CREATE TABLE IF NOT EXISTS forward_test_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    bias TEXT,
    regime TEXT NOT NULL,
    entry_time INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    sl_price REAL NOT NULL,
    tp_price REAL NOT NULL,
    quantity REAL NOT NULL,
    notional REAL NOT NULL,
    margin_required REAL NOT NULL,
    leverage REAL NOT NULL,
    equity_at_entry REAL NOT NULL,
    risk_amount REAL NOT NULL,
    fee_entry REAL NOT NULL,
    funding_cost REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    exit_time INTEGER,
    exit_price REAL,
    exit_reason TEXT,
    fee_exit REAL,
    gross_pnl REAL,
    net_pnl REAL,
    roe_pct REAL,
    mae_r REAL NOT NULL DEFAULT 0,
    mfe_r REAL NOT NULL DEFAULT 0,
    mae_abs REAL NOT NULL DEFAULT 0,
    mfe_abs REAL NOT NULL DEFAULT 0,
    liquidation_price REAL NOT NULL,
    liq_distance_entry_pct REAL NOT NULL,
    liq_distance_min_pct REAL NOT NULL,
    holding_candles INTEGER NOT NULL DEFAULT 0,
    mark_price REAL NOT NULL,
    last_mark_time INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_forward_test_positions_status
ON forward_test_positions(status, symbol, tf);

CREATE TABLE IF NOT EXISTS forward_test_equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time INTEGER NOT NULL,
    equity REAL NOT NULL,
    cash_balance REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    margin_used REAL NOT NULL,
    open_positions INTEGER NOT NULL,
    pending_orders INTEGER NOT NULL,
    drawdown_abs REAL NOT NULL,
    drawdown_pct REAL NOT NULL,
    exposure_flag INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_forward_test_equity_time
ON forward_test_equity(time DESC);

CREATE TABLE IF NOT EXISTS forward_test_funding_rates (
    symbol TEXT NOT NULL,
    funding_time INTEGER NOT NULL,
    funding_rate REAL NOT NULL,
    PRIMARY KEY(symbol, funding_time)
);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _connect() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _gross_pnl(direction: str, entry: float, exit_price: float, qty: float) -> float:
    if direction == "long":
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def _compute_liquidation_price(entry: float, direction: str, leverage: float) -> float:
    lev = max(leverage, 1.0)
    if direction == "long":
        liq = entry * (1.0 - 1.0 / lev + DEFAULT_MAINT_MARGIN_RATE)
    else:
        liq = entry * (1.0 + 1.0 / lev - DEFAULT_MAINT_MARGIN_RATE)
    return max(liq, 0.0)


def _regime_from_bias(bias: str | None) -> str:
    if bias in TRENDING_BIASES:
        return "trending"
    return "ranging"


def init_forward_test_db() -> None:
    conn = _connect()
    try:
        conn.executescript(SCHEMA_SQL)
        _ensure_run_row(conn)
        conn.commit()
    finally:
        conn.close()


def _ensure_run_row(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
    if row:
        return
    now_ms = _now_ms()
    conn.execute(
        """
        INSERT INTO forward_test_run (
            id, created_at, updated_at, enabled, start_time, starting_equity, cash_balance, peak_equity,
            leverage, risk_pct, max_positions, fee_rate, tp_r, cancel_after_candles, risk_free_rate, timezone
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            now_ms,
            now_ms,
            1,
            now_ms,
            DEFAULT_STARTING_EQUITY,
            DEFAULT_STARTING_EQUITY,
            DEFAULT_STARTING_EQUITY,
            DEFAULT_LEVERAGE,
            DEFAULT_RISK_PCT,
            DEFAULT_MAX_POSITIONS,
            DEFAULT_FEE_RATE,
            DEFAULT_TP_R,
            DEFAULT_CANCEL_AFTER_CANDLES,
            DEFAULT_RISK_FREE_RATE,
            DEFAULT_TIMEZONE,
        ),
    )


class ForwardTestService:
    def __init__(self, rest_base: str | None = None) -> None:
        self.rest_base = rest_base or DEFAULT_REST_BASE
        self._session = requests.Session()

    def initialize(self) -> None:
        init_forward_test_db()

    def get_status(self) -> dict:
        conn = _connect()
        try:
            _ensure_run_row(conn)
            run = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
            open_positions = conn.execute(
                "SELECT COUNT(1) AS count FROM forward_test_positions WHERE status = 'open'"
            ).fetchone()["count"]
            pending_orders = conn.execute(
                "SELECT COUNT(1) AS count FROM forward_test_orders WHERE status = 'pending'"
            ).fetchone()["count"]
            return {
                "enabled": bool(run["enabled"]),
                "start_time": run["start_time"],
                "starting_equity": run["starting_equity"],
                "cash_balance": run["cash_balance"],
                "peak_equity": run["peak_equity"],
                "leverage": run["leverage"],
                "risk_pct": run["risk_pct"],
                "max_positions": run["max_positions"],
                "fee_rate": run["fee_rate"],
                "tp_r": run["tp_r"],
                "cancel_after_candles": run["cancel_after_candles"],
                "risk_free_rate": run["risk_free_rate"],
                "timezone": run["timezone"],
                "open_positions": int(open_positions),
                "pending_orders": int(pending_orders),
                "updated_at": run["updated_at"],
            }
        finally:
            conn.close()

    def set_enabled(self, enabled: bool) -> dict:
        conn = _connect()
        try:
            _ensure_run_row(conn)
            now_ms = _now_ms()
            conn.execute(
                "UPDATE forward_test_run SET enabled = ?, updated_at = ? WHERE id = 1",
                (1 if enabled else 0, now_ms),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_status()

    def register_signal(self, alert: dict, signal_payload: dict | None = None) -> Optional[dict]:
        signal_type = str(alert.get("type", "")).lower().strip()
        if signal_type not in ALLOWED_SIGNAL_TYPES:
            return None
        direction = str(alert.get("direction", "")).lower().strip()
        if direction not in {"long", "short"}:
            return None

        symbol = str(alert.get("symbol", "")).upper().strip()
        tf = str(alert.get("tf", "")).strip()
        signal_time = int(_safe_float(alert.get("time"), 0))
        entry = _safe_float(alert.get("entry"))
        sl = _safe_float(alert.get("sl"))
        if not symbol or not tf or signal_time <= 0 or entry <= 0 or sl <= 0:
            return None
        risk_per_unit = abs(entry - sl)
        if risk_per_unit <= 0:
            return None

        bias = str(alert.get("hwc_bias") or (signal_payload or {}).get("hwc_bias") or "").strip().lower() or None
        regime = _regime_from_bias(bias)

        conn = _connect()
        try:
            _ensure_run_row(conn)
            run = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
            if not run["enabled"]:
                return None

            alert_id = alert.get("id")
            if alert_id is not None:
                existing = conn.execute(
                    "SELECT id FROM forward_test_orders WHERE alert_id = ?",
                    (int(alert_id),),
                ).fetchone()
                if existing:
                    return None

            open_positions = conn.execute(
                "SELECT COUNT(1) AS count FROM forward_test_positions WHERE status = 'open'"
            ).fetchone()["count"]
            if int(open_positions) >= int(run["max_positions"]):
                return None

            equity, _unrealized, margin_used, _open_count = self._compute_equity(conn, run)
            risk_amount = max(0.0, equity * float(run["risk_pct"]))
            qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
            if qty <= 0:
                return None
            notional = qty * entry
            leverage = max(float(run["leverage"]), 1.0)
            margin_required = notional / leverage
            if margin_required <= 0:
                return None
            if margin_used + margin_required > equity:
                return None

            sign = 1.0 if direction == "long" else -1.0
            tp = entry + sign * (risk_per_unit * float(run["tp_r"]))

            now_ms = _now_ms()
            cursor = conn.execute(
                """
                INSERT INTO forward_test_orders (
                    created_at, alert_id, symbol, tf, signal_type, direction, bias, regime, signal_time,
                    entry_price, sl_price, tp_price, risk_amount, quantity, notional, margin_required, leverage,
                    candles_waited, cancel_after_candles, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_ms,
                    int(alert_id) if alert_id is not None else None,
                    symbol,
                    tf,
                    signal_type,
                    direction,
                    bias,
                    regime,
                    signal_time,
                    entry,
                    sl,
                    tp,
                    risk_amount,
                    qty,
                    notional,
                    margin_required,
                    leverage,
                    0,
                    int(run["cancel_after_candles"]),
                    "pending",
                ),
            )
            conn.execute("UPDATE forward_test_run SET updated_at = ? WHERE id = 1", (now_ms,))
            conn.commit()
            return {"order_id": cursor.lastrowid, "status": "pending"}
        finally:
            conn.close()

    def process_symbol_tf(self, ingest, symbol: str, tf: str) -> None:
        symbol_upper = symbol.upper()
        conn = _connect()
        try:
            _ensure_run_row(conn)
            run = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
            if not run["enabled"]:
                return
            cache = ingest.get_cache(symbol_upper, tf)
            if cache is None:
                return
            candles = cache.list_all()
            if not candles:
                return
            cursor_row = conn.execute(
                "SELECT last_candle_time FROM forward_test_cursor WHERE symbol = ? AND tf = ?",
                (symbol_upper, tf),
            ).fetchone()
            last_time = int(cursor_row["last_candle_time"]) if cursor_row else 0
            new_candles = [candle for candle in candles if candle.close_time > last_time]
            if not new_candles:
                return

            for candle in new_candles:
                self._process_pending_orders_for_candle(conn, run, symbol_upper, tf, candle)
                self._process_open_positions_for_candle(conn, run, symbol_upper, tf, candle)
                self._snapshot(conn, run, candle.close_time)
                last_time = candle.close_time

            now_ms = _now_ms()
            conn.execute(
                """
                INSERT INTO forward_test_cursor(symbol, tf, last_candle_time)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol, tf) DO UPDATE SET last_candle_time = excluded.last_candle_time
                """,
                (symbol_upper, tf, last_time),
            )
            conn.execute("UPDATE forward_test_run SET updated_at = ? WHERE id = 1", (now_ms,))
            conn.commit()
        finally:
            conn.close()

    def list_equity(self, limit: int = 2000) -> list[dict]:
        limit_value = max(1, min(int(limit), 10000))
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM forward_test_equity ORDER BY time DESC LIMIT ?",
                (limit_value,),
            ).fetchall()
            items = [dict(row) for row in reversed(rows)]
            return items
        finally:
            conn.close()

    def list_trades(
        self,
        limit: int = 200,
        offset: int = 0,
        symbol: str | None = None,
        tf: str | None = None,
        direction: str | None = None,
    ) -> tuple[list[dict], int]:
        limit_value = max(1, min(int(limit), 1000))
        offset_value = max(0, int(offset))
        clauses = ["status = 'closed'"]
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if tf:
            clauses.append("tf = ?")
            params.append(tf)
        if direction:
            clauses.append("direction = ?")
            params.append(direction.lower())
        where = f"WHERE {' AND '.join(clauses)}"

        conn = _connect()
        try:
            total = conn.execute(
                f"SELECT COUNT(1) AS count FROM forward_test_positions {where}",
                params,
            ).fetchone()["count"]
            rows = conn.execute(
                f"""
                SELECT * FROM forward_test_positions
                {where}
                ORDER BY exit_time DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit_value, offset_value],
            ).fetchall()
            return [dict(row) for row in rows], int(total)
        finally:
            conn.close()

    def export_trades_csv(self) -> str:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM forward_test_positions
                WHERE status = 'closed'
                ORDER BY exit_time DESC, id DESC
                """
            ).fetchall()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "symbol",
                    "tf",
                    "signal_type",
                    "direction",
                    "regime",
                    "entry_time",
                    "entry_price",
                    "sl_price",
                    "tp_price",
                    "exit_time",
                    "exit_price",
                    "exit_reason",
                    "quantity",
                    "notional",
                    "margin_required",
                    "gross_pnl",
                    "net_pnl",
                    "fee_entry",
                    "fee_exit",
                    "funding_cost",
                    "roe_pct",
                    "mae_r",
                    "mfe_r",
                    "holding_candles",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["id"],
                        row["symbol"],
                        row["tf"],
                        row["signal_type"],
                        row["direction"],
                        row["regime"],
                        row["entry_time"],
                        row["entry_price"],
                        row["sl_price"],
                        row["tp_price"],
                        row["exit_time"],
                        row["exit_price"],
                        row["exit_reason"],
                        row["quantity"],
                        row["notional"],
                        row["margin_required"],
                        row["gross_pnl"],
                        row["net_pnl"],
                        row["fee_entry"],
                        row["fee_exit"],
                        row["funding_cost"],
                        row["roe_pct"],
                        row["mae_r"],
                        row["mfe_r"],
                        row["holding_candles"],
                    ]
                )
            return output.getvalue()
        finally:
            conn.close()

    def get_summary(self) -> dict:
        conn = _connect()
        try:
            _ensure_run_row(conn)
            run = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
            trades_rows = conn.execute(
                "SELECT * FROM forward_test_positions WHERE status = 'closed' ORDER BY exit_time ASC, id ASC"
            ).fetchall()
            snapshots_rows = conn.execute("SELECT * FROM forward_test_equity ORDER BY time ASC, id ASC").fetchall()
            open_positions = conn.execute(
                "SELECT COUNT(1) AS count FROM forward_test_positions WHERE status = 'open'"
            ).fetchone()["count"]
            pending_orders = conn.execute(
                "SELECT COUNT(1) AS count FROM forward_test_orders WHERE status = 'pending'"
            ).fetchone()["count"]

            trades = [dict(row) for row in trades_rows]
            snapshots = [dict(row) for row in snapshots_rows]
            status = {
                "enabled": bool(run["enabled"]),
                "start_time": run["start_time"],
                "starting_equity": run["starting_equity"],
                "cash_balance": run["cash_balance"],
                "peak_equity": run["peak_equity"],
                "open_positions": int(open_positions),
                "pending_orders": int(pending_orders),
                "updated_at": run["updated_at"],
                "leverage": run["leverage"],
                "risk_pct": run["risk_pct"],
                "max_positions": run["max_positions"],
                "fee_rate": run["fee_rate"],
                "tp_r": run["tp_r"],
                "cancel_after_candles": run["cancel_after_candles"],
                "risk_free_rate": run["risk_free_rate"],
                "timezone": run["timezone"],
            }
            metrics, breakdowns, charts = self._build_metrics(run, trades, snapshots)
            return {
                "status": status,
                "metrics": metrics,
                "breakdowns": breakdowns,
                "charts": charts,
            }
        finally:
            conn.close()

    def _process_pending_orders_for_candle(
        self,
        conn: sqlite3.Connection,
        run: sqlite3.Row,
        symbol: str,
        tf: str,
        candle,
    ) -> None:
        rows = conn.execute(
            """
            SELECT *
            FROM forward_test_orders
            WHERE status = 'pending' AND symbol = ? AND tf = ?
            ORDER BY created_at ASC, id ASC
            """,
            (symbol, tf),
        ).fetchall()
        if not rows:
            return

        now_ms = _now_ms()
        for row in rows:
            signal_time = int(row["signal_time"])
            if candle.close_time <= signal_time:
                continue

            touched = (candle.low <= row["entry_price"] <= candle.high)
            if touched:
                current_run = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
                open_positions = conn.execute(
                    "SELECT COUNT(1) AS count FROM forward_test_positions WHERE status = 'open'"
                ).fetchone()["count"]
                if int(open_positions) >= int(current_run["max_positions"]):
                    updated_waited = int(row["candles_waited"]) + 1
                    self._expire_or_keep_pending(conn, row["id"], updated_waited)
                    continue

                equity, _unrealized, margin_used, _open_count = self._compute_equity(conn, current_run)
                if margin_used + float(row["margin_required"]) > equity:
                    updated_waited = int(row["candles_waited"]) + 1
                    self._expire_or_keep_pending(conn, row["id"], updated_waited)
                    continue

                fee_entry = float(row["notional"]) * float(current_run["fee_rate"])
                conn.execute(
                    "UPDATE forward_test_run SET cash_balance = cash_balance - ?, updated_at = ? WHERE id = 1",
                    (fee_entry, now_ms),
                )
                entry_price = float(row["entry_price"])
                leverage = float(row["leverage"])
                liq_price = _compute_liquidation_price(entry_price, row["direction"], leverage)
                liq_dist_entry = abs(entry_price - liq_price) / entry_price * 100.0 if entry_price > 0 else 0.0
                conn.execute(
                    """
                    INSERT INTO forward_test_positions (
                        order_id, symbol, tf, signal_type, direction, bias, regime, entry_time, entry_price,
                        sl_price, tp_price, quantity, notional, margin_required, leverage, equity_at_entry,
                        risk_amount, fee_entry, status, liquidation_price, liq_distance_entry_pct, liq_distance_min_pct,
                        mark_price, last_mark_time, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        row["symbol"],
                        row["tf"],
                        row["signal_type"],
                        row["direction"],
                        row["bias"],
                        row["regime"],
                        candle.close_time,
                        entry_price,
                        row["sl_price"],
                        row["tp_price"],
                        row["quantity"],
                        row["notional"],
                        row["margin_required"],
                        row["leverage"],
                        equity,
                        row["risk_amount"],
                        fee_entry,
                        "open",
                        liq_price,
                        liq_dist_entry,
                        liq_dist_entry,
                        entry_price,
                        candle.close_time,
                        now_ms,
                        now_ms,
                    ),
                )
                conn.execute(
                    """
                    UPDATE forward_test_orders
                    SET status = 'filled', filled_at = ?, filled_price = ?, status_reason = NULL
                    WHERE id = ?
                    """,
                    (candle.close_time, entry_price, row["id"]),
                )
                continue

            updated_waited = int(row["candles_waited"]) + 1
            self._expire_or_keep_pending(conn, row["id"], updated_waited)

    def _expire_or_keep_pending(self, conn: sqlite3.Connection, order_id: int, candles_waited: int) -> None:
        row = conn.execute(
            "SELECT cancel_after_candles FROM forward_test_orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        cancel_after = int(row["cancel_after_candles"]) if row else DEFAULT_CANCEL_AFTER_CANDLES
        if candles_waited >= cancel_after:
            conn.execute(
                """
                UPDATE forward_test_orders
                SET candles_waited = ?, status = 'cancelled', status_reason = 'expired'
                WHERE id = ?
                """,
                (candles_waited, order_id),
            )
            return
        conn.execute(
            "UPDATE forward_test_orders SET candles_waited = ? WHERE id = ?",
            (candles_waited, order_id),
        )

    def _process_open_positions_for_candle(
        self,
        conn: sqlite3.Connection,
        run: sqlite3.Row,
        symbol: str,
        tf: str,
        candle,
    ) -> None:
        rows = conn.execute(
            """
            SELECT *
            FROM forward_test_positions
            WHERE status = 'open' AND symbol = ? AND tf = ?
            ORDER BY entry_time ASC, id ASC
            """,
            (symbol, tf),
        ).fetchall()
        if not rows:
            return

        now_ms = _now_ms()
        for row in rows:
            entry_price = float(row["entry_price"])
            sl_price = float(row["sl_price"])
            tp_price = float(row["tp_price"])
            liq_price = float(row["liquidation_price"])
            qty = float(row["quantity"])
            direction = row["direction"]
            risk_per_unit = max(abs(entry_price - sl_price), 1e-12)

            if direction == "long":
                adverse = max(0.0, entry_price - candle.low)
                favorable = max(0.0, candle.high - entry_price)
                sl_hit = candle.low <= sl_price
                tp_hit = candle.high >= tp_price
                liq_hit = candle.low <= liq_price
                current_liq_distance = ((candle.low - liq_price) / entry_price) * 100.0 if entry_price > 0 else 0.0
            else:
                adverse = max(0.0, candle.high - entry_price)
                favorable = max(0.0, entry_price - candle.low)
                sl_hit = candle.high >= sl_price
                tp_hit = candle.low <= tp_price
                liq_hit = candle.high >= liq_price
                current_liq_distance = ((liq_price - candle.high) / entry_price) * 100.0 if entry_price > 0 else 0.0

            mae_abs = max(float(row["mae_abs"]), adverse)
            mfe_abs = max(float(row["mfe_abs"]), favorable)
            mae_r = mae_abs / risk_per_unit
            mfe_r = mfe_abs / risk_per_unit
            liq_dist_min = min(float(row["liq_distance_min_pct"]), current_liq_distance)

            candidates: list[tuple[str, float]] = []
            if tp_hit:
                candidates.append(("tp", tp_price))
            if sl_hit:
                candidates.append(("sl", sl_price))
            if liq_hit:
                candidates.append(("liquidation", liq_price))

            if candidates:
                chosen_reason, chosen_price = min(
                    candidates,
                    key=lambda item: _gross_pnl(direction, entry_price, item[1], qty),
                )
                self._close_position(
                    conn,
                    run,
                    dict(row),
                    candle.close_time,
                    chosen_price,
                    chosen_reason,
                    mae_abs,
                    mfe_abs,
                    mae_r,
                    mfe_r,
                    liq_dist_min,
                )
                continue

            conn.execute(
                """
                UPDATE forward_test_positions
                SET holding_candles = holding_candles + 1,
                    mark_price = ?,
                    last_mark_time = ?,
                    mae_abs = ?,
                    mfe_abs = ?,
                    mae_r = ?,
                    mfe_r = ?,
                    liq_distance_min_pct = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    candle.close,
                    candle.close_time,
                    mae_abs,
                    mfe_abs,
                    mae_r,
                    mfe_r,
                    liq_dist_min,
                    now_ms,
                    row["id"],
                ),
            )

    def _close_position(
        self,
        conn: sqlite3.Connection,
        run: sqlite3.Row,
        position: dict,
        exit_time: int,
        exit_price: float,
        exit_reason: str,
        mae_abs: float,
        mfe_abs: float,
        mae_r: float,
        mfe_r: float,
        liq_dist_min: float,
    ) -> None:
        qty = float(position["quantity"])
        entry_price = float(position["entry_price"])
        direction = position["direction"]
        notional = float(position["notional"])
        fee_entry = float(position["fee_entry"])
        fee_exit = abs(exit_price * qty) * float(run["fee_rate"])
        gross = _gross_pnl(direction, entry_price, exit_price, qty)
        funding_cost = self._compute_funding_cost(
            conn,
            position["symbol"],
            direction,
            notional,
            int(position["entry_time"]),
            int(exit_time),
        )
        net = gross - fee_entry - fee_exit - funding_cost
        margin_required = float(position["margin_required"])
        roe_pct = (net / margin_required) * 100.0 if margin_required > 0 else 0.0
        now_ms = _now_ms()

        conn.execute(
            """
            UPDATE forward_test_positions
            SET status = 'closed',
                exit_time = ?,
                exit_price = ?,
                exit_reason = ?,
                fee_exit = ?,
                gross_pnl = ?,
                net_pnl = ?,
                roe_pct = ?,
                funding_cost = ?,
                holding_candles = holding_candles + 1,
                mark_price = ?,
                last_mark_time = ?,
                mae_abs = ?,
                mfe_abs = ?,
                mae_r = ?,
                mfe_r = ?,
                liq_distance_min_pct = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                exit_time,
                exit_price,
                exit_reason,
                fee_exit,
                gross,
                net,
                roe_pct,
                funding_cost,
                exit_price,
                exit_time,
                mae_abs,
                mfe_abs,
                mae_r,
                mfe_r,
                liq_dist_min,
                now_ms,
                position["id"],
            ),
        )
        conn.execute(
            "UPDATE forward_test_run SET cash_balance = cash_balance + ?, updated_at = ? WHERE id = 1",
            (gross - fee_exit - funding_cost, now_ms),
        )

    def _compute_funding_cost(
        self,
        conn: sqlite3.Connection,
        symbol: str,
        direction: str,
        notional: float,
        start_ms: int,
        end_ms: int,
    ) -> float:
        if end_ms <= start_ms:
            return 0.0
        self._sync_funding_rates(conn, symbol, start_ms, end_ms)
        rows = conn.execute(
            """
            SELECT funding_rate
            FROM forward_test_funding_rates
            WHERE symbol = ? AND funding_time > ? AND funding_time <= ?
            ORDER BY funding_time ASC
            """,
            (symbol.upper(), start_ms, end_ms),
        ).fetchall()
        total_cost = 0.0
        for row in rows:
            rate = _safe_float(row["funding_rate"])
            if direction == "long":
                total_cost += notional * rate
            else:
                total_cost += -notional * rate
        return total_cost

    def _sync_funding_rates(
        self,
        conn: sqlite3.Connection,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> None:
        symbol_upper = symbol.upper()
        if end_ms <= start_ms:
            return
        fetch_start = start_ms
        while fetch_start <= end_ms:
            try:
                response = self._session.get(
                    f"{self.rest_base}/fapi/v1/fundingRate",
                    params={
                        "symbol": symbol_upper,
                        "startTime": fetch_start,
                        "endTime": end_ms,
                        "limit": 1000,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception:
                return

            if not payload:
                return

            last_time = fetch_start
            for item in payload:
                funding_time = int(_safe_float(item.get("fundingTime"), 0))
                funding_rate = _safe_float(item.get("fundingRate"), 0.0)
                if funding_time <= 0:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO forward_test_funding_rates(symbol, funding_time, funding_rate)
                    VALUES (?, ?, ?)
                    """,
                    (symbol_upper, funding_time, funding_rate),
                )
                if funding_time > last_time:
                    last_time = funding_time

            if len(payload) < 1000 or last_time >= end_ms:
                return
            fetch_start = last_time + 1

    def _compute_equity(self, conn: sqlite3.Connection, run: sqlite3.Row) -> tuple[float, float, float, int]:
        rows = conn.execute(
            """
            SELECT direction, entry_price, quantity, mark_price, margin_required
            FROM forward_test_positions
            WHERE status = 'open'
            """
        ).fetchall()
        unrealized = 0.0
        margin_used = 0.0
        for row in rows:
            qty = _safe_float(row["quantity"])
            entry = _safe_float(row["entry_price"])
            mark = _safe_float(row["mark_price"], entry)
            direction = row["direction"]
            unrealized += _gross_pnl(direction, entry, mark, qty)
            margin_used += _safe_float(row["margin_required"])
        cash = _safe_float(run["cash_balance"])
        equity = cash + unrealized
        return equity, unrealized, margin_used, len(rows)

    def _snapshot(self, conn: sqlite3.Connection, run: sqlite3.Row, event_time: int) -> None:
        current_run = conn.execute("SELECT * FROM forward_test_run WHERE id = 1").fetchone()
        equity, unrealized, margin_used, open_count = self._compute_equity(conn, current_run)
        pending_orders = conn.execute(
            "SELECT COUNT(1) AS count FROM forward_test_orders WHERE status = 'pending'"
        ).fetchone()["count"]
        peak = max(_safe_float(current_run["peak_equity"]), equity)
        drawdown_abs = max(0.0, peak - equity)
        drawdown_pct = (drawdown_abs / peak * 100.0) if peak > 0 else 0.0
        conn.execute(
            """
            INSERT INTO forward_test_equity(
                time, equity, cash_balance, unrealized_pnl, margin_used, open_positions, pending_orders,
                drawdown_abs, drawdown_pct, exposure_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_time,
                equity,
                current_run["cash_balance"],
                unrealized,
                margin_used,
                open_count,
                pending_orders,
                drawdown_abs,
                drawdown_pct,
                1 if open_count > 0 else 0,
            ),
        )
        conn.execute(
            "UPDATE forward_test_run SET peak_equity = ?, updated_at = ? WHERE id = 1",
            (peak, _now_ms()),
        )

    def _build_metrics(
        self,
        run: sqlite3.Row,
        trades: list[dict],
        snapshots: list[dict],
    ) -> tuple[dict, dict, dict]:
        total_trades = len(trades)
        gross_profit = sum(max(_safe_float(item.get("gross_pnl")), 0.0) for item in trades)
        gross_loss_signed = sum(min(_safe_float(item.get("gross_pnl")), 0.0) for item in trades)
        gross_loss = abs(gross_loss_signed)
        net_profit = sum(_safe_float(item.get("net_pnl")) for item in trades)
        wins = [item for item in trades if _safe_float(item.get("net_pnl")) > 0]
        losses = [item for item in trades if _safe_float(item.get("net_pnl")) < 0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades else 0.0
        loss_rate = (len(losses) / total_trades * 100.0) if total_trades else 0.0
        avg_win = statistics.mean(_safe_float(item.get("net_pnl")) for item in wins) if wins else 0.0
        avg_loss = statistics.mean(_safe_float(item.get("net_pnl")) for item in losses) if losses else 0.0
        risk_reward = (avg_win / abs(avg_loss)) if avg_loss < 0 else None
        expectancy = (net_profit / total_trades) if total_trades else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        max_drawdown_abs = max((_safe_float(item.get("drawdown_abs")) for item in snapshots), default=0.0)
        max_drawdown_pct = max((_safe_float(item.get("drawdown_pct")) for item in snapshots), default=0.0)

        fee_paid = sum(_safe_float(item.get("fee_entry")) + _safe_float(item.get("fee_exit")) for item in trades)
        funding_costs = [_safe_float(item.get("funding_cost")) for item in trades]
        funding_paid = sum(value for value in funding_costs if value > 0)
        funding_received = sum(-value for value in funding_costs if value < 0)

        holding_ms_values = [
            max(0, int(_safe_float(item.get("exit_time")) - _safe_float(item.get("entry_time"))))
            for item in trades
            if item.get("entry_time") and item.get("exit_time")
        ]
        avg_holding_ms = statistics.mean(holding_ms_values) if holding_ms_values else 0.0

        exposure_pct = (
            (sum(int(item.get("exposure_flag", 0)) for item in snapshots) / len(snapshots) * 100.0)
            if snapshots
            else 0.0
        )

        margin_usage_values = []
        for item in snapshots:
            equity = _safe_float(item.get("equity"))
            margin = _safe_float(item.get("margin_used"))
            if equity > 0:
                margin_usage_values.append((margin / equity) * 100.0)
        margin_usage_avg = statistics.mean(margin_usage_values) if margin_usage_values else 0.0
        margin_usage_max = max(margin_usage_values) if margin_usage_values else 0.0

        liq_entry_values = [_safe_float(item.get("liq_distance_entry_pct")) for item in trades]
        liq_min_values = [_safe_float(item.get("liq_distance_min_pct")) for item in trades]
        liq_distance_avg = statistics.mean(liq_entry_values) if liq_entry_values else 0.0
        liq_distance_min = min(liq_min_values) if liq_min_values else 0.0

        start_equity = _safe_float(run["starting_equity"], 1.0)
        current_equity = _safe_float(run["cash_balance"])
        if snapshots:
            current_equity = _safe_float(snapshots[-1]["equity"], current_equity)
        roe_pct = ((current_equity - start_equity) / start_equity * 100.0) if start_equity > 0 else 0.0

        returns = []
        excess_returns = []
        for item in trades:
            margin = _safe_float(item.get("margin_required"))
            if margin <= 0:
                continue
            ret = _safe_float(item.get("net_pnl")) / margin
            returns.append(ret)
            duration_ms = max(0.0, _safe_float(item.get("exit_time")) - _safe_float(item.get("entry_time")))
            years = duration_ms / (365.0 * 24.0 * 60.0 * 60.0 * 1000.0)
            rf_trade = (1.0 + _safe_float(run["risk_free_rate"])) ** years - 1.0 if years > 0 else 0.0
            excess_returns.append(ret - rf_trade)

        volatility_returns = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = None
        if len(excess_returns) > 1:
            std_excess = statistics.pstdev(excess_returns)
            if std_excess > 0:
                sharpe = (statistics.mean(excess_returns) / std_excess) * math.sqrt(len(excess_returns))

        sortino = None
        if excess_returns:
            downside = [value for value in excess_returns if value < 0]
            if downside:
                downside_std = statistics.pstdev(downside) if len(downside) > 1 else abs(downside[0])
                if downside_std > 0:
                    sortino = (statistics.mean(excess_returns) / downside_std) * math.sqrt(len(excess_returns))

        elapsed_ms = max(1.0, _now_ms() - _safe_float(run["start_time"]))
        elapsed_days = elapsed_ms / (24.0 * 60.0 * 60.0 * 1000.0)
        annualized_return = 0.0
        if start_equity > 0 and current_equity > 0 and elapsed_days >= 1.0:
            try:
                annualized_return = (current_equity / start_equity) ** (365.0 / elapsed_days) - 1.0
            except OverflowError:
                annualized_return = float("inf")
        calmar = (annualized_return / (max_drawdown_pct / 100.0)) if max_drawdown_pct > 0 else None
        recovery_factor = (net_profit / max_drawdown_abs) if max_drawdown_abs > 0 else None
        equity_slope = self._equity_slope_per_day(snapshots)

        consecutive_wins, consecutive_losses = self._max_consecutive_streaks(trades)

        risk_pcts = []
        for item in trades:
            eq = _safe_float(item.get("equity_at_entry"))
            risk_amt = _safe_float(item.get("risk_amount"))
            if eq > 0:
                risk_pcts.append(risk_amt / eq)
        position_size_consistency = (
            (statistics.pstdev(risk_pcts) / statistics.mean(risk_pcts))
            if len(risk_pcts) > 1 and statistics.mean(risk_pcts) > 0
            else 0.0
        )

        mae_values = [_safe_float(item.get("mae_r")) for item in trades]
        mfe_values = [_safe_float(item.get("mfe_r")) for item in trades]
        mae_avg = statistics.mean(mae_values) if mae_values else 0.0
        mfe_avg = statistics.mean(mfe_values) if mfe_values else 0.0

        long_perf = self._side_performance(trades, "long")
        short_perf = self._side_performance(trades, "short")
        regime_perf = self._regime_performance(trades)
        hour_perf = self._time_of_day_performance(trades, run["timezone"])
        day_perf = self._day_of_week_performance(trades, run["timezone"])
        symbol_perf = self._symbol_performance(trades)
        daily_pnl = self._daily_pnl(trades, run["timezone"])

        charts = {
            "equity_curve": [
                {
                    "time": item["time"],
                    "equity": item["equity"],
                    "cash_balance": item["cash_balance"],
                    "drawdown_abs": item["drawdown_abs"],
                    "drawdown_pct": item["drawdown_pct"],
                    "margin_usage_pct": ((item["margin_used"] / item["equity"]) * 100.0) if item["equity"] > 0 else 0.0,
                    "exposure_flag": item["exposure_flag"],
                }
                for item in snapshots
            ],
            "daily_pnl": daily_pnl,
            "mae_mfe": [
                {
                    "trade_id": item["id"],
                    "mae_r": _safe_float(item.get("mae_r")),
                    "mfe_r": _safe_float(item.get("mfe_r")),
                    "net_pnl": _safe_float(item.get("net_pnl")),
                    "direction": item.get("direction"),
                }
                for item in trades
            ],
            "trade_returns": [
                {
                    "trade_id": item["id"],
                    "time": item.get("exit_time"),
                    "return_pct": ((_safe_float(item.get("net_pnl")) / _safe_float(item.get("margin_required"))) * 100.0)
                    if _safe_float(item.get("margin_required")) > 0
                    else 0.0,
                }
                for item in trades
            ],
        }

        metrics = {
            "net_profit": net_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "win_rate_pct": win_rate,
            "loss_rate_pct": loss_rate,
            "risk_reward_ratio": risk_reward,
            "expectancy_per_trade": expectancy,
            "average_win": avg_win,
            "average_loss": avg_loss,
            "max_drawdown_pct": max_drawdown_pct,
            "absolute_drawdown": max_drawdown_abs,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "equity_curve_slope_per_day": equity_slope,
            "recovery_factor": recovery_factor,
            "total_trades": total_trades,
            "long_trades_performance": long_perf,
            "short_trades_performance": short_perf,
            "funding_fees_paid": funding_paid,
            "funding_fees_received": funding_received,
            "trading_fees_paid": fee_paid,
            "slippage_paid": 0.0,
            "average_holding_time_ms": avg_holding_ms,
            "exposure_time_pct": exposure_pct,
            "margin_usage_pct_avg": margin_usage_avg,
            "margin_usage_pct_max": margin_usage_max,
            "liquidation_distance_pct_avg": liq_distance_avg,
            "liquidation_distance_pct_min": liq_distance_min,
            "return_on_equity_pct": roe_pct,
            "volatility_of_returns": volatility_returns,
            "consecutive_wins": consecutive_wins,
            "consecutive_losses": consecutive_losses,
            "position_size_consistency": position_size_consistency,
            "mae_avg_r": mae_avg,
            "mfe_avg_r": mfe_avg,
            "elapsed_days": elapsed_days,
            "annualized_return": annualized_return,
            "current_equity": current_equity,
            "starting_equity": start_equity,
        }

        breakdowns = {
            "time_of_day_performance": hour_perf,
            "day_of_week_performance": day_perf,
            "market_regime_performance": regime_perf,
            "symbol_performance": symbol_perf,
            "long_short_performance": [long_perf, short_perf],
        }
        return metrics, breakdowns, charts

    def _equity_slope_per_day(self, snapshots: list[dict]) -> float:
        if len(snapshots) < 2:
            return 0.0
        t0 = _safe_float(snapshots[0]["time"])
        xs = [(_safe_float(item["time"]) - t0) / (24.0 * 60.0 * 60.0 * 1000.0) for item in snapshots]
        ys = [_safe_float(item["equity"]) for item in snapshots]
        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(ys)
        denom = sum((value - mean_x) ** 2 for value in xs)
        if denom <= 0:
            return 0.0
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        return num / denom

    def _max_consecutive_streaks(self, trades: list[dict]) -> tuple[int, int]:
        wins = 0
        losses = 0
        max_wins = 0
        max_losses = 0
        for item in trades:
            pnl = _safe_float(item.get("net_pnl"))
            if pnl > 0:
                wins += 1
                losses = 0
            elif pnl < 0:
                losses += 1
                wins = 0
            else:
                wins = 0
                losses = 0
            max_wins = max(max_wins, wins)
            max_losses = max(max_losses, losses)
        return max_wins, max_losses

    def _side_performance(self, trades: list[dict], side: str) -> dict:
        items = [item for item in trades if item.get("direction") == side]
        total = len(items)
        if total == 0:
            return {"side": side, "trades": 0, "net_profit": 0.0, "win_rate_pct": 0.0, "profit_factor": None}
        net = sum(_safe_float(item.get("net_pnl")) for item in items)
        wins = [item for item in items if _safe_float(item.get("net_pnl")) > 0]
        win_rate = len(wins) / total * 100.0
        gross_profit = sum(max(_safe_float(item.get("gross_pnl")), 0.0) for item in items)
        gross_loss = abs(sum(min(_safe_float(item.get("gross_pnl")), 0.0) for item in items))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
        return {
            "side": side,
            "trades": total,
            "net_profit": net,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
        }

    def _regime_performance(self, trades: list[dict]) -> list[dict]:
        groups: dict[str, list[dict]] = {}
        for item in trades:
            regime = str(item.get("regime") or "ranging")
            groups.setdefault(regime, []).append(item)
        result = []
        for regime, items in sorted(groups.items(), key=lambda pair: pair[0]):
            total = len(items)
            wins = len([row for row in items if _safe_float(row.get("net_pnl")) > 0])
            net = sum(_safe_float(row.get("net_pnl")) for row in items)
            result.append(
                {
                    "regime": regime,
                    "trades": total,
                    "net_profit": net,
                    "win_rate_pct": (wins / total * 100.0) if total else 0.0,
                }
            )
        return result

    def _time_of_day_performance(self, trades: list[dict], tz_name: str) -> list[dict]:
        try:
            tzinfo = ZoneInfo(str(tz_name))
        except Exception:
            tzinfo = timezone.utc
        buckets: dict[int, list[dict]] = {idx: [] for idx in range(24)}
        for item in trades:
            ts = _safe_float(item.get("entry_time"))
            if ts <= 0:
                continue
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).astimezone(tzinfo)
            buckets[dt.hour].append(item)
        result = []
        for hour in range(24):
            items = buckets[hour]
            total = len(items)
            wins = len([row for row in items if _safe_float(row.get("net_pnl")) > 0])
            net = sum(_safe_float(row.get("net_pnl")) for row in items)
            result.append(
                {
                    "hour": hour,
                    "trades": total,
                    "net_profit": net,
                    "win_rate_pct": (wins / total * 100.0) if total else 0.0,
                }
            )
        return result

    def _day_of_week_performance(self, trades: list[dict], tz_name: str) -> list[dict]:
        try:
            tzinfo = ZoneInfo(str(tz_name))
        except Exception:
            tzinfo = timezone.utc
        buckets: dict[str, list[dict]] = {day: [] for day in DAY_ORDER}
        for item in trades:
            ts = _safe_float(item.get("entry_time"))
            if ts <= 0:
                continue
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).astimezone(tzinfo)
            buckets[dt.strftime("%A")].append(item)
        result = []
        for day in DAY_ORDER:
            items = buckets.get(day, [])
            total = len(items)
            wins = len([row for row in items if _safe_float(row.get("net_pnl")) > 0])
            net = sum(_safe_float(row.get("net_pnl")) for row in items)
            result.append(
                {
                    "day": day,
                    "trades": total,
                    "net_profit": net,
                    "win_rate_pct": (wins / total * 100.0) if total else 0.0,
                }
            )
        return result

    def _daily_pnl(self, trades: list[dict], tz_name: str) -> list[dict]:
        try:
            tzinfo = ZoneInfo(str(tz_name))
        except Exception:
            tzinfo = timezone.utc
        buckets: dict[str, dict[str, Any]] = {}
        for item in trades:
            ts = _safe_float(item.get("exit_time"))
            if ts <= 0:
                continue
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).astimezone(tzinfo)
            day = dt.strftime("%Y-%m-%d")
            bucket = buckets.setdefault(day, {"day": day, "trades": 0, "net_profit": 0.0})
            bucket["trades"] += 1
            bucket["net_profit"] += _safe_float(item.get("net_pnl"))
        return [buckets[key] for key in sorted(buckets.keys())]

    def _symbol_performance(self, trades: list[dict]) -> list[dict]:
        buckets: dict[str, dict[str, Any]] = {}
        for item in trades:
            symbol = str(item.get("symbol") or "")
            if not symbol:
                continue
            bucket = buckets.setdefault(symbol, {"symbol": symbol, "trades": 0, "net_profit": 0.0, "wins": 0})
            bucket["trades"] += 1
            pnl = _safe_float(item.get("net_pnl"))
            bucket["net_profit"] += pnl
            if pnl > 0:
                bucket["wins"] += 1
        result = []
        for symbol, bucket in sorted(buckets.items(), key=lambda pair: pair[0]):
            total = int(bucket["trades"])
            result.append(
                {
                    "symbol": symbol,
                    "trades": total,
                    "net_profit": bucket["net_profit"],
                    "win_rate_pct": (bucket["wins"] / total * 100.0) if total else 0.0,
                }
            )
        return result
