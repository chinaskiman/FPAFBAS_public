import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.alert_poller import AlertPoller
from app.candle_cache import Candle, CandleCache
from app.journal import JournalStore, build_journal_record
from app.main import app
from app.storage import init_db


class DummyIngest:
    def __init__(self, cache: CandleCache) -> None:
        self._cache = cache

    def get_cache(self, symbol: str, tf: str) -> CandleCache | None:
        return self._cache


class DummyNotifier:
    def send_alert(self, _alert: dict):
        return True, None


def _make_watchlist() -> dict:
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "enabled": True,
                "entry_tfs": ["1h"],
                "setups": {"continuation": True, "retest": True, "fakeout": True, "setup_candle": True},
                "levels": {
                    "auto": True,
                    "max_levels": 12,
                    "cluster_tol_pct": 0.003,
                    "overrides": {"add": [], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }


def _make_candles(count: int, step_ms: int = 3_600_000) -> CandleCache:
    cache = CandleCache(maxlen=2000)
    for idx in range(count):
        open_time = idx * step_ms
        close_time = open_time + step_ms - 1
        cache.append(
            Candle(
                open_time=open_time,
                close_time=close_time,
                open=100 + idx,
                high=101 + idx,
                low=99 + idx,
                close=100 + idx,
                volume=1.0,
            )
        )
    return cache


def test_journal_insert_and_candles(monkeypatch, tmp_path):
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(json.dumps(_make_watchlist()), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))

    db_path = tmp_path / "alerts.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    init_db()

    journal_path = tmp_path / "journal.db"
    journal_url = f"sqlite:///{journal_path.as_posix()}"
    monkeypatch.setenv("JOURNAL_DB_URL", journal_url)

    cache = _make_candles(120)
    ingest = DummyIngest(cache)
    notifier = DummyNotifier()
    journal = JournalStore(journal_url)
    journal.init_db()

    signal_time = cache.list_recent(1)[0].close_time
    signal = {
        "type": "break",
        "direction": "long",
        "level": 123.0,
        "time": signal_time,
        "entry": 125.0,
        "sl": 120.0,
        "sl_reason": "atr_stop",
        "candle": {
            "open_time": signal_time - 3_600_000 + 1,
            "close_time": signal_time,
            "open": 124.0,
            "high": 126.0,
            "low": 123.0,
            "close": 125.0,
            "volume": 1.0,
        },
    }
    openings = {"symbol": "BTCUSDT", "tf": "1h", "signals": [signal]}
    alert = {
        "symbol": "BTCUSDT",
        "tf": "1h",
        "type": "break",
        "direction": "long",
        "level": 123.0,
        "time": signal_time,
        "entry": 125.0,
        "sl": 120.0,
        "sl_reason": "atr_stop",
        "hwc_bias": "bullish",
    }

    poller = AlertPoller(ingest=ingest, notifier=notifier, journal=journal)
    poller._journal_signal(openings, signal, alert)

    rows = journal.list_signals(symbol="BTCUSDT", timeframe="1h", limit=10)
    assert len(rows) == 1
    record = rows[0]
    assert len(record["candles"]) == 100
    assert record["signal_candle_close_ts_ms"] == signal_time


def test_entry_filler_updates_price(tmp_path, monkeypatch):
    journal_path = tmp_path / "journal.db"
    journal_url = f"sqlite:///{journal_path.as_posix()}"
    journal = JournalStore(journal_url)
    journal.init_db()

    cache = _make_candles(10, step_ms=60_000)
    signal_time = cache.list_recent(1)[0].close_time
    record = build_journal_record(
        openings={"symbol": "BTCUSDT", "tf": "15m"},
        signal={"direction": "long", "time": signal_time, "type": "setup", "level": 100.0},
        candles=cache.list_all(),
        strategy_id="default",
        strategy_version="1",
        notification={"channel": "telegram", "message": "test"},
        now_ms=signal_time,
    )
    journal.insert_record(record)

    planned_time = record.planned_entry_time_ms
    candle = Candle(
        open_time=planned_time - 60_000 + 1,
        close_time=planned_time,
        open=200.0,
        high=201.0,
        low=199.0,
        close=200.5,
        volume=1.0,
    )
    updated = journal.fill_entry_from_candle("BTCUSDT", "15m", candle)
    assert updated == 1
    fetched = journal.get_signal(record.signal_id)
    assert fetched["entry_price"] == 200.0


def test_export_jsonl(monkeypatch, tmp_path):
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(json.dumps(_make_watchlist()), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")

    journal_path = tmp_path / "journal.db"
    journal_url = f"sqlite:///{journal_path.as_posix()}"
    monkeypatch.setenv("JOURNAL_DB_URL", journal_url)
    journal = JournalStore(journal_url)
    journal.init_db()

    record = build_journal_record(
        openings={"symbol": "BTCUSDT", "tf": "1h"},
        signal={"direction": "long", "time": 1700000000000, "type": "break", "level": 100.0},
        candles=_make_candles(120).list_all(),
        strategy_id="default",
        strategy_version="1",
        notification={"channel": "telegram", "message": "test"},
        now_ms=1700000000000,
    )
    journal.insert_record(record)

    with TestClient(app) as client:
        response = client.get("/api/journal/export.jsonl", headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200
        lines = [line for line in response.text.splitlines() if line.strip()]
        assert len(lines) >= 1
        parsed = json.loads(lines[0])
        assert parsed["signal_id"]


def test_journal_dedupe(tmp_path):
    journal_path = tmp_path / "journal.db"
    journal_url = f"sqlite:///{journal_path.as_posix()}"
    journal = JournalStore(journal_url)
    journal.init_db()
    record = build_journal_record(
        openings={"symbol": "BTCUSDT", "tf": "1h"},
        signal={"direction": "long", "time": 1700000000000, "type": "break", "level": 100.0},
        candles=_make_candles(120).list_all(),
        strategy_id="default",
        strategy_version="1",
        notification={"channel": "telegram", "message": "test"},
        now_ms=1700000000000,
    )
    first = journal.insert_record(record)
    second = journal.insert_record(record)
    assert first is True
    assert second is False
