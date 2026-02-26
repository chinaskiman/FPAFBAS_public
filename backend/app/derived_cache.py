from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .candle_cache import Candle
from .indicators import atr, dmi_adx, rsi, sma


@dataclass
class DerivedSeries:
    candles: List[Candle]
    rsi14: List[Optional[float]]
    atr5: List[Optional[float]]
    sma7: List[Optional[float]]
    sma25: List[Optional[float]]
    sma99: List[Optional[float]]
    di_plus: List[Optional[float]]
    di_minus: List[Optional[float]]
    adx14: List[Optional[float]]
    vol_ma10: List[Optional[float]]
    vol_highest10_last: bool

    @classmethod
    def recompute(cls, candles: List[Candle]) -> "DerivedSeries":
        closes = [candle.close for candle in candles]
        highs = [candle.high for candle in candles]
        lows = [candle.low for candle in candles]
        volumes = [candle.volume for candle in candles]

        rsi14 = rsi(closes, 14)
        atr5 = atr(highs, lows, closes, 5)
        sma7 = sma(closes, 7)
        sma25 = sma(closes, 25)
        sma99 = sma(closes, 99)
        di_plus, di_minus, adx14 = dmi_adx(highs, lows, closes, 14)
        vol_ma10 = sma(volumes, 10)

        vol_highest10_last = False
        if len(volumes) >= 10:
            last_window = volumes[-10:]
            vol_highest10_last = volumes[-1] == max(last_window)

        return cls(
            candles=candles,
            rsi14=rsi14,
            atr5=atr5,
            sma7=sma7,
            sma25=sma25,
            sma99=sma99,
            di_plus=di_plus,
            di_minus=di_minus,
            adx14=adx14,
            vol_ma10=vol_ma10,
            vol_highest10_last=vol_highest10_last,
        )

    def to_dict(self, limit: int) -> dict:
        if limit <= 0:
            return {
                "candles": [],
                "rsi14": [],
                "atr5": [],
                "sma7": [],
                "sma25": [],
                "sma99": [],
                "di_plus": [],
                "di_minus": [],
                "adx14": [],
                "vol_ma10": [],
                "vol_highest10_last": self.vol_highest10_last,
            }

        candles = self.candles[-limit:]

        def tail(values: List[Optional[float]]) -> List[Optional[float]]:
            return values[-limit:]

        return {
            "candles": [candle.to_dict() for candle in candles],
            "rsi14": tail(self.rsi14),
            "atr5": tail(self.atr5),
            "sma7": tail(self.sma7),
            "sma25": tail(self.sma25),
            "sma99": tail(self.sma99),
            "di_plus": tail(self.di_plus),
            "di_minus": tail(self.di_minus),
            "adx14": tail(self.adx14),
            "vol_ma10": tail(self.vol_ma10),
            "vol_highest10_last": self.vol_highest10_last,
        }
