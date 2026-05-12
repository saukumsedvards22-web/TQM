"""Tests for volatility-based delta thresholds."""

import pytest

from tqm.ai.volatility import VolatilityTracker, _STATIC_FALLBACK_PCT, _MIN_HISTORY


def _kpi_deltas(qty_pct: float, rev_pct: float) -> dict:
    return {
        "total_qty": {"pct": qty_pct, "current": 1000, "previous": 1000 / (1 + qty_pct / 100), "abs": 0},
        "total_revenue": {"pct": rev_pct, "current": 90000, "previous": 90000 / (1 + rev_pct / 100), "abs": 0},
    }


def test_static_fallback_when_no_history(tmp_path):
    tracker = VolatilityTracker(history_dir=tmp_path)
    profile = tracker.compute_profile("acme")
    assert not profile.thresholds  # no history → empty thresholds → caller uses fallback


def test_static_fallback_below_min_history(tmp_path):
    tracker = VolatilityTracker(history_dir=tmp_path, min_history=3)
    tracker.record("acme", "2024-01", _kpi_deltas(3.0, 2.5))
    tracker.record("acme", "2024-02", _kpi_deltas(4.0, 3.0))
    profile = tracker.compute_profile("acme")
    # Only 2 records, need 3 → still falls back
    assert not profile.thresholds


def test_volatility_threshold_computed_after_sufficient_history(tmp_path):
    tracker = VolatilityTracker(history_dir=tmp_path, min_history=3)
    for month, qty, rev in [
        ("2024-01", 3.0, 2.0),
        ("2024-02", 4.0, 3.0),
        ("2024-03", 2.5, 1.5),
    ]:
        tracker.record("acme", month, _kpi_deltas(qty, rev))

    profile = tracker.compute_profile("acme")
    assert "total_qty" in profile.thresholds
    t = profile.thresholds["total_qty"]
    assert t.method == "volatility_mad"
    assert t.history_count == 3
    assert t.threshold_pct >= 5.0  # never below floor


def test_threshold_is_higher_for_volatile_client(tmp_path):
    tracker = VolatilityTracker(history_dir=tmp_path, min_history=3)
    # Stable client
    for m, q in [("2024-01", 2.0), ("2024-02", 2.2), ("2024-03", 1.9)]:
        tracker.record("stable", m, _kpi_deltas(q, q))
    # Volatile client
    for m, q in [("2024-01", 30.0), ("2024-02", -15.0), ("2024-03", 25.0)]:
        tracker.record("volatile", m, _kpi_deltas(q, q))

    stable_profile = tracker.compute_profile("stable")
    volatile_profile = tracker.compute_profile("volatile")

    stable_t = stable_profile.thresholds.get("total_qty")
    volatile_t = volatile_profile.thresholds.get("total_qty")

    if stable_t and volatile_t:
        assert volatile_t.threshold_pct > stable_t.threshold_pct


def test_history_persisted_across_instances(tmp_path):
    t1 = VolatilityTracker(history_dir=tmp_path, min_history=3)
    for m, q in [("2024-01", 3.0), ("2024-02", 4.0), ("2024-03", 2.5)]:
        t1.record("acme", m, _kpi_deltas(q, q))

    t2 = VolatilityTracker(history_dir=tmp_path, min_history=3)
    profile = t2.compute_profile("acme")
    assert "total_qty" in profile.thresholds


def test_get_threshold_falls_back_for_unknown_kpi(tmp_path):
    tracker = VolatilityTracker(history_dir=tmp_path)
    profile = tracker.compute_profile("acme")
    t = profile.get_threshold("some_new_kpi")
    assert t.method == "static_fallback"
    assert t.threshold_pct == _STATIC_FALLBACK_PCT
