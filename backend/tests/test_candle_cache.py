from app.candle_cache import Candle, CandleCache


def _candle(seq: int) -> Candle:
    return Candle(
        open_time=seq,
        close_time=seq + 1,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0,
    )


def test_cache_appends_and_truncates() -> None:
    cache = CandleCache(maxlen=3)
    for idx in range(5):
        cache.append(_candle(idx))

    assert len(cache) == 3
    recent = cache.list_recent(10)
    assert [candle.open_time for candle in recent] == [2, 3, 4]


def test_cache_append_if_new_replaces_last() -> None:
    cache = CandleCache(maxlen=3)
    cache.append(_candle(1))
    cache.append_if_new(_candle(2))
    cache.append_if_new(_candle(2))

    assert len(cache) == 2
    recent = cache.list_recent(2)
    assert recent[-1].open_time == 2
