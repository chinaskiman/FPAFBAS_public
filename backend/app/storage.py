from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "app.db"

ALERTS_SCHEMA = '''
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    type TEXT NOT NULL,
    direction TEXT NOT NULL,
    level REAL,
    time INTEGER NOT NULL,
    entry REAL,
    sl REAL,
    sl_reason TEXT,
    hwc_bias TEXT,
    payload_json TEXT,
    notified INTEGER NOT NULL DEFAULT 0,
    notify_error TEXT
);
'''


def get_db_path() -> Path:
    path = os.getenv("SQLITE_PATH")
    if path:
        return Path(path)
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return Path(env_dir) / "app.db"
    local_dir = Path(__file__).resolve().parents[2] / "data"
    return local_dir / "app.db"


def check_db() -> bool:
    try:
        conn = _connect()
        try:
            conn.execute("SELECT 1")
            return True
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return False


def _connect() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(ALERTS_SCHEMA)
        _migrate_alerts(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate_alerts(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(alerts)")
    existing = {row["name"] for row in cur.fetchall()}
    columns = [
        ("created_at", "INTEGER"),
        ("type", "TEXT"),
        ("time", "INTEGER"),
        ("entry", "REAL"),
        ("sl", "REAL"),
        ("sl_reason", "TEXT"),
        ("hwc_bias", "TEXT"),
        ("payload_json", "TEXT"),
        ("notified", "INTEGER"),
        ("notify_error", "TEXT"),
    ]
    for name, column_type in columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE alerts ADD COLUMN {name} {column_type}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_key ON alerts(symbol, tf, type, direction, level, time)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC)")


def insert_alert_if_new(alert: dict) -> Tuple[bool, Optional[dict]]:
    conn = _connect()
    try:
        created_at = int(time.time() * 1000)
        payload_json = json.dumps(alert.get("payload")) if alert.get("payload") is not None else None
        cur = conn.execute(
            "INSERT OR IGNORE INTO alerts "
            "(created_at, symbol, tf, type, direction, level, time, entry, sl, sl_reason, hwc_bias, payload_json, notified, notify_error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                created_at,
                alert["symbol"],
                alert["tf"],
                alert["type"],
                alert["direction"],
                alert.get("level"),
                alert["time"],
                alert.get("entry"),
                alert.get("sl"),
                alert.get("sl_reason"),
                alert.get("hwc_bias"),
                payload_json,
                0,
                None,
            ),
        )
        conn.commit()
        inserted = cur.rowcount == 1
        if inserted:
            row_id = cur.lastrowid
        else:
            row_id = _get_alert_id(conn, alert)
        row = _get_alert_by_id(conn, row_id) if row_id else None
        return inserted, row
    finally:
        conn.close()


