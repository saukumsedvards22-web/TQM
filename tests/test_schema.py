"""Tests for schema detection and dimensional model building."""

from pathlib import Path

import pandas as pd
import pytest

from tqm.ingestion.base import RawTable
from tqm.schema import SchemaDetector
from tqm.schema.model import ColumnRole


def _make_table(name: str, df: pd.DataFrame) -> RawTable:
    return RawTable(name=name, df=df, source_file=Path("test.csv"))


def _sales_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"] * 10),
        "customer": ["Acme", "Beta", "Gamma"] * 10,
        "region": ["Rīga", "Vidzeme", "Kurzeme"] * 10,
        "qty": [100, 200, 150] * 10,
        "unit_price": [45.5, 12.99, 8.75] * 10,
        "discount_pct": [5, 0, 10] * 10,
    })


def test_detect_single_table():
    table = _make_table("sales", _sales_df())
    model = SchemaDetector().detect([table])
    assert model.fact.name == "sales"
    assert len(model.fact.measures) > 0


def test_measures_detected():
    table = _make_table("sales", _sales_df())
    model = SchemaDetector().detect([table])
    measure_names = model.fact.measure_names
    # qty and unit_price should be detected as numeric measures
    assert any("qty" in n or "price" in n for n in measure_names)


def test_date_columns_detected():
    table = _make_table("sales", _sales_df())
    model = SchemaDetector().detect([table])
    assert "date" in model.fact.date_column_names


def test_largest_table_becomes_fact():
    small = _make_table("dim_product", pd.DataFrame({"product_code": ["P1", "P2"], "name": ["A", "B"]}))
    big = _make_table("sales", _sales_df())
    model = SchemaDetector().detect([small, big])
    assert model.fact.name == "sales"


def test_dim_table_registered():
    small = _make_table("dim_product", pd.DataFrame({"product_code": ["P1", "P2"], "name": ["Prod A", "Prod B"]}))
    big = _make_table("sales", _sales_df())
    model = SchemaDetector().detect([small, big])
    assert any(d.name == "dim_product" for d in model.dims)


def test_model_summary_is_string():
    table = _make_table("sales", _sales_df())
    model = SchemaDetector().detect([table])
    summary = model.summary()
    assert isinstance(summary, str)
    assert "sales" in summary
