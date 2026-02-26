from app.quality_controls import score_signal


def test_quality_scoring_basic() -> None:
    signal = {
        "type": "break",
        "direction": "long",
        "context": {
            "vol_ma5_slope_ok": True,
            "pullback_vol_decline": False,
            "not_at_peak_long": True,
            "rsi_distance": 12.5,
        },
    }
    score, badges, reasons = score_signal(signal)
    assert score == 62
    assert badges["vol_ok"] is True
    assert badges["di_ok"] is True
    assert badges["pullback_ok"] is False
    assert "vol_ma5_slope_ok" in reasons
    assert "di_not_at_peak" in reasons


def test_quality_scoring_fakeout_bonus() -> None:
    signal = {
        "type": "fakeout",
        "direction": "short",
        "context": {
            "vol_ma5_slope_ok": True,
            "pullback_vol_decline": True,
            "not_at_peak_short": True,
            "rsi_distance": 30,
        },
    }
    score, badges, reasons = score_signal(signal)
    assert score == 100
    assert badges["di_ok"] is True
    assert "fakeout_bonus" in reasons