def _get_alert_id(conn: sqlite3.Connection, alert: dict) -> Optional[int]:
    cur = conn.execute(
        "SELECT id FROM alerts WHERE symbol=? AND tf=? AND type=? AND direction=? AND level=? AND time=?",
        (
            alert["symbol"],
            alert["tf"],
            alert["type"],
            alert["direction"],
            alert.get("level"),
            alert["time"],
        ),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def exists_alert(
    symbol: str,
    tf: str,
    alert_type: str,
    direction: str,
    level: float | None,
    time_ms: int,
) -> bool:
    conn = _connect()
    try:
        if level is None:
            cur = conn.execute(
                "SELECT 1 FROM alerts WHERE symbol=? AND tf=? AND type=? AND direction=? AND level IS NULL AND time=?",
                (symbol, tf, alert_type, direction, time_ms),
            )
        else:
            cur = conn.execute(
                "SELECT 1 FROM alerts WHERE symbol=? AND tf=? AND type=? AND direction=? AND level=? AND time=?",
                (symbol, tf, alert_type, direction, level, time_ms),
            )
        return cur.fetchone() is not None
    finally:
        conn.close()


def _get_alert_by_id(conn: sqlite3.Connection, alert_id: int | None) -> Optional[dict]:
    if alert_id is None:
        return None
    cur = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cur.fetchone()
    return _row_to_alert(row) if row else None


def mark_notified(alert_id: int, ok: bool, error: str | None = None) -> None:
    conn = _connect()
    try:
        conn.execute(
            "UPDATE alerts SET notified = ?, notify_error = ? WHERE id = ?",
            (1 if ok else 0, error, alert_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_alerts(symbol: str, since_ms: int) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT COUNT(1) AS count FROM alerts WHERE symbol = ? AND created_at >= ?",
            (symbol.upper(), since_ms),
        )
        row = cur.fetchone()
        return int(row["count"]) if row else 0
    finally:
        conn.close()


def count_alerts_global(since_ms: int) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT COUNT(1) AS count FROM alerts WHERE created_at >= ?",
            (since_ms,),
        )
        row = cur.fetchone()
        return int(row["count"]) if row else 0
    finally:
        conn.close()


def last_alert_time(
    symbol: str, tf: str, alert_type: str, direction: str, level: float | None
) -> Optional[int]:
    conn = _connect()
    try:
        if level is None:
            cur = conn.execute(
                "SELECT MAX(time) AS last_time FROM alerts "
                "WHERE symbol=? AND tf=? AND type=? AND direction=? AND level IS NULL",
                (symbol.upper(), tf, alert_type, direction),
            )
        else:
            cur = conn.execute(
                "SELECT MAX(time) AS last_time FROM alerts "
                "WHERE symbol=? AND tf=? AND type=? AND direction=? AND level=?",
                (symbol.upper(), tf, alert_type, direction, level),
            )
        row = cur.fetchone()
        return int(row["last_time"]) if row and row["last_time"] is not None else None
    finally:
        conn.close()


def alerts_stats(since_ms: int | None = None) -> dict:
    conn = _connect()
    try:
        clauses = []
        params: List[object] = []
        if since_ms is not None:
            clauses.append("created_at >= ?")
            params.append(since_ms)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        cur = conn.execute(f"SELECT COUNT(1) AS count FROM alerts {where}", params)
        row = cur.fetchone()
        total = int(row["count"]) if row else 0

        cur = conn.execute(f"SELECT type, COUNT(1) AS count FROM alerts {where} GROUP BY type", params)
        by_type = {item["type"]: int(item["count"]) for item in cur.fetchall()}

        cur = conn.execute(
            f"SELECT symbol, COUNT(1) AS count FROM alerts {where} GROUP BY symbol ORDER BY count DESC LIMIT 10",
            params,
        )
        by_symbol = [{"symbol": item["symbol"], "count": int(item["count"])} for item in cur.fetchall()]

        reason_where = f"{where} AND notify_error IS NOT NULL" if where else "WHERE notify_error IS NOT NULL"
        cur = conn.execute(
            f"SELECT notify_error, COUNT(1) AS count FROM alerts {reason_where} GROUP BY notify_error",
            params,
        )
        by_reason = {}
        for item in cur.fetchall():
            key = item["notify_error"]
            if key is None:
                continue
            if isinstance(key, str) and ":" in key:
                key = key.split(":", 1)[1]
            by_reason[key] = by_reason.get(key, 0) + int(item["count"])

        return {"total": total, "by_type": by_type, "by_symbol": by_symbol, "by_reason": by_reason}
    finally:
        conn.close()


def list_alerts(
    limit: int = 200,
    offset: int = 0,
    symbol: str | None = None,
    tf: str | None = None,
    alert_type: str | None = None,
    direction: str | None = None,
    notified: int | None = None,
    since_ms: int | None = None,
    until_ms: int | None = None,
    include_payload: bool = False,
) -> Tuple[List[dict], int]:
    conn = _connect()
    try:
        clauses = []
        params: List[object] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if tf:
            clauses.append("tf = ?")
            params.append(tf)
        if alert_type:
            clauses.append("type = ?")
            params.append(alert_type)
        if direction:
            clauses.append("direction = ?")
            params.append(direction)
        if notified in {0, 1}:
            clauses.append("notified = ?")
            params.append(notified)
        if since_ms is not None:
            clauses.append("created_at >= ?")
            params.append(since_ms)
        if until_ms is not None:
            clauses.append("created_at <= ?")
            params.append(until_ms)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        count_params = list(params)
        cur = conn.execute(f"SELECT COUNT(1) AS count FROM alerts {where}", count_params)
        row = cur.fetchone()
        total = int(row["count"]) if row else 0

        params.extend([limit, offset])
        cur = conn.execute(
            f"SELECT * FROM alerts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = cur.fetchall()
        return [_row_to_alert(row, include_payload=include_payload) for row in rows], total
    finally:
        conn.close()


def get_alert(alert_id: int) -> Optional[dict]:
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        row = cur.fetchone()
        return _row_to_alert(row, include_payload=True) if row else None
    finally:
        conn.close()


def _row_to_alert(row: sqlite3.Row, include_payload: bool = False) -> dict:
    item = dict(row)
    payload = item.pop("payload_json", None)
    if payload and include_payload:
        try:
            item["payload"] = json.loads(payload)
        except json.JSONDecodeError:
            item["payload"] = payload
    return item
