from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Dict, Iterable, List, Tuple

import websocket

from .binance_client import DEFAULT_WS_BASE, BinanceRestClient
from .candle_cache import Candle, CandleCache
from .derived_cache import DerivedSeries
from .hwc import compute_timeframe_bias

logger = logging.getLogger(__name__)

STREAM_TFS = ("15m", "1h")
BOOTSTRAP_TFS = ("1w", "1d", "4h", "1h", "15m")
BOOTSTRAP_LIMITS = {
    "15m": 1000,
    "1h": 1000,
    "4h": 1500,
    "1d": 1500,
    "1w": 600,
}


class IngestService:
    def __init__(
        self,
        rest_client: BinanceRestClient,
        cache_maxlen: int = 1200,
        ws_base: str | None = None,
        rest_limits: Dict[str, int] | None = None,
        journal_store=None,
    ) -> None:
        self.rest_client = rest_client
        self.cache_maxlen = cache_maxlen
        self.ws_base = ws_base or os.getenv("BINANCE_FAPI_WS", DEFAULT_WS_BASE)
        self.rest_limits = rest_limits or BOOTSTRAP_LIMITS
        self.journal = journal_store
        self.caches: Dict[Tuple[str, str], CandleCache] = {}
        self.derived: Dict[Tuple[str, str], DerivedSeries] = {}
        self.biases: Dict[Tuple[str, str], dict] = {}
        self.tracked: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._ws_thread: threading.Thread | None = None
        self._ws: websocket.WebSocketApp | None = None

    def _cache_maxlen_for_tf(self, tf: str) -> int:
        if tf == "1w":
            return 800
        if tf in ("1d", "4h"):
            return 2000
        return self.cache_maxlen

    def bootstrap(self, symbols: Iterable[str]) -> None:
        symbols_list = [symbol.upper() for symbol in symbols]
        if not symbols_list:
            logger.info("No enabled symbols; skipping bootstrap.")
            return

        for symbol in symbols_list:
            with self._lock:
                self.tracked[symbol] = list(BOOTSTRAP_TFS)
            for tf in BOOTSTRAP_TFS:
                limit = self.rest_limits[tf]
                logger.info("Bootstrapping %s %s with %s candles", symbol, tf, limit)
                candles = self.rest_client.get_klines(symbol, tf, limit)
                cache = CandleCache(maxlen=self._cache_maxlen_for_tf(tf))
                cache.extend(candles)
                with self._lock:
                    self.caches[(symbol, tf)] = cache
                self._recompute(symbol, tf, cache)
                if tf in ("1w", "1d"):
                    self._recompute_bias(symbol, tf, cache)

    def start_streaming(self, symbols: Iterable[str]) -> None:
        symbols_list = [symbol.upper() for symbol in symbols]
        if not symbols_list:
            logger.info("No enabled symbols; skipping websocket streaming.")
            return
        if self._ws_thread and self._ws_thread.is_alive():
            return

        self._stop_event.clear()
        self._ws_thread = threading.Thread(
            target=self._run_ws,
            args=(symbols_list,),
            daemon=True,
            name="binance-ws",
        )
        self._ws_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                logger.exception("Failed to close websocket cleanly")
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5)

    def list_candles(self, symbol: str, tf: str, limit: int) -> List[dict] | None:
        cache = self.get_cache(symbol, tf)
        if cache is None:
            return None
        return cache.to_dicts(limit)

    def list_indicators(self, symbol: str, tf: str, limit: int) -> dict | None:
        key = (symbol.upper(), tf)
        with self._lock:
            derived = self.derived.get(key)
        if derived is None:
            cache = self.get_cache(symbol, tf)
            if cache is None:
                return None
            self._recompute(symbol, tf, cache)
            with self._lock:
                derived = self.derived.get(key)
        if derived is None:
            return None
        return derived.to_dict(limit)

    def get_cached_range(
        self,
        symbol: str,
        tf: str,
        from_ms: int,
        to_ms: int,
        limit: int | None = None,
    ) -> List[Candle]:
        cache = self.get_cache(symbol, tf)
        if cache is None:
            return []
        candles = cache.list_all()
        filtered = [candle for candle in candles if from_ms <= candle.close_time <= to_ms]
        if limit is not None and limit > 0:
            filtered = filtered[-limit:]
        return filtered

    def get_bias(self, symbol: str, tf: str) -> dict | None:
        with self._lock:
            bias = self.biases.get((symbol.upper(), tf))
        if bias is not None:
            return bias
        cache = self.get_cache(symbol, tf)
        if cache is None:
            return None
        bias = compute_timeframe_bias(cache.list_all())
        with self._lock:
            self.biases[(symbol.upper(), tf)] = bias
        return bias

    def list_symbols(self) -> List[dict]:
        with self._lock:
            items = sorted(self.tracked.items())
        return [{"symbol": symbol, "tfs": tfs} for symbol, tfs in items]

    def get_cache(self, symbol: str, tf: str) -> CandleCache | None:
        with self._lock:
            return self.caches.get((symbol.upper(), tf))

    def append_candle(self, symbol: str, tf: str, candle: Candle) -> None:
        symbol = symbol.upper()
        cache = self.get_cache(symbol, tf)
        if cache is None:
            cache = CandleCache(maxlen=self._cache_maxlen_for_tf(tf))
            with self._lock:
                self.caches[(symbol, tf)] = cache
                self.tracked.setdefault(symbol, list(BOOTSTRAP_TFS))
        cache.append_if_new(candle)
        self._recompute(symbol, tf, cache)
        if tf in ("1w", "1d"):
            self._recompute_bias(symbol, tf, cache)
        if self.journal is not None:
            try:
                self.journal.fill_entry_from_candle(symbol, tf, candle)
            except Exception as exc:  # noqa: BLE001
                logger.error("Journal entry fill failed: %s", exc)

    def _run_ws(self, symbols: List[str]) -> None:
        streams = [f"{symbol.lower()}@kline_{tf}" for symbol in symbols for tf in STREAM_TFS]
        url = f"{self.ws_base}/stream?streams=" + "/".join(streams)
        backoff = 1
        max_backoff = 60
        opened_since = False

        while not self._stop_event.is_set():
            opened_since = False

            def on_open(_: websocket.WebSocketApp) -> None:
                nonlocal opened_since, backoff
                opened_since = True
                backoff = 1
                logger.info("WebSocket connected.")

            self._ws = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
            )

            self._ws.run_forever(ping_interval=20, ping_timeout=10)

            if self._stop_event.is_set():
                break

            if not opened_since:
                backoff = min(backoff * 2, max_backoff)
            logger.warning("WebSocket disconnected; reconnecting in %s seconds", backoff)
            time.sleep(backoff)

    def _on_ws_message(self, _: websocket.WebSocketApp, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Failed to decode websocket payload")
            return

        data = payload.get("data", payload)
        if data.get("e") != "kline":
            return
        kline = data.get("k", {})
        if not kline.get("x"):
            return

        interval = kline.get("i")
        if interval not in STREAM_TFS:
            return
        symbol = data.get("s") or kline.get("s")
        if not symbol:
            return

        candle = Candle.from_ws_kline(kline)
        self.append_candle(symbol, interval, candle)

    @staticmethod
    def _on_ws_error(_: websocket.WebSocketApp, error: Exception) -> None:
        logger.error("WebSocket error: %s", error)

    @staticmethod
    def _on_ws_close(_: websocket.WebSocketApp, code: int, reason: str) -> None:
        logger.warning("WebSocket closed: %s %s", code, reason)

    def _recompute(self, symbol: str, tf: str, cache: CandleCache) -> None:
        candles = cache.list_all()
        derived = DerivedSeries.recompute(candles)
        with self._lock:
            self.derived[(symbol.upper(), tf)] = derived

    def _recompute_bias(self, symbol: str, tf: str, cache: CandleCache) -> None:
        bias = compute_timeframe_bias(cache.list_all())
        with self._lock:
            self.biases[(symbol.upper(), tf)] = bias
