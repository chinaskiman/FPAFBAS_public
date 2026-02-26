from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, List


@dataclass(frozen=True)
class Candle:
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_rest_kline(cls, kline: list) -> "Candle":
        if len(kline) < 7:
            raise ValueError("Kline payload missing required fields")
        return cls(
            open_time=int(kline[0]),
            open=float(kline[1]),
            high=float(kline[2]),
            low=float(kline[3]),
            close=float(kline[4]),
            volume=float(kline[5]),
            close_time=int(kline[6]),
        )

    @classmethod
    def from_ws_kline(cls, kline: dict) -> "Candle":
        return cls(
            open_time=int(kline["t"]),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
            close_time=int(kline["T"]),
        )

    def to_dict(self) -> dict:
        return {
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class CandleCache:
    def __init__(self, maxlen: int = 1200) -> None:
        self._data: Deque[Candle] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def append(self, candle: Candle) -> None:
        with self._lock:
            self._data.append(candle)

    def append_if_new(self, candle: Candle) -> None:
        with self._lock:
            if self._data and self._data[-1].close_time == candle.close_time:
                self._data[-1] = candle
                return
            self._data.append(candle)

    def extend(self, candles: Iterable[Candle]) -> None:
        with self._lock:
            self._data.extend(candles)

    def list_recent(self, limit: int) -> List[Candle]:
        with self._lock:
            if limit <= 0:
                return []
            data = list(self._data)
        return data[-limit:]

    def list_all(self) -> List[Candle]:
        with self._lock:
            return list(self._data)

    def to_dicts(self, limit: int) -> List[dict]:
        return [candle.to_dict() for candle in self.list_recent(limit)]
