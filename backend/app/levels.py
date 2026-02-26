from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import math

from .candle_cache import Candle
from .indicators import atr
from .pivots import find_pivot_highs, find_pivot_lows

HTF_TFS = ("1w", "1d", "4h")
HTF_LIMITS = {"1w": 300, "1d": 1000, "4h": 1500}
MIN_BELOW_DEFAULT = 4
MIN_ABOVE_DEFAULT = 4
ATR_TOL_MULTIPLIER = 0.35
MIN_TOL = 0.003
MAX_TOL = 0.007
TOUCH_CAP = 6
REJECTION_WINDOW = 3
ROLE_LOOKBACK_4H = 800
ROLE_RETEST_4H = 30
ROLE_RETEST_1D = 10
DBSCAN_MIN_SAMPLES = 2
DBSCAN_EPS_MULT = 1.0
PROM_WINDOW = 8
PROM_MIN_PCT = 0.003
PROM_ATR_MULT = 0.6
TOUCH_COOLDOWN = 3
SR_MIN_STRENGTH = 0.62
SR_MIN_TOUCH_EVENTS = 2
SR_MIN_REJECTIONS = 0
MIN_SPACING_PCT_MULT = 1.0


def compute_levels(
    candles_by_tf: Dict[str, List[Candle]],
    tol_pct: float,
    max_levels: int,
) -> tuple[List[float], List[dict], List[dict], dict]:
    last_close = _get_last_close(candles_by_tf)
    tol_pct_used, atr_pct, atr5_last, tol_pct_raw = _compute_tol_pct_used(candles_by_tf, tol_pct, last_close)
    eps_pct_used = tol_pct_used * DBSCAN_EPS_MULT
    eps_log_used = math.log(1.0 + eps_pct_used) if eps_pct_used > 0 else 0.0
    min_below = min(MIN_BELOW_DEFAULT, max_levels // 2) if max_levels > 0 else 0
    min_above = min(MIN_ABOVE_DEFAULT, max_levels - min_below) if max_levels > 0 else 0

    auto_levels: List[float] = []
    selected: List[dict] = []
    clusters: List[dict] = []
    below_count = 0
    above_count = 0
    forced_count = 0
    forced_centers: List[float] = []
    cluster_count_before = 0
    cluster_count_after = 0

    dense_count = 0
    merge_triggered = False
    merge_tol_pct = None

    for multiplier in (1, 2):
        points, series_by_tf = _collect_points(candles_by_tf, multiplier)
        clusters = cluster_points(points, tol_pct_used)
        clusters = score_clusters(clusters, series_by_tf, tol_pct_used)
        clusters, dense_count, merge_triggered, merge_tol_pct = soft_merge_clusters(
            clusters,
            last_close,
            tol_pct_used,
            max_levels,
            series_by_tf,
        )
        clusters = assign_rank_scores(clusters, last_close, series_by_tf)
        cluster_count_before = len(clusters)
        if max_levels <= 0:
            selected = _select_strong_clusters(clusters, tol_pct_used)
            auto_levels = sorted([cluster["center"] for cluster in selected])
            below_count = len([level for level in auto_levels if last_close is not None and level < last_close])
            above_count = len([level for level in auto_levels if last_close is not None and level > last_close])
            forced_count = 0
            forced_centers = []
            cluster_count_after = len(selected)
            if not selected and multiplier == 1:
                continue
            break
        selected, forced = select_clusters_with_forced(
            clusters,
            last_close,
            max_levels,
            tol_pct_used,
            min_below=min_below,
            min_above=min_above,
        )
        auto_levels = sorted([cluster["center"] for cluster in selected])

        below_count = len([level for level in auto_levels if last_close is not None and level < last_close])
        above_count = len([level for level in auto_levels if last_close is not None and level > last_close])
        forced_count = len(forced)
        forced_centers = [cluster["center"] for cluster in forced]
        cluster_count_after = len(selected)

        if (
            max_levels > 0
            and last_close is not None
            and (len(auto_levels) < max_levels or below_count < min_below or above_count < min_above)
            and multiplier == 1
        ):
            continue
        break

    meta = {
        "last_close_used": last_close,
        "below_count": below_count,
        "above_count": above_count,
        "tol_pct_used": tol_pct_used,
        "atr_pct": atr_pct,
        "atr5_last_used": atr5_last,
        "tol_pct_raw": tol_pct_raw,
        "dbscan_eps_pct_used": eps_pct_used,
        "dbscan_eps_log": eps_log_used,
        "dbscan_min_samples": DBSCAN_MIN_SAMPLES,
        "sr_min_strength": SR_MIN_STRENGTH,
        "sr_min_touch_events": SR_MIN_TOUCH_EVENTS,
        "sr_min_rejections": SR_MIN_REJECTIONS,
        "min_spacing_pct_used": (tol_pct_used * MIN_SPACING_PCT_MULT) if tol_pct_used else None,
        "clusters_before_filter": cluster_count_before,
        "clusters_after_filter": cluster_count_after,
        "dense_count_near_price": dense_count,
        "merge_triggered": merge_triggered,
        "merge_tol_pct_used": merge_tol_pct,
        "forced_count": forced_count,
        "forced_centers": forced_centers,
    }
    return auto_levels, selected, clusters, meta


def apply_overrides(
    auto_levels: Iterable[float],
    pinned_levels: Iterable[float],
    disabled_levels: Iterable[float],
    tol_pct: float,
) -> dict:
    pinned = sorted(set(float(val) for val in pinned_levels))
    disabled = sorted(set(float(val) for val in disabled_levels))
    filtered_auto: List[float] = []
    for level in auto_levels:
        if _within_any(level, disabled, tol_pct):
            continue
        if _within_any(level, pinned, tol_pct):
            continue
        filtered_auto.append(level)
    final_levels = sorted(filtered_auto + pinned)
    return {
        "auto_levels": list(auto_levels),
        "pinned_levels": pinned,
        "disabled_levels": disabled,
        "final_levels": final_levels,
    }


def balance_levels(
    auto_levels: List[float], last_close: float, target: int, min_below: int = 4, min_above: int = 4
) -> List[float]:
    if target <= 0 or not auto_levels:
        return []
    unique_levels = sorted(set(auto_levels))
    if len(unique_levels) <= target:
        return unique_levels

    below = sorted([level for level in unique_levels if level < last_close], reverse=True)
    above = sorted([level for level in unique_levels if level > last_close])

    required_below = min(min_below, target // 2)
    required_above = min(min_above, target - required_below)

    chosen = below[:required_below] + above[:required_above]

    if len(chosen) < target:
        remaining = [level for level in below[required_below:] if level not in chosen]
        remaining += [level for level in above[required_above:] if level not in chosen]
        chosen.extend(remaining[: target - len(chosen)])

    return sorted(chosen)


def cluster_points(points: List[dict], tol_pct: float) -> List[dict]:
    """DBSCAN-style clustering in log-price space with relative epsilon.

    This avoids rolling-mean chain-linking by using a fixed epsilon in ln(price)
    space and density-based expansion with min_samples.
    """
    if tol_pct <= 0:
        raise ValueError("tol_pct must be > 0")
    if not points:
        return []

    eps_pct = tol_pct * DBSCAN_EPS_MULT
    eps_pct = eps_pct if eps_pct > 0 else tol_pct
    eps_log = math.log(1.0 + eps_pct)

    valid: List[tuple[float, dict]] = []
    noise_points: List[dict] = []
    for point in points:
        price = point.get("price")
        if price is None or price <= 0:
            noise_points.append(point)
        else:
            valid.append((math.log(price), point))

    if not valid:
        clusters = [_cluster_from_members([point]) for point in noise_points]
        clusters.sort(key=lambda item: item["center"])
        return clusters

    valid.sort(key=lambda item: (item[0], item[1].get("ts", 0), item[1].get("index", 0)))
    xs = [item[0] for item in valid]
    n = len(xs)
    left_idx = [0] * n
    right_idx = [0] * n

    left = 0
    for i in range(n):
        while xs[i] - xs[left] > eps_log:
            left += 1
        left_idx[i] = left

    right = 0
    for i in range(n):
        if right < i:
            right = i
        while right + 1 < n and xs[right + 1] - xs[i] <= eps_log:
            right += 1
        right_idx[i] = right

    neighbor_count = [right_idx[i] - left_idx[i] + 1 for i in range(n)]
    labels: List[int | None] = [None] * n
    cluster_id = 0

    for i in range(n):
        if labels[i] is not None:
            continue
        if neighbor_count[i] < DBSCAN_MIN_SAMPLES:
            labels[i] = -1
            continue
        cluster_id += 1
        labels[i] = cluster_id
        stack = [i]
        while stack:
            idx = stack.pop()
            start = left_idx[idx]
            end = right_idx[idx]
            for j in range(start, end + 1):
                if labels[j] is None or labels[j] == -1:
                    labels[j] = cluster_id
                    if neighbor_count[j] >= DBSCAN_MIN_SAMPLES:
                        stack.append(j)

    clusters: List[dict] = []
    members_by_cluster: Dict[int, List[dict]] = {}
    for label, (_, point) in zip(labels, valid):
        if label is None:
            continue
        if label == -1:
            # Keep isolated valid pivots as singleton levels instead of dropping them.
            clusters.append(_cluster_from_members([point]))
            continue
        members_by_cluster.setdefault(label, []).append(point)

    for members in members_by_cluster.values():
        clusters.append(_cluster_from_members(members))

    for point in noise_points:
        clusters.append(_cluster_from_members([point]))

    clusters.sort(key=lambda item: item["center"])
    return clusters


def _cluster_from_members(members: List[dict]) -> dict:
    prices = [member["price"] for member in members]
    times = [member["ts"] for member in members]
    center = sum(prices) / len(prices)
    last_member = max(members, key=lambda item: item["index"])
    return {
        "center": center,
        "members": list(members),
        "min": min(prices),
        "max": max(prices),
        "count": len(prices),
        "last_seen": max(times) if times else 0,
        "last_touch_index": last_member["index"],
        "last_touch_limit": last_member["series_len"],
        "touches": len(prices),
    }


def _within_any(value: float, reference: List[float], tol_pct: float) -> bool:
    for item in reference:
        if item == 0:
            if value == 0:
                return True
        elif abs(value - item) / item <= tol_pct:
            return True
    return False


def _collect_points(candles_by_tf: Dict[str, List[Candle]], multiplier: int) -> Tuple[List[dict], Dict[str, List[Candle]]]:
    points: List[dict] = []
    series_by_tf: Dict[str, List[Candle]] = {}
    for tf in HTF_TFS:
        candles = candles_by_tf.get(tf) or []
        if not candles:
            series_by_tf[tf] = []
            continue
        limit = HTF_LIMITS.get(tf)
        if limit is not None:
            limit = int(limit * multiplier)
            if len(candles) > limit:
                candles = candles[-limit:]
        series_by_tf[tf] = candles
        highs = [candle.high for candle in candles]
        lows = [candle.low for candle in candles]
        closes = [candle.close for candle in candles]
        times = [candle.close_time for candle in candles]
        atr_series = atr(highs, lows, closes, 5)
        pivot_high = find_pivot_highs(highs, 2, 2)
        pivot_low = find_pivot_lows(lows, 2, 2)
        series_len = len(candles)
        for idx, is_pivot in enumerate(pivot_high):
            if is_pivot:
                prominence, threshold = _pivot_prominence(
                    highs,
                    lows,
                    closes,
                    atr_series,
                    idx,
                    True,
                    PROM_WINDOW,
                )
                if prominence is None or threshold is None or prominence < threshold:
                    continue
                points.append(
                    {
                        "price": highs[idx],
                        "price_used": highs[idx],
                        "index": idx,
                        "side": "high",
                        "tf": tf,
                        "type": "pivot_high",
                        "ts": times[idx],
                        "series_len": series_len,
                        "prominence": prominence,
                    }
                )
        for idx, is_pivot in enumerate(pivot_low):
            if is_pivot:
                prominence, threshold = _pivot_prominence(
                    highs,
                    lows,
                    closes,
                    atr_series,
                    idx,
                    False,
                    PROM_WINDOW,
                )
                if prominence is None or threshold is None or prominence < threshold:
                    continue
                points.append(
                    {
                        "price": lows[idx],
                        "price_used": lows[idx],
                        "index": idx,
                        "side": "low",
                        "tf": tf,
                        "type": "pivot_low",
                        "ts": times[idx],
                        "series_len": series_len,
                        "prominence": prominence,
                    }
                )
    return points, series_by_tf


def _pivot_prominence(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    atr_series: List[float | None],
    idx: int,
    is_high: bool,
    window: int,
) -> tuple[float | None, float | None]:
    if idx < 0 or idx >= len(highs):
        return None, None
    start = max(0, idx - window)
    end = min(len(highs), idx + window + 1)
    if is_high:
        high_val = highs[idx]
        if high_val <= 0:
            return None, None
        window_lows = lows[start:end]
        if not window_lows:
            return None, None
        prominence = (high_val - min(window_lows)) / high_val
    else:
        low_val = lows[idx]
        if low_val <= 0:
            return None, None
        window_highs = highs[start:end]
        if not window_highs:
            return None, None
        prominence = (max(window_highs) - low_val) / low_val

    atr_pct = None
    if 0 <= idx < len(atr_series):
        atr_val = atr_series[idx]
        close_val = closes[idx] if idx < len(closes) else None
        if atr_val is not None and close_val and close_val > 0:
            atr_pct = atr_val / close_val
    threshold = PROM_MIN_PCT
    if atr_pct is not None:
        threshold = max(PROM_MIN_PCT, PROM_ATR_MULT * atr_pct)
    return prominence, threshold


def _get_last_close(candles_by_tf: Dict[str, List[Candle]]) -> float | None:
    daily_candles = candles_by_tf.get("1d") or []
    if daily_candles:
        return daily_candles[-1].close
    four_hour = candles_by_tf.get("4h") or []
    if four_hour:
        return four_hour[-1].close
    weekly = candles_by_tf.get("1w") or []
    if weekly:
        return weekly[-1].close
    return None


def score_clusters(
    clusters: List[dict],
    series_by_tf: Dict[str, List[Candle]],
    tol_pct_used: float | None,
) -> List[dict]:
    closes_by_tf = {
        tf: [candle.close for candle in candles] for tf, candles in series_by_tf.items()
    }
    score_tf, score_candles = _select_score_series(series_by_tf)
    band_pct = tol_pct_used if tol_pct_used is not None else MIN_TOL
    break_buf_pct = min(0.002, band_pct * 0.35) if band_pct is not None else 0.0
    if score_tf == "4h":
        lookback = ROLE_LOOKBACK_4H
        retest_window = ROLE_RETEST_4H
    else:
        lookback = ROLE_LOOKBACK_4H
        retest_window = ROLE_RETEST_1D

    for cluster in clusters:
        center = cluster.get("center", 0.0)
        touch_events, avg_rejection_strength, last_touch_idx = _count_touch_events(
            score_candles,
            center,
            band_pct,
            TOUCH_COOLDOWN,
            lookback,
        )
        if last_touch_idx is not None:
            cluster["last_touch_index"] = last_touch_idx
            cluster["last_touch_limit"] = len(score_candles)

        touch_score = 1.0 - math.exp(-touch_events / TOUCH_CAP) if touch_events > 0 else 0.0

        last_touch_index = cluster.get("last_touch_index", 0)
        last_touch_limit = cluster.get("last_touch_limit", 1)
        denom = max(last_touch_limit - 1, 1)
        age = max(0, denom - last_touch_index)
        recency_score = math.exp(-age / 200.0)

        base_strength = 0.55 * touch_score + 0.25 * recency_score + 0.20 * avg_rejection_strength
        rejections, last_rejection, flips, last_flip = _compute_rejections_and_flips(
            score_candles,
            cluster.get("center", 0.0),
            band_pct,
            break_buf_pct,
            lookback,
            retest_window,
        )
        rej_score = 1.0 - math.exp(-rejections / 6.0) if rejections > 0 else 0.0
        flip_score = 1.0 - math.exp(-flips / 2.0) if flips > 0 else 0.0
        strength = _clamp01(base_strength + 0.10 * rej_score + 0.18 * flip_score)
        cluster["recency_score"] = recency_score
        cluster["rejection_score"] = avg_rejection_strength
        cluster["strength"] = strength
        cluster["base_strength"] = base_strength
        cluster["touches"] = touch_events
        cluster["touch_events"] = touch_events
        cluster["avg_rejection_strength"] = avg_rejection_strength
        cluster["rejections"] = rejections
        cluster["last_rejection_index"] = last_rejection
        cluster["flips"] = flips
        cluster["last_flip_index"] = last_flip
        cluster["score_tf_used"] = score_tf

    return clusters


def soft_merge_clusters(
    clusters: List[dict],
    last_close: float | None,
    tol_pct_used: float,
    max_levels: int,
    series_by_tf: Dict[str, List[Candle]],
) -> tuple[List[dict], int, bool, float | None]:
    if not clusters:
        return clusters, 0, False, None
    dense_count = 0
    if last_close is not None and last_close > 0:
        band_pct = tol_pct_used * 2.0
        for cluster in clusters:
            if abs(cluster["center"] - last_close) / last_close <= band_pct:
                dense_count += 1

    if last_close is None or last_close <= 0 or max_levels <= 0 or dense_count <= max_levels:
        return clusters, dense_count, False, None

    merge_tol_pct = min(max(tol_pct_used * 1.25, tol_pct_used + 0.001), 0.009)
    merged: List[dict] = []
    current = clusters[0]
    for nxt in clusters[1:]:
        if current["center"] == 0:
            within = nxt["center"] == 0
        else:
            within = abs(nxt["center"] - current["center"]) / current["center"] <= merge_tol_pct
        if within:
            members = current.get("members", []) + nxt.get("members", [])
            current = _cluster_from_members(members)
        else:
            merged.append(current)
            current = nxt
    merged.append(current)
    merged.sort(key=lambda item: item["center"])
    merged = score_clusters(merged, series_by_tf, tol_pct_used)
    return merged, dense_count, True, merge_tol_pct


def assign_rank_scores(
    clusters: List[dict],
    last_close: float | None,
    series_by_tf: Dict[str, List[Candle]],
) -> List[dict]:
    if not clusters:
        return clusters
    for cluster in clusters:
        strength = cluster.get("strength") or 0.0
        dist_pct = 0.0
        if last_close is not None and last_close > 0:
            dist_pct = abs(cluster.get("center", 0.0) - last_close) / last_close
        distance_score = 1.0 / (1.0 + dist_pct * 20.0)

        last_touch_index = cluster.get("last_touch_index", 0)
        score_tf = cluster.get("score_tf_used")
        if score_tf and series_by_tf.get(score_tf):
            now_index = len(series_by_tf[score_tf]) - 1
        else:
            limit = cluster.get("last_touch_limit")
            now_index = (limit - 1) if isinstance(limit, int) and limit > 0 else last_touch_index
        age = max(0, now_index - last_touch_index)
        recency = 1.0 / (1.0 + age)

        rank_score = 0.60 * strength + 0.25 * recency + 0.15 * distance_score
        cluster["rank_score"] = _clamp01(rank_score)
    return clusters


def select_clusters(
    clusters: List[dict],
    last_close: float | None,
    max_levels: int,
    min_below: int = 4,
    min_above: int = 4,
) -> List[dict]:
    if max_levels <= 0:
        return []
    if last_close is None:
        ordered = sorted(
            clusters,
            key=lambda item: (-item.get("rank_score", item.get("strength", 0.0)), -item.get("last_touch_index", 0), item["center"]),
        )
        return ordered[:max_levels]

    below = [cluster for cluster in clusters if cluster["center"] < last_close]
    above = [cluster for cluster in clusters if cluster["center"] > last_close]

    below_sorted = sorted(
        below,
        key=lambda item: (-item.get("rank_score", item.get("strength", 0.0)), -item.get("last_touch_index", 0), item["center"]),
    )
    above_sorted = sorted(
        above,
        key=lambda item: (-item.get("rank_score", item.get("strength", 0.0)), -item.get("last_touch_index", 0), item["center"]),
    )

    target_below = max_levels // 2
    target_above = max_levels - target_below
    required_below = min(min_below, target_below)
    required_above = min(min_above, target_above)

    selected: List[dict] = []
    selected.extend(below_sorted[:required_below])
    selected.extend(above_sorted[:required_above])

    remaining_below = [cluster for cluster in below_sorted if cluster not in selected]
    remaining_above = [cluster for cluster in above_sorted if cluster not in selected]

    if len([c for c in selected if c in below_sorted]) < target_below:
        needed = target_below - len([c for c in selected if c in below_sorted])
        selected.extend(remaining_below[:needed])
        remaining_below = remaining_below[needed:]

    if len([c for c in selected if c in above_sorted]) < target_above:
        needed = target_above - len([c for c in selected if c in above_sorted])
        selected.extend(remaining_above[:needed])
        remaining_above = remaining_above[needed:]

    if len(selected) < max_levels:
        remaining = remaining_below + remaining_above
        remaining_sorted = sorted(
            remaining,
            key=lambda item: (-item.get("rank_score", item.get("strength", 0.0)), -item.get("last_touch_index", 0), item["center"]),
        )
        selected.extend(remaining_sorted[: max_levels - len(selected)])

    return selected[:max_levels]


def select_clusters_with_forced(
    clusters: List[dict],
    last_close: float | None,
    max_levels: int,
    tol_pct_used: float,
    min_below: int = 4,
    min_above: int = 4,
    forced_limit: int = 2,
) -> tuple[List[dict], List[dict]]:
    if max_levels <= 0:
        return [], []
    forced = _select_forced_clusters(clusters, last_close, tol_pct_used, forced_limit)
    remaining_slots = max(0, max_levels - len(forced))
    if remaining_slots == 0:
        return forced[:max_levels], forced[:max_levels]
    remaining = _exclude_by_tolerance(clusters, forced, tol_pct_used)
    selected = select_clusters(
        remaining,
        last_close,
        remaining_slots,
        min_below=min_below,
        min_above=min_above,
    )
    combined = forced + selected
    return combined[:max_levels], forced


def _select_strong_clusters(
    clusters: List[dict],
    tol_pct_used: float,
) -> List[dict]:
    if not clusters:
        return []
    band_pct = tol_pct_used if tol_pct_used > 0 else MIN_TOL
    min_spacing_pct = band_pct * MIN_SPACING_PCT_MULT if band_pct > 0 else band_pct

    filtered = [
        cluster
        for cluster in clusters
        if cluster.get("strength", 0.0) >= SR_MIN_STRENGTH
        and cluster.get("touch_events", cluster.get("touches", 0)) >= SR_MIN_TOUCH_EVENTS
        and cluster.get("rejections", 0) >= SR_MIN_REJECTIONS
    ]
    ordered = sorted(
        filtered,
        key=lambda item: (
            -item.get("rank_score", item.get("strength", 0.0)),
            -item.get("strength", 0.0),
            -item.get("last_touch_index", 0),
            item.get("center", 0.0),
        ),
    )
    kept: List[dict] = []
    for cluster in ordered:
        center = cluster.get("center", 0.0)
        if min_spacing_pct > 0 and _within_any(center, [item.get("center", 0.0) for item in kept], min_spacing_pct):
            continue
        kept.append(cluster)
    return kept


def _compute_tol_pct_used(
    candles_by_tf: Dict[str, List[Candle]],
    base_tol: float,
    last_close: float | None,
) -> tuple[float, float | None, float | None, float | None]:
    atr_pct = None
    atr_last = None
    if last_close is not None and last_close > 0:
        atr_pct, atr_last = _atr_pct_from_candles(candles_by_tf.get("1d") or [], last_close)
        if atr_pct is None:
            atr_pct, atr_last = _atr_pct_from_candles(candles_by_tf.get("4h") or [], last_close)
    if atr_pct is None:
        tol_raw = base_tol
    else:
        tol_raw = max(base_tol, atr_pct * ATR_TOL_MULTIPLIER)
    tol_used = max(MIN_TOL, min(MAX_TOL, tol_raw))
    return tol_used, atr_pct, atr_last, tol_raw


def _atr_pct_from_candles(candles: List[Candle], last_close: float) -> tuple[float | None, float | None]:
    if not candles or last_close <= 0:
        return None, None
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]
    series = atr(highs, lows, closes, 5)
    last_val = None
    for value in reversed(series):
        if value is not None:
            last_val = value
            break
    if last_val is None:
        return None, None
    return last_val / last_close, last_val


def _select_score_series(series_by_tf: Dict[str, List[Candle]]) -> tuple[str | None, List[Candle]]:
    four_hour = series_by_tf.get("4h") or []
    if four_hour:
        return "4h", four_hour
    daily = series_by_tf.get("1d") or []
    if daily:
        return "1d", daily
    return None, []


def _count_touch_events(
    candles: List[Candle],
    center: float,
    band_pct: float,
    cooldown: int,
    lookback: int,
) -> tuple[int, float, int | None]:
    if center <= 0 or not candles:
        return 0, 0.0, None
    zone_low = center * (1 - band_pct)
    zone_high = center * (1 + band_pct)
    start = max(1, len(candles) - lookback)
    last_touch_idx = None
    touch_events = 0
    strengths: List[float] = []

    for idx in range(start, len(candles)):
        candle = candles[idx]
        if candle.low > zone_high or candle.high < zone_low:
            continue
        if last_touch_idx is not None and idx - last_touch_idx <= cooldown:
            continue
        prev_close = candles[idx - 1].close
        if prev_close < center:
            denom = zone_high - candle.low
            strength = (zone_high - candle.close) / denom if denom > 0 else 0.0
        else:
            denom = candle.high - zone_low
            strength = (candle.close - zone_low) / denom if denom > 0 else 0.0
        strengths.append(_clamp01(strength))
        touch_events += 1
        last_touch_idx = idx

    avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
    return touch_events, avg_strength, last_touch_idx


def _compute_rejections_and_flips(
    candles: List[Candle],
    level: float,
    band_pct: float,
    break_buf_pct: float,
    lookback: int,
    retest_window: int,
) -> tuple[int, int | None, int, int | None]:
    if level <= 0 or len(candles) < 2:
        return 0, None, 0, None

    start = max(1, len(candles) - lookback)
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]

    def is_resistance_rejection(idx: int) -> bool:
        prev_close = closes[idx - 1]
        return (
            prev_close < level
            and highs[idx] >= level * (1 - band_pct)
            and closes[idx] <= level * (1 - break_buf_pct)
        )

    def is_support_rejection(idx: int) -> bool:
        prev_close = closes[idx - 1]
        return (
            prev_close > level
            and lows[idx] <= level * (1 + band_pct)
            and closes[idx] >= level * (1 + break_buf_pct)
        )

    rejections = 0
    last_rejection = None
    for idx in range(start, len(candles)):
        if is_resistance_rejection(idx) or is_support_rejection(idx):
            rejections += 1
            last_rejection = idx

    flips = 0
    last_flip = None
    idx = start
    end = len(candles)
    while idx < end:
        prev_close = closes[idx - 1]
        close_val = closes[idx]
        if prev_close < level and close_val > level * (1 + break_buf_pct):
            found = False
            max_j = min(end - 1, idx + retest_window)
            for j in range(idx + 1, max_j + 1):
                if lows[j] <= level * (1 + band_pct) and closes[j] >= level:
                    hold = closes[j] >= level * (1 + break_buf_pct) or is_support_rejection(j)
                    if hold:
                        flips += 1
                        last_flip = j
                        idx = j + 1
                        found = True
                        break
            if found:
                continue
        if prev_close > level and close_val < level * (1 - break_buf_pct):
            found = False
            max_j = min(end - 1, idx + retest_window)
            for j in range(idx + 1, max_j + 1):
                if highs[j] >= level * (1 - band_pct) and closes[j] <= level:
                    hold = closes[j] <= level * (1 - break_buf_pct) or is_resistance_rejection(j)
                    if hold:
                        flips += 1
                        last_flip = j
                        idx = j + 1
                        found = True
                        break
            if found:
                continue
        idx += 1

    return rejections, last_rejection, flips, last_flip


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _select_forced_clusters(
    clusters: List[dict],
    last_close: float | None,
    tol_pct_used: float,
    forced_limit: int,
) -> List[dict]:
    if last_close is None or last_close <= 0 or tol_pct_used <= 0 or forced_limit <= 0:
        return []
    threshold = tol_pct_used * 3.0
    sorted_clusters = sorted(
        clusters,
        key=lambda item: abs(item.get("center", 0.0) - last_close) / last_close,
    )
    forced: List[dict] = []
    for cluster in sorted_clusters:
        if len(forced) >= forced_limit:
            break
        center = cluster.get("center", 0.0)
        dist_pct = abs(center - last_close) / last_close
        if dist_pct > threshold:
            break
        if _within_any(center, [item.get("center", 0.0) for item in forced], tol_pct_used):
            continue
        forced.append(cluster)
    return forced


