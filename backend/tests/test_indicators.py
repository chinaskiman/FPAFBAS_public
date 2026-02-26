from app.indicators import atr, dmi_adx, rsi, sma


def test_sma_basic() -> None:
    values = [1, 2, 3, 4, 5]
    result = sma(values, 3)
    assert result == [None, None, 2.0, 3.0, 4.0]


def test_rsi_trending_up() -> None:
    values = list(range(1, 20))
    result = rsi(values, 14)
    assert result[:14].count(None) == 14
    assert result[-1] == 100.0


def test_rsi_trending_down() -> None:
    values = list(range(20, 0, -1))
    result = rsi(values, 14)
    assert result[:14].count(None) == 14
    assert result[-1] == 0.0


def test_atr_constant_range() -> None:
    highs = [10, 10, 10, 10, 10, 10]
    lows = [9, 9, 9, 9, 9, 9]
    closes = [9.5, 9.5, 9.5, 9.5, 9.5, 9.5]
    result = atr(highs, lows, closes, 5)
    assert result[4] == 1.0
    assert result[-1] == 1.0


def test_dmi_adx_shapes_and_direction() -> None:
    highs = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]
    lows = [9, 9.5, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
    closes = [9.5, 10.5, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
    di_plus, di_minus, adx = dmi_adx(highs, lows, closes, 14)
    assert len(di_plus) == len(highs)
    assert len(di_minus) == len(highs)
    assert len(adx) == len(highs)
    assert di_plus[-1] is not None
    assert di_minus[-1] is not None
    assert di_plus[-1] > di_minus[-1]
