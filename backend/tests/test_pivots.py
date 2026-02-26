from app.pivots import cluster_levels, find_pivot_highs, find_pivot_lows


def test_pivot_highs_basic() -> None:
    highs = [1, 2, 3, 5, 4, 3, 2, 1, 2, 3, 1]
    result = find_pivot_highs(highs, 2, 2)
    assert result[3] is True
    assert sum(result) == 1


def test_pivot_lows_basic() -> None:
    lows = [5, 4, 3, 1, 2, 3, 4, 3, 2, 3, 4]
    result = find_pivot_lows(lows, 2, 2)
    assert result[3] is True
    assert result[8] is True
    assert sum(result) == 2


def test_pivot_boundaries_false() -> None:
    highs = [3, 2, 3, 2, 3]
    lows = [1, 2, 1, 2, 1]
    high_result = find_pivot_highs(highs, 2, 2)
    low_result = find_pivot_lows(lows, 2, 2)
    assert high_result[0] is False
    assert high_result[-1] is False
    assert low_result[0] is False
    assert low_result[-1] is False


def test_cluster_levels_within_tolerance() -> None:
    prices = [100.0, 100.2, 99.9, 105.0]
    clusters = cluster_levels(prices, 0.003)
    assert len(clusters) == 2
    assert clusters[0]["count"] == 3
    assert clusters[1]["count"] == 1


def test_cluster_levels_separated() -> None:
    prices = [100.0, 101.0, 102.0]
    clusters = cluster_levels(prices, 0.003)
    assert len(clusters) == 3


def test_cluster_levels_sorted_by_center() -> None:
    prices = [200.0, 100.0, 150.0]
    clusters = cluster_levels(prices, 0.0001)
    centers = [cluster["center"] for cluster in clusters]
    assert centers == sorted(centers)
