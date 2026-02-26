from __future__ import annotations

from datetime import datetime, time as dtime
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field


class QuietHours(BaseModel):
    enabled: bool = False
    start: str = "23:00"
    end: str = "07:00"
    tz: str = "Europe/Paris"


class QualitySettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cooldown_minutes_by_type: Dict[str, int] = Field(
        default_factory=lambda: {"break": 60, "setup": 45, "fakeout": 60}
    )
    min_score_by_type: Dict[str, int] = Field(
        default_factory=lambda: {"break": 60, "setup": 55, "fakeout": 55}
    )
    max_alerts_per_symbol_per_hour: int = 6
    max_alerts_global_per_hour: int = 30
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    di_peak_window_for_quality: int = 20
    di_peak_ratio_threshold: float = 0.98


def score_signal(signal: Dict[str, Any]) -> Tuple[int, Dict[str, bool], List[str]]:
    context = signal.get("context") or {}
    direction = signal.get("direction")

    vol_ok = context.get("vol_ma5_slope_ok") is True
    pullback_ok = context.get("pullback_vol_decline") is True
    if direction == "long":
        di_ok = context.get("not_at_peak_long") is True
    elif direction == "short":
        di_ok = context.get("not_at_peak_short") is True
    else:
        di_ok = False

    rsi_distance = _to_float(context.get("rsi_distance"))

    score = 0
    reasons: List[str] = []
    if vol_ok:
        score += 25
        reasons.append("vol_ma5_slope_ok")
    if pullback_ok:
        score += 15
        reasons.append("pullback_vol_decline")
    if di_ok:
        score += 25
        reasons.append("di_not_at_peak")
    if rsi_distance is not None:
        rsi_points = min(20.0, rsi_distance)
        score += int(rsi_points)
        reasons.append(f"rsi_distance={rsi_distance:.2f}")
    if signal.get("type") == "fakeout":
        score += 15
        reasons.append("fakeout_bonus")

    badges = {"vol_ok": vol_ok, "di_ok": di_ok, "pullback_ok": pullback_ok}
    return score, badges, reasons


def should_suppress_due_to_quiet_hours(now_ms: int, settings: QualitySettings) -> bool:
    quiet = settings.quiet_hours
    if not quiet.enabled:
        return False
    tz = quiet.tz or "UTC"
    try:
        zone = ZoneInfo(tz)
    except Exception:
        zone = ZoneInfo("UTC")
    local_dt = datetime.fromtimestamp(now_ms / 1000, tz=zone)
    start = _parse_hhmm(quiet.start)
    end = _parse_hhmm(quiet.end)
    current = local_dt.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _parse_hhmm(value: str) -> dtime:
    try:
        parts = value.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return dtime(hour=hour, minute=minute)
    except Exception:
        return dtime(hour=0, minute=0)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return num
