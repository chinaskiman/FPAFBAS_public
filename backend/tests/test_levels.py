import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.candle_cache import Candle, CandleCache
from app.levels import (
    _collect_points,
    apply_overrides,
    assign_rank_scores,
    balance_levels,
    build_levels_detailed,
    cluster_points,
    compute_levels,
    score_clusters,
    soft_merge_clusters,
    select_clusters_with_forced,
    select_clusters,
)
from app.main import app


def _candles_from_series(highs, lows, start=0, step=60_000):
    candles = []
    for idx, (high, low) in enumerate(zip(highs, lows)):
        open_time = start + idx * step
        close_time = open_time + step - 1
        candles.append(
            Candle(
                open_time=open_time,
                close_time=close_time,
                open=low,
                high=high,
                low=low,
                close=high,
                volume=1.0,
            )
        )
    return candles


def _candles_from_closes(closes, start=0, step=60_000):
    return _candles_from_series(closes, closes, start=start, step=step)


def _candles_from_ohlc(ohlc_rows, start=0, step=60_000):
    candles = []
    for idx, (open_val, high, low, close) in enumerate(ohlc_rows):
        open_time = start + idx * step
        close_time = open_time + step - 1
        candles.append(
            Candle(
                open_time=open_time,
                close_time=close_time,
                open=open_val,
                high=high,
                low=low,
                close=close,
                volume=1.0,
            )
        )
    return candles


class FakeIngest:
    def __init__(self, candles_by_tf):
        self._caches = {}
        for tf, candles in candles_by_tf.items():
            cache = CandleCache(maxlen=2000)
            cache.extend(candles)
            self._caches[("BTCUSDT", tf)] = cache

    def get_cache(self, symbol, tf):
        return self._caches.get((symbol.upper(), tf))

    def stop(self):
        return None


def test_compute_levels_and_ordering() -> None:
    highs = [100, 110, 120, 110, 100, 110, 120, 110, 100, 110, 120, 110, 100]
    lows = [90, 95, 100, 95, 90, 95, 100, 95, 90, 95, 100, 95, 90]
    candles = _candles_from_series(highs, lows)
    auto_levels, selected, clusters, _meta = compute_levels({"1d": candles}, tol_pct=0.2, max_levels=2)
    assert len(clusters) >= 2
    assert len(selected) == 2
    assert auto_levels == sorted(auto_levels)


def test_overrides_disable_and_pinned() -> None:
    auto_levels = [100.0, 110.0]
    pinned = [105.0]
    disabled = [100.2]
    result = apply_overrides(auto_levels, pinned, disabled, tol_pct=0.005)
    assert 100.0 not in result["final_levels"]
    assert 105.0 in result["final_levels"]


def test_max_levels_respected() -> None:
    highs = [100, 110, 120, 110, 100, 110, 120, 110, 100, 110, 120, 110, 100]
    lows = [90, 95, 100, 95, 90, 95, 100, 95, 90, 95, 100, 95, 90]
    candles = _candles_from_series(highs, lows)
    auto_levels, _, _, _meta = compute_levels({"1d": candles}, tol_pct=0.2, max_levels=1)
    assert len(auto_levels) == 1


def test_levels_api_and_watchlist_put(tmp_path, monkeypatch) -> None:
    watchlist_path = tmp_path / "watchlist.json"
    base_watchlist = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "enabled": True,
                "entry_tfs": ["15m", "1h"],
                "setups": {
                    "continuation": True,
                    "retest": True,
                    "fakeout": True,
                    "setup_candle": True,
                },
                "levels": {
                    "auto": True,
                    "max_levels": 5,
                    "cluster_tol_pct": 0.01,
                    "overrides": {"add": [123.0], "disable": []},
                },
            }
        ],
        "global": {"max_alerts_per_symbol_per_day": 6, "cooldown_minutes": 60},
    }
    watchlist_path.write_text(json.dumps(base_watchlist), encoding="utf-8")
    monkeypatch.setenv("WATCHLIST_PATH", str(watchlist_path))
    monkeypatch.setenv("DISABLE_INGESTION", "1")

    highs = [100, 110, 120, 110, 100, 110, 120, 110, 100, 110, 120, 110, 100]
    lows = [90, 95, 100, 95, 90, 95, 100, 95, 90, 95, 100, 95, 90]
    candles = _candles_from_series(highs, lows)
    with TestClient(app) as client:
        app.state.ingest = FakeIngest({"1d": candles, "1w": candles, "4h": candles})
        resp = client.get("/api/levels/BTCUSDT")
        assert resp.status_code == 200
        payload = resp.json()
        assert "auto_levels" in payload
        assert "final_levels" in payload
        assert "last_close_used" in payload
        assert "below_count" in payload
        assert "above_count" in payload
        assert "tol_pct_used" in payload

        updated = base_watchlist.copy()
        updated["symbols"][0]["levels"]["overrides"]["add"] = [123.0, 130.0]
        put_resp = client.put("/api/watchlist", json=updated)
        assert put_resp.status_code == 200

        refreshed = json.loads(watchlist_path.read_text(encoding="utf-8"))
        assert 130.0 in refreshed["symbols"][0]["levels"]["overrides"]["add"]


