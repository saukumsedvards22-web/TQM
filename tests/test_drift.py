"""Tests for schema drift detection."""

import pandas as pd
import pytest

from tqm.schema.drift import SchemaDriftDetector


def _make_df(**cols) -> pd.DataFrame:
    return pd.DataFrame(cols)


def test_first_run_is_clean(tmp_path):
    detector = SchemaDriftDetector(schema_dir=tmp_path)
    df = _make_df(revenue=[1000.0, 2000.0], region=["Rīga", "Vidzeme"])
    report = detector.check(df, "acme")
    assert report.is_clean


def test_identical_schema_is_clean(tmp_path):
    detector = SchemaDriftDetector(schema_dir=tmp_path)
    df = _make_df(revenue=[1000.0], region=["Rīga"])
    detector.check(df, "acme")  # first run — saves fingerprint
    report = detector.check(df, "acme")  # second run — should match
    assert report.is_clean


def test_missing_column_blocks(tmp_path):
    detector = SchemaDriftDetector(schema_dir=tmp_path)
    df1 = _make_df(revenue=[1000.0], region=["Rīga"], cost=[500.0])
    df2 = _make_df(revenue=[1000.0], region=["Rīga"])  # cost is gone
    detector.check(df1, "acme")
    report = detector.check(df2, "acme")
    assert report.has_blockers
    assert any(e.code == "COLUMN_MISSING" for e in report.events)


def test_new_column_warns(tmp_path):
    detector = SchemaDriftDetector(schema_dir=tmp_path)
    df1 = _make_df(revenue=[1000.0])
    df2 = _make_df(revenue=[1000.0], new_col=["x"])
    detector.check(df1, "acme")
    report = detector.check(df2, "acme")
    assert any(e.code == "COLUMN_ADDED" for e in report.events)
    assert not report.has_blockers  # new column is only a warning


def test_type_regression_blocks(tmp_path):
    detector = SchemaDriftDetector(schema_dir=tmp_path)
    df1 = _make_df(revenue=[1000.0, 2000.0])
    df2 = _make_df(revenue=["one thousand", "two thousand"])  # text instead of numeric
    detector.check(df1, "acme")
    report = detector.check(df2, "acme")
    assert report.has_blockers
    assert any(e.code == "TYPE_REGRESSION" for e in report.events)


def test_update_overwrites_fingerprint(tmp_path):
    detector = SchemaDriftDetector(schema_dir=tmp_path)
    df1 = _make_df(revenue=[1000.0])
    df2 = _make_df(revenue=[1000.0], new_col=["x"])
    detector.check(df1, "acme")
    detector.update(df2, "acme")  # accept the new schema
    report = detector.check(df2, "acme")
    assert report.is_clean
