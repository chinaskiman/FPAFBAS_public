from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.sql import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .candle_cache import Candle
from .config import get_data_dir
from .derived_cache import DerivedSeries

logger = logging.getLogger(__name__)


def _tf_to_ms(tf: str) -> int:
    mapping = {
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
        "1w": 7 * 24 * 60 * 60 * 1000,
    }
    return mapping.get(tf, 0)


def _default_journal_url() -> str:
    path = get_data_dir() / "journal.db"
    return f"sqlite:///{path.as_posix()}"


def get_journal_db_url() -> str:
    return os.getenv("JOURNAL_DB_URL") or _default_journal_url()


def _safe_db_label(url: str) -> str:
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        # strip password for logging
        parts = url.split("@")
        if len(parts) == 2 and ":" in parts[0]:
            user_part = parts[0].split("://", 1)[1].split(":", 1)[0]
            return f"postgres://{user_part}@{parts[1]}"
    return url


def compute_signal_id(fields: Iterable[str]) -> str:
    payload = "|".join([value for value in fields if value])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class JournalRecord:
    signal_id: str
    created_at_ms: int
    symbol: str
    timeframe: str
    direction: str
    signal_type: Optional[str]
    level: Optional[float]
    signal_candle_close_ts_ms: int
    entry_mode: str
    planned_entry_time_ms: Optional[int]
    entry_time_ms: Optional[int]
    entry_price: Optional[float]
    stop_price: Optional[float]
    stop_rule: Optional[str]
    payload_json: str
    notification_json: str
    indicators_json: str
    candles_json: str
    meta_json: str
    tp_plan_json: str
    management_rules_json: str


