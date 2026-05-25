"""Tests for monthly snapshot and comparison."""

import pandas as pd
import pytest

from tqm.ai.snapshot import MonthlySnapshot, SnapshotComparison


def _make_snap(period: str, total_qty: float, total_revenue: float) -> MonthlySnapshot:
    return MonthlySnapshot(
        period=period,
        kpis={"total_qty": total_qty, "total_unit_price": total_revenue},
        row_count=100,
    )


def test_kpi_deltas_positive():
    cur = _make_snap("2024-03", 1200, 95000)
    prev = _make_snap("2024-02", 1000, 80000)
    comp = SnapshotComparison(current=cur, previous=prev)
    deltas = comp.kpi_deltas
    assert deltas["total_qty"]["pct"] == pytest.approx(20.0)
    assert deltas["total_unit_price"]["pct"] == pytest.approx(18.75)


def test_kpi_deltas_negative():
    cur = _make_snap("2024-03", 800, 70000)
    prev = _make_snap("2024-02", 1000, 80000)
    comp = SnapshotComparison(current=cur, previous=prev)
    deltas = comp.kpi_deltas
    assert deltas["total_qty"]["pct"] == pytest.approx(-20.0)


def test_top_movers_sorted():
    cur = _make_snap("2024-03", 2000, 95000)  # +100% qty, +18.75% revenue
    prev = _make_snap("2024-02", 1000, 80000)
    comp = SnapshotComparison(current=cur, previous=prev)
    movers = comp.top_movers(n=2)
    # qty has larger % change (100%) than revenue (18.75%)
    assert movers[0][0] == "total_qty"


def test_period_label():
    cur = _make_snap("2024-03", 1000, 80000)
    prev = _make_snap("2024-02", 1000, 80000)
    comp = SnapshotComparison(current=cur, previous=prev)
    assert "2024-03" in comp.period_label
    assert "2024-02" in comp.period_label


def test_to_prompt_context_is_json():
    import json
    cur = _make_snap("2024-03", 1200, 95000)
    prev = _make_snap("2024-02", 1000, 80000)
    comp = SnapshotComparison(current=cur, previous=prev)
    ctx = comp.to_prompt_context()
    data = json.loads(ctx)
    assert "kpi_deltas" in data
    assert "top_movers" in data


def test_snapshot_from_dataframe():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-03-01"] * 5),
        "qty": [100, 200, 150, 300, 250],
        "unit_price": [45.5, 12.99, 8.75, 5.60, 3.20],
        "region": ["Rīga", "Vidzeme", "Kurzeme", "Rīga", "Vidzeme"],
    })
    snap = MonthlySnapshot.from_dataframe(
        df, "date", ["qty", "unit_price"], ["region"], "2024-03"
    )
    assert snap.kpis["total_qty"] == pytest.approx(1000.0)
    assert "region" in snap.dimension_breakdowns


def test_period_days_single_day():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-03-01"] * 5),
        "qty": [10, 20, 30, 40, 50],
    })
    snap = MonthlySnapshot.from_dataframe(df, "date", ["qty"], [], "2024-03")
    assert snap.period_days == 1


def test_period_days_full_month():
    dates = pd.date_range("2024-03-01", "2024-03-31")
    df = pd.DataFrame({"date": dates, "qty": [1.0] * len(dates)})
    snap = MonthlySnapshot.from_dataframe(df, "date", ["qty"], [], "2024-03")
    assert snap.period_days == 31


def test_period_days_zero_when_no_date_col():
    df = pd.DataFrame({"qty": [10, 20, 30]})
    snap = MonthlySnapshot.from_dataframe(df, "missing_date", ["qty"], [], "2024-03")
    assert snap.period_days == 0


def test_period_days_in_to_json():
    import json
    df = pd.DataFrame({
        "date": pd.date_range("2024-03-01", "2024-03-28"),
        "qty": [1.0] * 28,
    })
    snap = MonthlySnapshot.from_dataframe(df, "date", ["qty"], [], "2024-03")
    data = json.loads(snap.to_json())
    assert data["period_days"] == 28


def test_all_null_measure_column_skipped():
    """A 100% null column must not produce NaN KPIs that bypass gate checks."""
    df = pd.DataFrame({
        "date": pd.date_range("2024-03-01", periods=5),
        "revenue": [100.0, 200.0, 150.0, 180.0, 120.0],
        "bad_col": [None, None, None, None, None],  # 100% null
    })
    snap = MonthlySnapshot.from_dataframe(df, "date", ["revenue", "bad_col"], [], "2024-03")
    # bad_col must be absent from kpis — no NaN values
    kpi_keys = list(snap.kpis.keys())
    assert not any("bad_col" in k for k in kpi_keys), (
        f"All-null column produced KPI entries: {[k for k in kpi_keys if 'bad_col' in k]}"
    )
    # Revenue column must still be present
    assert "total_revenue" in snap.kpis
    import math
    assert not any(math.isnan(v) for v in snap.kpis.values()), (
        "NaN found in kpis — would silently bypass all gate comparisons"
    )