def _exclude_by_tolerance(
    clusters: List[dict],
    forced: List[dict],
    tol_pct_used: float,
) -> List[dict]:
    if not forced:
        return list(clusters)
    forced_centers = [cluster.get("center", 0.0) for cluster in forced]
    filtered = []
    for cluster in clusters:
        center = cluster.get("center", 0.0)
        if _within_any(center, forced_centers, tol_pct_used):
            continue
        filtered.append(cluster)
    return filtered


def build_levels_detailed(
    levels: List[float],
    clusters: List[dict],
    last_close: float | None,
    tol_pct_used: float,
) -> List[dict]:
    details: List[dict] = []
    for level in levels:
        match = _find_cluster_for_level(level, clusters, tol_pct_used)
        if last_close is not None and last_close > 0:
            dist_pct = abs(level - last_close) / last_close
            if dist_pct <= tol_pct_used:
                role = "mixed"
            elif level < last_close:
                role = "support"
            else:
                role = "resistance"
        else:
            role = "mixed"
        details.append(
            {
                "center": level,
                "role": role,
                "zone_low": level * (1 - tol_pct_used),
                "zone_high": level * (1 + tol_pct_used),
                "strength": match.get("strength") if match else 0.0,
                "touches": match.get("touches") if match else 0,
                "touch_events": match.get("touch_events") if match else 0,
                "avg_rejection_strength": match.get("avg_rejection_strength") if match else 0.0,
                "rejections": match.get("rejections") if match else 0,
                "flips": match.get("flips") if match else 0,
                "last_touch_index": match.get("last_touch_index") if match else None,
                "last_rejection_index": match.get("last_rejection_index") if match else None,
                "last_flip_index": match.get("last_flip_index") if match else None,
                "score_tf_used": match.get("score_tf_used") if match else None,
            }
        )
    return details


def _find_cluster_for_level(level: float, clusters: List[dict], tol_pct: float) -> dict | None:
    best = None
    best_diff = None
    for cluster in clusters:
        center = cluster.get("center")
        if center is None:
            continue
        if center == 0:
            within = level == 0
        else:
            within = abs(level - center) / center <= tol_pct
        if not within:
            continue
        diff = abs(level - center)
        if best is None or diff < (best_diff or float("inf")):
            best = cluster
            best_diff = diff
    return best
