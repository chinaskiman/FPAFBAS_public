from __future__ import annotations

from typing import List


def find_pivot_highs(highs: List[float], left: int = 2, right: int = 2) -> List[bool]:
    size = len(highs)
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    result = [False] * size
    for idx in range(size):
        if idx - left < 0 or idx + right >= size:
            continue
        left_window = highs[idx - left : idx]
        right_window = highs[idx + 1 : idx + right + 1]
        if all(highs[idx] > value for value in left_window) and all(highs[idx] >= value for value in right_window):
            result[idx] = True
    return result


def find_pivot_lows(lows: List[float], left: int = 2, right: int = 2) -> List[bool]:
    size = len(lows)
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    result = [False] * size
    for idx in range(size):
        if idx - left < 0 or idx + right >= size:
            continue
        left_window = lows[idx - left : idx]
        right_window = lows[idx + 1 : idx + right + 1]
        if all(lows[idx] < value for value in left_window) and all(lows[idx] <= value for value in right_window):
            result[idx] = True
    return result


def cluster_levels(prices: List[float], tol_pct: float) -> List[dict]:
    if tol_pct <= 0:
        raise ValueError("tol_pct must be > 0")
    if not prices:
        return []
    sorted_prices = sorted(prices)
    clusters: List[dict] = []

    current_members = [sorted_prices[0]]
    current_center = sorted_prices[0]

    for price in sorted_prices[1:]:
        if current_center == 0:
            within = price == current_center
        else:
            within = abs(price - current_center) / current_center <= tol_pct
        if within:
            current_members.append(price)
            current_center = sum(current_members) / len(current_members)
        else:
            clusters.append(_cluster_from_members(current_members))
            current_members = [price]
            current_center = price

    clusters.append(_cluster_from_members(current_members))
    clusters.sort(key=lambda item: item["center"])
    return clusters


def _cluster_from_members(members: List[float]) -> dict:
    center = sum(members) / len(members)
    return {
        "center": center,
        "members": list(members),
        "min": min(members),
        "max": max(members),
        "count": len(members),
    }