class JournalStore:
    def __init__(self, db_url: Optional[str] = None) -> None:
        self.db_url = db_url or get_journal_db_url()
        self.engine: Engine = create_engine(self.db_url, future=True)
        self.metadata = MetaData()
        self.table = Table(
            "journal_signals",
            self.metadata,
            Column("signal_id", String, primary_key=True),
            Column("created_at_ms", Integer, nullable=False),
            Column("symbol", String, nullable=False),
            Column("timeframe", String, nullable=False),
            Column("direction", String, nullable=False),
            Column("signal_type", String),
            Column("level", Float),
            Column("signal_candle_close_ts_ms", Integer, nullable=False),
            Column("entry_mode", String),
            Column("planned_entry_time_ms", Integer),
            Column("entry_time_ms", Integer),
            Column("entry_price", Float),
            Column("stop_price", Float),
            Column("stop_rule", Text),
            Column("payload_json", Text),
            Column("notification_json", Text),
            Column("indicators_json", Text),
            Column("candles_json", Text),
            Column("meta_json", Text),
            Column("tp_plan_json", Text),
            Column("management_rules_json", Text),
            Index("idx_journal_symbol_tf_created", "symbol", "timeframe", "created_at_ms"),
        )

    def init_db(self) -> None:
        self.metadata.create_all(self.engine)
        logger.info("Journal DB ready (%s)", _safe_db_label(self.db_url))

    def insert_record(self, record: JournalRecord) -> bool:
        values = record.__dict__.copy()
        dialect = self.engine.dialect.name
        if dialect == "postgresql":
            stmt = pg_insert(self.table).values(**values).on_conflict_do_nothing(index_elements=["signal_id"])
        elif dialect == "sqlite":
            stmt = insert(self.table).values(**values).prefix_with("OR IGNORE")
        else:
            stmt = insert(self.table).values(**values)
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
        return result.rowcount == 1

    def fill_entry_from_candle(self, symbol: str, tf: str, candle: Candle) -> int:
        planned_time_ms = candle.close_time
        update_stmt = (
            self.table.update()
            .where(self.table.c.symbol == symbol.upper())
            .where(self.table.c.timeframe == tf)
            .where(self.table.c.entry_price.is_(None))
            .where(self.table.c.planned_entry_time_ms == planned_time_ms)
            .values(entry_price=candle.open, entry_time_ms=planned_time_ms)
        )
        with self.engine.begin() as conn:
            result = conn.execute(update_stmt)
            if result.rowcount:
                rows = conn.execute(
                    select(self.table.c.signal_id, self.table.c.payload_json, self.table.c.stop_price)
                    .where(self.table.c.symbol == symbol.upper())
                    .where(self.table.c.timeframe == tf)
                    .where(self.table.c.planned_entry_time_ms == planned_time_ms)
                ).fetchall()
                for row in rows:
                    payload = _safe_load_json(row.payload_json)
                    entry = payload.get("entry", {})
                    entry["price"] = candle.open
                    entry["time_ms"] = planned_time_ms
                    payload["entry"] = entry
                    stop_price = row.stop_price
                    payload = _attach_tp_prices(payload, stop_price, candle.open)
                    conn.execute(
                        self.table.update()
                        .where(self.table.c.signal_id == row.signal_id)
                        .values(payload_json=json.dumps(payload))
                    )
            return int(result.rowcount or 0)

    def list_signals(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        stmt = select(self.table)
        if symbol:
            stmt = stmt.where(self.table.c.symbol == symbol.upper())
        if timeframe:
            stmt = stmt.where(self.table.c.timeframe == timeframe)
        if from_ms is not None:
            stmt = stmt.where(self.table.c.created_at_ms >= from_ms)
        if to_ms is not None:
            stmt = stmt.where(self.table.c.created_at_ms <= to_ms)
        stmt = stmt.order_by(self.table.c.created_at_ms.desc()).limit(limit).offset(offset)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_signal(self, signal_id: str) -> Optional[dict]:
        stmt = select(self.table).where(self.table.c.signal_id == signal_id)
        with self.engine.begin() as conn:
            row = conn.execute(stmt).fetchone()
        return _row_to_dict(row) if row else None

    def iter_signals(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        from_ms: Optional[int] = None,
        to_ms: Optional[int] = None,
    ) -> Iterable[dict]:
        stmt = select(self.table)
        if symbol:
            stmt = stmt.where(self.table.c.symbol == symbol.upper())
        if timeframe:
            stmt = stmt.where(self.table.c.timeframe == timeframe)
        if from_ms is not None:
            stmt = stmt.where(self.table.c.created_at_ms >= from_ms)
        if to_ms is not None:
            stmt = stmt.where(self.table.c.created_at_ms <= to_ms)
        stmt = stmt.order_by(self.table.c.created_at_ms.desc())
        with self.engine.begin() as conn:
            for row in conn.execute(stmt):
                yield _row_to_dict(row)


def _row_to_dict(row) -> dict:
    data = dict(row._mapping) if row else {}
    for key in ("payload_json", "notification_json", "indicators_json", "candles_json", "meta_json", "tp_plan_json", "management_rules_json"):
        if key in data:
            parsed = _safe_load_json(data[key])
            data[key.replace("_json", "")] = parsed
            data.pop(key, None)
    return data


def _safe_load_json(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


def _attach_tp_prices(payload: dict, stop_price: Optional[float], entry_price: Optional[float]) -> dict:
    if stop_price is None or entry_price is None:
        return payload
    tp_plan = payload.get("take_profit_plan", {})
    direction = payload.get("direction")
    if not tp_plan:
        return payload
    risk = entry_price - stop_price if direction == "long" else stop_price - entry_price
    if risk <= 0:
        return payload
    for key in ("tp1", "tp2", "tp3"):
        plan = tp_plan.get(key)
        if not isinstance(plan, dict):
            continue
        rr = plan.get("rr")
        if rr is None:
            continue
        if direction == "long":
            plan["price"] = entry_price + rr * risk
        else:
            plan["price"] = entry_price - rr * risk
        tp_plan[key] = plan
    payload["take_profit_plan"] = tp_plan
    return payload


def build_journal_record(
    *,
    openings: dict,
    signal: dict,
    candles: list[Candle],
    strategy_id: str,
    strategy_version: str,
    notification: dict,
    now_ms: int,
) -> JournalRecord:
    symbol = openings.get("symbol")
    tf = openings.get("tf")
    direction = signal.get("direction")
    signal_time = signal.get("time")
    signal_type = signal.get("type")
    level = signal.get("level")

    fields = [
        symbol,
        tf,
        direction,
        str(signal_time) if signal_time else "",
        signal_type or "",
        str(level) if level is not None else "",
        strategy_id,
        strategy_version,
    ]
    signal_id = compute_signal_id(fields)

    lookback = candles[-100:] if len(candles) >= 100 else candles
    candles_payload = [
        {
            "ts_ms": candle.close_time,
            "o": candle.open,
            "h": candle.high,
            "l": candle.low,
            "c": candle.close,
            "v": candle.volume,
        }
        for candle in lookback
    ]

    derived = DerivedSeries.recompute(candles)
    indicators = {
        "rsi14": derived.rsi14[-len(lookback):],
        "atr5": derived.atr5[-len(lookback):],
        "sma7": derived.sma7[-len(lookback):],
        "sma25": derived.sma25[-len(lookback):],
        "sma99": derived.sma99[-len(lookback):],
        "di_plus": derived.di_plus[-len(lookback):],
        "di_minus": derived.di_minus[-len(lookback):],
        "adx14": derived.adx14[-len(lookback):],
        "vol_ma10": derived.vol_ma10[-len(lookback):],
        "vol_highest10_last": derived.vol_highest10_last,
    }
    indicators["last"] = {
        "rsi14": _last_value(indicators["rsi14"]),
        "atr5": _last_value(indicators["atr5"]),
        "sma7": _last_value(indicators["sma7"]),
        "sma25": _last_value(indicators["sma25"]),
        "sma99": _last_value(indicators["sma99"]),
        "di_plus": _last_value(indicators["di_plus"]),
        "di_minus": _last_value(indicators["di_minus"]),
        "adx14": _last_value(indicators["adx14"]),
        "vol_ma10": _last_value(indicators["vol_ma10"]),
    }

    timeframe_ms = _tf_to_ms(tf)
    planned_entry_time_ms = signal_time + timeframe_ms if signal_time and timeframe_ms else None
    entry_price = None
    entry_time_ms = None
    if planned_entry_time_ms:
        for candle in reversed(candles):
            if candle.close_time == planned_entry_time_ms:
                entry_price = candle.open
                entry_time_ms = planned_entry_time_ms
                break

    entry = {
        "mode": "NEXT_OPEN",
        "planned_time_ms": planned_entry_time_ms,
        "time_ms": entry_time_ms,
        "price": entry_price,
    }

    stop_price = signal.get("sl")
    stop_rule = signal.get("sl_reason")

    take_profit_plan = {
        "tp1": {"rr": 2, "qty_pct": 30, "price": None},
        "tp2": {"rr": 5, "qty_pct": 40, "price": None},
        "tp3": {"rr": 10, "qty_pct": 20, "price": None},
        "runner": {"qty_pct": 10, "rule": "until SL"},
    }
    management_rules = [
        "Move SL to breakeven after TP1",
        "After TP1, trail SL via Dow Theory / below/after blow-off candle (manual/heuristic)",
    ]

    signal_candle = signal.get("candle")
    if not signal_candle and candles_payload:
        last_candle = candles_payload[-1]
        signal_candle = {
            "close_ts_ms": last_candle["ts_ms"],
            "open": last_candle["o"],
            "high": last_candle["h"],
            "low": last_candle["l"],
            "close": last_candle["c"],
            "volume": last_candle["v"],
        }
    payload = {
        "signal_id": signal_id,
        "created_at_ms": now_ms,
        "symbol": symbol,
        "timeframe": tf,
        "direction": direction,
        "strategy": {"id": strategy_id, "version": strategy_version},
        "signal_candle": signal_candle,
        "entry": entry,
        "stop": {"price": stop_price, "rule": stop_rule},
        "take_profit_plan": take_profit_plan,
        "management_rules": management_rules,
        "indicators": indicators,
        "candles_lookback": candles_payload,
        "notification": notification,
        "source": {"mode": "live"},
    }

    if planned_entry_time_ms and stop_price and entry.get("price"):
        payload = _attach_tp_prices(payload, stop_price, entry.get("price"))

    return JournalRecord(
        signal_id=signal_id,
        created_at_ms=now_ms,
        symbol=symbol,
        timeframe=tf,
        direction=direction,
        signal_type=signal_type,
        level=level,
        signal_candle_close_ts_ms=signal_time or 0,
        entry_mode="NEXT_OPEN",
        planned_entry_time_ms=planned_entry_time_ms,
        entry_time_ms=entry.get("time_ms"),
        entry_price=entry.get("price"),
        stop_price=stop_price,
        stop_rule=stop_rule,
        payload_json=json.dumps(payload),
        notification_json=json.dumps(notification),
        indicators_json=json.dumps(indicators),
        candles_json=json.dumps(candles_payload),
        meta_json=json.dumps({"strategy_id": strategy_id, "strategy_version": strategy_version, "source": "live"}),
        tp_plan_json=json.dumps(take_profit_plan),
        management_rules_json=json.dumps(management_rules),
    )


def _last_value(values: list[Optional[float]]) -> Optional[float]:
    for value in reversed(values):
        if value is not None:
            return value
    return None
