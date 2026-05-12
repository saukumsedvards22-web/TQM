"""Tests for the data ingestion layer."""

import io
from pathlib import Path

import pandas as pd
import pytest

from tqm.ingestion import ExcelIngester, SAPIngester
from tqm.ingestion.excel import _slugify, _coerce_types


# ── slugify ──────────────────────────────────────────────────────────

def test_slugify_basic():
    assert _slugify("Sales Amount") == "sales_amount"

def test_slugify_special_chars():
    # Trailing underscores are stripped, so "revenue_(€)" → "revenue"
    assert _slugify("Revenue (€)") == "revenue"

def test_slugify_trailing_spaces():
    assert _slugify("  Net Profit  ") == "net_profit"

def test_slugify_slashes():
    assert _slugify("Cost/Item") == "cost_item"


# ── coerce_types ─────────────────────────────────────────────────────

def test_coerce_numeric():
    df = pd.DataFrame({"amount": ["100", "200.5", "300", "400"]})
    warns: list[str] = []
    out = _coerce_types(df, warns)
    assert pd.api.types.is_numeric_dtype(out["amount"])

def test_coerce_dates():
    df = pd.DataFrame({"date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]})
    warns: list[str] = []
    out = _coerce_types(df, warns)
    assert pd.api.types.is_datetime64_any_dtype(out["date"])

def test_coerce_mixed_stays_string():
    df = pd.DataFrame({"label": ["foo", "bar", "baz", "qux"]})
    warns: list[str] = []
    out = _coerce_types(df, warns)
    # pandas 2.x may return StringDtype; either way it's not numeric
    assert not pd.api.types.is_numeric_dtype(out["label"])
    assert not pd.api.types.is_datetime64_any_dtype(out["label"])


# ── SAPIngester ───────────────────────────────────────────────────────

PIPE_CONTENT = """\
|Customer     |Amount    |Date      |
|-------------|----------|----------|
|Acme Corp    |12000.50  |2024-03-01|
|Beta Ltd     |8500.00   |2024-03-02|
|Gamma SIA    |4200.75   |2024-03-03|
"""

CSV_CONTENT = """\
Customer;Amount;Date
Acme Corp;12000.50;2024-03-01
Beta Ltd;8500.00;2024-03-02
Gamma SIA;4200.75;2024-03-03
"""


def _write_tmp(tmp_path: Path, content: str, name: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_sap_pipe_ingestion(tmp_path):
    p = _write_tmp(tmp_path, PIPE_CONTENT, "report.txt")
    result = SAPIngester().ingest(p)
    assert len(result.tables) == 1
    df = result.tables[0].df
    assert len(df) == 3
    assert "customer" in df.columns or "customer_____" in df.columns or any("customer" in c for c in df.columns)


def test_sap_csv_ingestion(tmp_path):
    p = _write_tmp(tmp_path, CSV_CONTENT, "report.csv")
    result = SAPIngester().ingest(p)
    assert len(result.tables) == 1
    assert result.tables[0].row_count == 3


def test_sap_missing_file():
    with pytest.raises(FileNotFoundError):
        SAPIngester().ingest(Path("/nonexistent/file.txt"))


# ── ExcelIngester ─────────────────────────────────────────────────────

def test_excel_ingester_csv_fallback(tmp_path):
    """SAP ingester handles CSVs from sample_data correctly."""
    sample = Path(__file__).parent.parent / "sample_data" / "sales_2024_03.csv"
    if not sample.exists():
        pytest.skip("sample_data not present")

    result = SAPIngester().ingest(sample)
    assert result.tables
    df = result.tables[0].df
    assert len(df) > 0
    assert any("qty" in c or "unit_price" in c for c in df.columns)