def test_balance_levels_price_low() -> None:
    auto_levels = [100.0, 110.0, 120.0, 130.0]
    balanced = balance_levels(auto_levels, last_close=95.0, target=4)
    assert 100.0 in balanced
    assert 120.0 in balanced


def test_balance_levels_price_high() -> None:
    auto_levels = [100.0, 110.0, 120.0, 130.0]
    balanced = balance_levels(auto_levels, last_close=150.0, target=4)
    assert 120.0 in balanced
    assert 100.0 in balanced


def test_balance_levels_one_side() -> None:
    auto_levels = [100.0, 110.0]
    balanced = balance_levels(auto_levels, last_close=200.0, target=4)
    assert balanced == [100.0, 110.0]


def test_balancing_includes_older_supports() -> None:
    highs = []
    lows = []
    total = 1300
    for idx in range(total):
        highs.append(300.0)
        lows.append(150.0)
    lows[150] = 50.0
    lows[300] = 50.3
    candles = _candles_from_series(highs, lows)
    auto_levels, _, _, meta = compute_levels({"1d": candles}, tol_pct=0.01, max_levels=4)
    assert any(level < candles[-1].close for level in auto_levels)
    assert meta["last_close_used"] == candles[-1].close


def test_deeper_lookback_finds_old_support() -> None:
    total = 1600
    highs = [100.0] * total
    lows = [80.0] * total
    lows[100] = 10.0
    lows[200] = 10.06
    highs[1200] = 200.0
    candles = _candles_from_series(highs, lows)
    auto_levels, _, _, meta = compute_levels({"1d": candles}, tol_pct=0.01, max_levels=4)
    assert meta["last_close_used"] == candles[-1].close
    assert any(level < meta["last_close_used"] for level in auto_levels)


def test_levels_have_below_and_above() -> None:
    highs = [100, 110, 120, 110, 100, 110, 120, 110, 100, 110, 120, 110, 100]
    lows = [90, 95, 100, 95, 90, 95, 100, 95, 90, 95, 100, 95, 90]
    candles = _candles_from_series(highs, lows)
    auto_levels, _, _, meta = compute_levels({"1d": candles}, tol_pct=0.2, max_levels=2)
    last_close = meta["last_close_used"]
    assert any(level < last_close for level in auto_levels)
    assert any(level > last_close for level in auto_levels)


def test_dynamic_tolerance_increases_with_atr() -> None:
    highs = [100.0] * 10
    lows = [100.0] * 10
    candles = _candles_from_series(highs, lows)
    _auto_levels, _selected, _clusters, meta = compute_levels({"1d": candles}, tol_pct=0.003, max_levels=4)
    assert meta["tol_pct_used"] == 0.003

    highs = [101.0] * 10
    lows = [100.0] * 10
    candles = _candles_from_series(highs, lows)
    _auto_levels, _selected, _clusters, meta = compute_levels({"1d": candles}, tol_pct=0.003, max_levels=4)
    assert 0.003 < meta["tol_pct_used"] < 0.007

    highs = [200.0] * 10
    lows = [0.0] * 10
    candles = _candles_from_series(highs, lows)
    _auto_levels, _selected, _clusters, meta = compute_levels({"1d": candles}, tol_pct=0.003, max_levels=4)
    assert meta["tol_pct_used"] == 0.007


