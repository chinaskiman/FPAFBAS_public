from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from app.quality_controls import QualitySettings, QuietHours, should_suppress_due_to_quiet_hours


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def test_quiet_hours_cross_midnight() -> None:
    settings = QualitySettings(
        quiet_hours=QuietHours(enabled=True, start="23:00", end="07:00", tz="Europe/Paris")
    )
    try:
        tz = ZoneInfo("Europe/Paris")
    except ZoneInfoNotFoundError:
        pytest.skip("ZoneInfo Europe/Paris not available")
    dt_inside = datetime(2026, 2, 3, 23, 30, tzinfo=tz)
    assert should_suppress_due_to_quiet_hours(_to_ms(dt_inside), settings) is True

    dt_inside2 = datetime(2026, 2, 4, 2, 0, tzinfo=tz)
    assert should_suppress_due_to_quiet_hours(_to_ms(dt_inside2), settings) is True

    dt_outside = datetime(2026, 2, 4, 8, 0, tzinfo=tz)
    assert should_suppress_due_to_quiet_hours(_to_ms(dt_outside), settings) is False
