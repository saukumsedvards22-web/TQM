"""Tests for date column ambiguity detection."""

import pandas as pd
import pytest

from tqm.schema.date_validator import DateColumnValidator, DateAmbiguityError


def _df_with_dates(*col_names: str) -> pd.DataFrame:
    """Create a DataFrame with multiple well-formed date columns."""
    data = {col: pd.date_range("2024-03-01", periods=20, freq="D") for col in col_names}
    data["revenue"] = range(20)
    return pd.DataFrame(data)


def test_single_passing_candidate_returns_it():
    df = _df_with_dates("order_date")
    col, result = DateColumnValidator().pick_best_date_column(df, ["order_date"])
    assert col == "order_date"
    assert result is not None and result.passed


def test_multiple_passing_candidates_raises():
    df = _df_with_dates("order_date", "ship_date", "posted_date")
    with pytest.raises(DateAmbiguityError, match="Multiple date columns"):
        DateColumnValidator().pick_best_date_column(df, ["order_date", "ship_date", "posted_date"])


def test_explicit_config_overrides_ambiguity():
    df = _df_with_dates("order_date", "ship_date")
    col, result = DateColumnValidator().pick_best_date_column(
        df, ["order_date", "ship_date"], explicit_config="ship_date"
    )
    assert col == "ship_date"


def test_explicit_config_missing_column_raises():
    df = _df_with_dates("order_date")
    with pytest.raises(ValueError, match="not found in data"):
        DateColumnValidator().pick_best_date_column(
            df, ["order_date"], explicit_config="nonexistent_date"
        )


def test_no_candidates_returns_none():
    df = pd.DataFrame({"revenue": [1, 2, 3]})
    col, result = DateColumnValidator().pick_best_date_column(df, [])
    assert col is None
    assert result is None


def test_zero_passing_returns_least_broken(tmp_path):
    """When nothing passes, return the column with fewest blockers (not raise)."""
    df = pd.DataFrame({
        "bad1": ["not", "a", "date"] * 7,
        "bad2": ["also", "not", "dates"] * 7,
        "revenue": range(21),
    })
    col, result = DateColumnValidator().pick_best_date_column(df, ["bad1", "bad2"])
    assert col is not None  # returns something
    assert result is not None
    # The result should not have passed
    assert not result.passed