def test_cluster_strength_prefers_more_touches() -> None:
    candles_1d = _candles_from_closes([100.0] * 20)
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 5, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 1, "series_len": len(candles_1d)},
        {"price": 100.0, "price_used": 100.0, "index": 6, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 2, "series_len": len(candles_1d)},
        {"price": 100.0, "price_used": 100.0, "index": 7, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 3, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 5, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 4, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 6, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 5, "series_len": len(candles_1d)},
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"1d": candles_1d}, tol_pct_used=0.003)
    strength_100 = next(c for c in clusters if c["center"] == 100.0)["strength"]
    strength_200 = next(c for c in clusters if c["center"] == 200.0)["strength"]
    assert strength_100 > strength_200


def test_touch_events_exceed_member_count() -> None:
    candles_1d = _candles_from_closes([100.0] * 30)
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 10, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 10, "series_len": len(candles_1d)},
        {"price": 100.0, "price_used": 100.0, "index": 12, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 12, "series_len": len(candles_1d)},
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"1d": candles_1d}, tol_pct_used=0.003)
    cluster = clusters[0]
    assert cluster["touch_events"] > len(cluster["members"])


def test_cluster_strength_prefers_recent_touch() -> None:
    candles_1d = _candles_from_closes([200.0] * 6 + [100.0] * 6)
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 9, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 9, "series_len": len(candles_1d)},
        {"price": 100.0, "price_used": 100.0, "index": 10, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 10, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 2, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 2, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 3, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 3, "series_len": len(candles_1d)},
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"1d": candles_1d}, tol_pct_used=0.003)
    strength_100 = next(c for c in clusters if c["center"] == 100.0)["strength"]
    strength_200 = next(c for c in clusters if c["center"] == 200.0)["strength"]
    assert strength_100 > strength_200


def test_recency_score_decay() -> None:
    candles_1d = _candles_from_closes([200.0] * 300 + [100.0] * 200)
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 489, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 1, "series_len": len(candles_1d)},
        {"price": 100.0, "price_used": 100.0, "index": 488, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 3, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 199, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 2, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 198, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 4, "series_len": len(candles_1d)},
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"1d": candles_1d}, tol_pct_used=0.003)
    strength_recent = next(c for c in clusters if c["center"] == 100.0)["strength"]
    strength_old = next(c for c in clusters if c["center"] == 200.0)["strength"]
    assert strength_recent > strength_old


def test_cluster_strength_prefers_rejection() -> None:
    candles_1d = _candles_from_closes([100.0, 100.0, 120.0, 120.0, 120.0])
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 1, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 1, "series_len": len(candles_1d)},
        {"price": 100.0, "price_used": 100.0, "index": 2, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 2, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 1, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 3, "series_len": len(candles_1d)},
        {"price": 200.0, "price_used": 200.0, "index": 2, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 4, "series_len": len(candles_1d)},
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"1d": candles_1d}, tol_pct_used=0.003)
    strength_100 = next(c for c in clusters if c["center"] == 100.0)["strength"]
    strength_200 = next(c for c in clusters if c["center"] == 200.0)["strength"]
    assert strength_100 > strength_200


def test_rejection_scoring_increases_strength() -> None:
    level = 100.0
    ohlc_rows = [(99.0, 99.5, 98.5, 99.0)]
    for _ in range(5):
        ohlc_rows.append((99.0, 100.2, 98.8, 99.7))
    ohlc_rows.extend([(99.0, 99.5, 98.5, 99.0)] * 3)
    candles = _candles_from_ohlc(ohlc_rows)
    points = [
        {
            "price": level,
            "price_used": level,
            "index": 2,
            "side": "high",
            "tf": "4h",
            "type": "pivot_high",
            "ts": 1,
            "series_len": len(candles),
        },
        {
            "price": level,
            "price_used": level,
            "index": 3,
            "side": "high",
            "tf": "4h",
            "type": "pivot_high",
            "ts": 2,
            "series_len": len(candles),
        }
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"4h": candles}, tol_pct_used=0.005)
    cluster = clusters[0]
    assert cluster["rejections"] > 0
    assert cluster["strength"] > cluster["base_strength"]


