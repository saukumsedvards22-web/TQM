"""Tests for CLI utility functions (no Click invocation needed)."""

import pytest

from tqm.cli import _parse_period


# ── _parse_period ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("filepath,expected", [
    # Underscore separators
    ("sales_2024_03.csv",            "2024-03"),
    ("acme_2024_03_final.xlsx",      "2024-03"),
    ("2024_11.csv",                  "2024-11"),
    # Dash separators
    ("acme-2024-03-data.xlsx",       "2024-03"),
    ("report-2023-12.pdf",           "2023-12"),
    # Mixed
    ("export_2025-01_v2.csv",        "2025-01"),
    # Year-month at start of stem
    ("2024_07_sales.csv",            "2024-07"),
])
def test_parse_period_valid_patterns(filepath, expected):
    assert _parse_period(filepath) == expected


@pytest.mark.parametrize("filepath", [
    "sales_data.csv",
    "report.xlsx",
    "2024.csv",           # year only, no month
    "03_2024.csv",        # month-first — not YYYY-MM
    "no_dates_here.txt",
])
def test_parse_period_returns_none_on_no_match(filepath):
    """No YYYY-MM in filename → None, not a garbage string."""
    assert _parse_period(filepath) is None


def test_parse_period_none_prevents_silent_audit_corruption(tmp_path):
    """Verify that None from _parse_period is caught at the call site.

    This is a documentation test: the caller (tqm report) must check for None
    and exit rather than storing the raw stem as a period in the audit log.
    The function contract is: return str | None, never a raw stem.
    """
    result = _parse_period("my_unnamed_export.xlsx")
    assert result is None, (
        "Returning a non-None value for an unrecognised filename would silently "
        "store the stem as the period in audit logs and rolling windows."
    )
