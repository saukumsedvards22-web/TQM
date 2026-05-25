"""Tests for date column validation."""

import pandas as pd
import pytest

from tqm.schema.date_validator import DateColumnValidator


def test_valid_date_column_passes():
    df = pd.DataFrame({
        "date": pd.date_range("2024-03-01", periods=20, freq="D"),
        "revenue": range(20),
    })
    result = DateColumnValidator(expected_period="2024-03").validate(df, "date")
    assert result.passed


def test_missing_column_blocks():
    df = pd.DataFrame({"revenue": [1, 2, 3]})
    result = DateColumnValidator().validate(df, "date")
    assert not result.passed
    assert any(i.code == "COLUMN_NOT_FOUND" for i in result.issues)


def test_high_null_rate_blocks():
    dates = [pd.Timestamp("2024-03-01")] * 5 + [None] * 95  # 95% null
    df = pd.DataFrame({"date": dates, "revenue": range(100)})
    result = DateColumnValidator(max_null_rate=0.05).validate(df, "date")
    assert any(i.code == "HIGH_NULL_RATE" for i in result.issues)
    assert not result.passed


def test_period_mismatch_blocks():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),  # January, not March
        "revenue": range(10),
    })
    result = DateColumnValidator(expected_period="2024-03").validate(df, "date")
    assert any(i.code == "PERIOD_MISMATCH" for i in result.issues)
    assert not result.passed


def test_future_dates_warn():
    import datetime
    future = pd.Timestamp(datetime.date.today()) + pd.Timedelta(days=30)
    df = pd.DataFrame({
        "date": pd.date_range("2024-03-01", periods=9, freq="D").tolist() + [future],
        "revenue": range(10),
    })
    result = DateColumnValidator(max_future_days=3).validate(df, "date")
    assert any(i.code == "FUTURE_DATES" for i in result.issues)


def test_pick_best_column_returns_passing_one():
    df = pd.DataFrame({
        "bad_date": ["not", "a", "date", "column"] * 5,
        "good_date": pd.date_range("2024-03-01", periods=20, freq="D"),
        "revenue": range(20),
    })
    col, result = DateColumnValidator().pick_best_date_column(df, ["bad_date", "good_date"])
    assert col == "good_date"
    assert result is not None and result.passed


def test_pick_best_column_no_candidates():
    df = pd.DataFrame({"revenue": [1, 2, 3]})
    col, result = DateColumnValidator().pick_best_date_column(df, [])
    assert col is None
    assert result is None


# ── expected_period validation ─────────────────────────────────────────────────

import pytest

@pytest.mark.parametrize("bad_period", [
    "2024",          # year only
    "2024-13",       # month out of range
    "03-2024",       # month-first
    "2024/03",       # wrong separator
    "not-a-period",  # garbage
])
def test_malformed_expected_period_raises(bad_period):
    """Malformed expected_period must raise ValueError, not crash mid-validation."""
    df = pd.DataFrame({
        "date": pd.date_range("2024-03-01", periods=10, freq="D"),
        "revenue": range(10),
    })
    with pytest.raises(ValueError, match="expected_period"):
        DateColumnValidator(expected_period=bad_period).validate(df, "date")