def test_role_flip_scoring_increases_strength() -> None:
    level = 100.0
    ohlc_rows = [
        (99.0, 99.4, 98.8, 99.0),
        (99.0, 100.6, 99.0, 100.3),
        (100.3, 101.0, 100.6, 100.7),
        (100.7, 100.9, 100.1, 100.3),
        (100.3, 101.0, 100.2, 100.6),
    ]
    candles = _candles_from_ohlc(ohlc_rows)
    points = [
        {
            "price": level,
            "price_used": level,
            "index": 1,
            "side": "high",
            "tf": "4h",
            "type": "pivot_high",
            "ts": 1,
            "series_len": len(candles),
        },
        {
            "price": level,
            "price_used": level,
            "index": 2,
            "side": "high",
            "tf": "4h",
            "type": "pivot_high",
            "ts": 2,
            "series_len": len(candles),
        }
    ]
    clusters = cluster_points(points, tol_pct=0.001)
    clusters = score_clusters(clusters, {"4h": candles}, tol_pct_used=0.005)
    cluster = clusters[0]
    assert cluster["flips"] > 0
    assert cluster["strength"] > cluster["base_strength"]


def test_role_assignment_support_resistance_mixed() -> None:
    levels = [95.0, 100.5, 105.0]
    detailed = build_levels_detailed(levels, clusters=[], last_close=100.0, tol_pct_used=0.01)
    roles = {item["center"]: item["role"] for item in detailed}
    assert roles[95.0] == "support"
    assert roles[105.0] == "resistance"
    assert roles[100.5] == "mixed"


def test_zone_bounds() -> None:
    detailed = build_levels_detailed([100.0], clusters=[], last_close=100.0, tol_pct_used=0.01)
    assert detailed[0]["zone_low"] == 99.0
    assert detailed[0]["zone_high"] == 101.0


def test_rank_score_biases_toward_recent_or_strong() -> None:
    candles = _candles_from_closes([100.0] * 500)
    clusters = [
        {"center": 100.0, "strength": 0.9, "last_touch_index": 0, "score_tf_used": "4h"},
        {"center": 101.0, "strength": 0.8, "last_touch_index": 498, "score_tf_used": "4h"},
    ]
    assign_rank_scores(clusters, last_close=100.0, series_by_tf={"4h": candles})
    rank_old = clusters[0]["rank_score"]
    rank_recent = clusters[1]["rank_score"]
    assert rank_recent > rank_old


def test_forced_includes_close_cluster() -> None:
    clusters = [
        {"center": 101.0, "rank_score": 0.1, "strength": 0.1, "last_touch_index": 5},
        {"center": 150.0, "rank_score": 0.9, "strength": 0.9, "last_touch_index": 5},
        {"center": 50.0, "rank_score": 0.8, "strength": 0.8, "last_touch_index": 5},
    ]
    selected, forced = select_clusters_with_forced(
        clusters,
        last_close=100.0,
        max_levels=2,
        tol_pct_used=0.01,
        min_below=1,
        min_above=1,
    )
    centers = [cluster["center"] for cluster in selected]
    assert 101.0 in centers
    assert len(forced) == 1


def test_forced_count_zero_when_no_close() -> None:
    clusters = [
        {"center": 120.0, "rank_score": 0.9, "strength": 0.9, "last_touch_index": 5},
        {"center": 140.0, "rank_score": 0.8, "strength": 0.8, "last_touch_index": 5},
    ]
    selected_forced, forced = select_clusters_with_forced(
        clusters,
        last_close=100.0,
        max_levels=2,
        tol_pct_used=0.01,
        min_below=1,
        min_above=1,
    )
    selected_plain = select_clusters(clusters, last_close=100.0, max_levels=2, min_below=1, min_above=1)
    assert len(forced) == 0
    assert [c["center"] for c in selected_forced] == [c["center"] for c in selected_plain]


def test_select_clusters_balanced() -> None:
    clusters = [
        {"center": 90.0, "strength": 0.9, "last_touch_index": 5},
        {"center": 95.0, "strength": 0.8, "last_touch_index": 4},
        {"center": 110.0, "strength": 0.7, "last_touch_index": 6},
        {"center": 120.0, "strength": 0.6, "last_touch_index": 3},
    ]
    selected = select_clusters(clusters, last_close=100.0, max_levels=4, min_below=1, min_above=1)
    centers = sorted([cluster["center"] for cluster in selected])
    assert any(center < 100.0 for center in centers)
    assert any(center > 100.0 for center in centers)


