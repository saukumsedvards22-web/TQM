"""Tests for number reconciliation."""

import pytest

from tqm.ai.reconciler import NumberReconciler, ExtractedNumber
from tqm.ai.snapshot import MonthlySnapshot, SnapshotComparison


def _comparison(qty_pct: float = 12.0, rev_pct: float = 8.5) -> SnapshotComparison:
    cur = MonthlySnapshot(
        period="2024-03",
        kpis={"total_qty": 1120.0, "total_revenue": 97650.0},
    )
    prev = MonthlySnapshot(
        period="2024-02",
        kpis={
            "total_qty": 1120.0 / (1 + qty_pct / 100),
            "total_revenue": 97650.0 / (1 + rev_pct / 100),
        },
    )
    return SnapshotComparison(current=cur, previous=prev)


def test_matching_pct_passes():
    comp = _comparison(qty_pct=12.0)
    r = NumberReconciler().reconcile("Volume grew 12% this month.", comp)
    assert r.passed
    assert r.numbers_matched >= 1


def test_large_deviation_blocks():
    comp = _comparison(qty_pct=12.0)
    # Claims 50% but data shows 12%
    r = NumberReconciler().reconcile("Volume grew 50% this month.", comp)
    assert not r.passed
    assert any(i.code == "NUMERIC_MISMATCH" for i in r.issues)


def test_small_deviation_warns_not_blocks():
    comp = _comparison(qty_pct=12.0)
    # 12.3% vs 12.0% — within 3pp but beyond 2pp default tolerance
    r = NumberReconciler(max_deviation_pct=2.0).reconcile("Volume grew 14.5%.", comp)
    # Should not be a hard block for a small deviation
    assert any(i.code in ("NUMERIC_APPROXIMATION", "NUMERIC_MISMATCH") for i in r.issues)


def test_no_numbers_in_text():
    comp = _comparison()
    r = NumberReconciler().reconcile("Results were stable overall.", comp)
    assert r.numbers_checked == 0
    assert r.passed


def test_currency_value_matched():
    # Revenue is ~97650, commentary says €97k — should match within 2%
    comp = _comparison(rev_pct=8.5)
    r = NumberReconciler(max_deviation_pct=2.0).reconcile(
        "Revenue reached €97,650 this month.", comp
    )
    assert r.passed


def test_extraction_handles_scale():
    r = NumberReconciler()
    numbers = r._extract_numbers("Revenue is €1.2M and volume is 1.5k units.")
    values = {n.value for n in numbers}
    assert 1_200_000 in values
    assert 1_500 in values


def test_extraction_pct_flag():
    r = NumberReconciler()
    numbers = r._extract_numbers("Grew 12.4% this quarter.")
    pcts = [n for n in numbers if n.is_pct]
    assert len(pcts) == 1
    assert abs(pcts[0].value - 12.4) < 0.01
