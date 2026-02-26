from __future__ import annotations

import os
from typing import Iterable, List

import requests

from .candle_cache import Candle

DEFAULT_REST_BASE = "https://fapi.binance.com"
DEFAULT_WS_BASE = "wss://fstream.binance.com"


def parse_klines(payload: Iterable[list]) -> List[Candle]:
    candles: List[Candle] = []
    for item in payload:
        candles.append(Candle.from_rest_kline(item))
    candles.sort(key=lambda candle: candle.open_time)
    return candles


class BinanceRestClient:
    def __init__(self, rest_base: str | None = None, session: requests.Session | None = None) -> None:
        self.rest_base = rest_base or os.getenv("BINANCE_FAPI_REST", DEFAULT_REST_BASE)
        self._session = session or requests.Session()

    def get_klines(self, symbol: str, interval: str, limit: int) -> List[Candle]:
        url = f"{self.rest_base}/fapi/v1/klines"
        response = self._session.get(
            url,
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=15,
        )
        response.raise_for_status()
        return parse_klines(response.json())