def test_soft_merge_triggers_when_dense() -> None:
    candles = _candles_from_closes([100.0] * 20)
    points = []
    centers = [99.6, 99.95, 100.3, 100.55]
    for idx, center in enumerate(centers):
        for offset in (0, 1):
            points.append(
                {
                    "price": center,
                    "price_used": center,
                    "index": idx + 5 + offset,
                    "side": "high",
                    "tf": "1d",
                    "type": "pivot_high",
                    "ts": idx + offset,
                    "series_len": len(candles),
                }
            )
    clusters = cluster_points(points, tol_pct=0.003)
    clusters = score_clusters(clusters, {"1d": candles}, tol_pct_used=0.003)
    merged, dense_count, triggered, _merge_tol = soft_merge_clusters(
        clusters, last_close=100.0, tol_pct_used=0.003, max_levels=2, series_by_tf={"1d": candles}
    )
    assert dense_count > 2
    assert triggered is True
    assert len(merged) < len(clusters)


def test_soft_merge_not_triggered_when_sparse() -> None:
    candles = _candles_from_closes([100.0] * 20)
    points = []
    centers = [95.0, 105.0, 120.0]
    for idx, center in enumerate(centers):
        for offset in (0, 1):
            points.append(
                {
                    "price": center,
                    "price_used": center,
                    "index": idx + 5 + offset,
                    "side": "high",
                    "tf": "1d",
                    "type": "pivot_high",
                    "ts": idx + offset,
                    "series_len": len(candles),
                }
            )
    clusters = cluster_points(points, tol_pct=0.003)
    clusters = score_clusters(clusters, {"1d": candles}, tol_pct_used=0.003)
    merged, dense_count, triggered, merge_tol = soft_merge_clusters(
        clusters, last_close=100.0, tol_pct_used=0.003, max_levels=2, series_by_tf={"1d": candles}
    )
    assert dense_count <= 2
    assert triggered is False
    assert merge_tol is None
    assert len(merged) == len(clusters)


def test_dbscan_separates_distant_groups() -> None:
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 1, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 1, "series_len": 10},
        {"price": 100.2, "price_used": 100.2, "index": 2, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 2, "series_len": 10},
        {"price": 105.0, "price_used": 105.0, "index": 3, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 3, "series_len": 10},
        {"price": 105.2, "price_used": 105.2, "index": 4, "side": "high", "tf": "1d", "type": "pivot_high", "ts": 4, "series_len": 10},
    ]
    clusters = cluster_points(points, tol_pct=0.003)
    centers = sorted(round(cluster["center"], 1) for cluster in clusters)
    assert len(centers) == 2
    assert centers[0] < centers[1]


def test_prominence_filter_removes_micro_pivots() -> None:
    highs = [100.0, 100.05, 100.0, 100.05, 100.0, 100.05, 100.0, 100.05, 100.0]
    lows = [99.95, 99.9, 99.95, 99.9, 99.95, 99.9, 99.95, 99.9, 99.95]
    candles = _candles_from_series(highs, lows)
    points, _ = _collect_points({"1d": candles}, multiplier=1)
    assert points == []


def test_unlimited_levels_returns_strong_zones(monkeypatch) -> None:
    import app.levels as levels

    ohlc = [(120.0, 160.0, 90.0, 130.0)] * 24
    candles = _candles_from_ohlc(ohlc)
    points = [
        {"price": 100.0, "price_used": 100.0, "index": 5, "side": "low", "tf": "4h", "type": "pivot_low", "ts": 5, "series_len": len(candles)},
        {"price": 100.1, "price_used": 100.1, "index": 6, "side": "low", "tf": "4h", "type": "pivot_low", "ts": 6, "series_len": len(candles)},
        {"price": 150.0, "price_used": 150.0, "index": 7, "side": "high", "tf": "4h", "type": "pivot_high", "ts": 7, "series_len": len(candles)},
        {"price": 150.2, "price_used": 150.2, "index": 8, "side": "high", "tf": "4h", "type": "pivot_high", "ts": 8, "series_len": len(candles)},
    ]

    def fake_collect(_candles_by_tf, _multiplier):
        return points, {"4h": candles}

    monkeypatch.setattr(levels, "_collect_points", fake_collect)
    auto_levels, _selected, _clusters, meta = levels.compute_levels({"4h": candles}, tol_pct=0.005, max_levels=0)
    assert len(auto_levels) == 2
    assert meta["clusters_after_filter"] == 2
