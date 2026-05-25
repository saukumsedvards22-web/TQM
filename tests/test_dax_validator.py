"""Tests for static DAX measure validator."""

from tqm.dax.measures import DAXMeasure, DAXMeasureSet
from tqm.dax.validator import DAXValidator


def _measure(name="Total Revenue", expr="SUM(sales[amount])", table="sales") -> DAXMeasure:
    return DAXMeasure(name=name, expression=expr, table=table)


# ── Valid measures ────────────────────────────────────────────────────

def test_valid_measure_passes():
    m = _measure(expr="SUMX(sales, sales[qty] * sales[unit_price])")
    issues = DAXValidator().validate_measure(m)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors


def test_divide_passes():
    m = _measure(expr="DIVIDE(SUM(sales[profit]), SUM(sales[revenue]), 0)")
    issues = DAXValidator().validate_measure(m)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors


# ── Syntax errors ─────────────────────────────────────────────────────

def test_unbalanced_parens_is_error():
    m = _measure(expr="SUM(sales[amount]")  # missing closing paren
    issues = DAXValidator().validate_measure(m)
    assert any(i.code == "UNBALANCED_PARENS" for i in issues if i.severity == "error")


def test_unbalanced_brackets_is_error():
    m = _measure(expr="SUM(sales[amount)")  # missing closing bracket
    issues = DAXValidator().validate_measure(m)
    assert any(i.code == "UNBALANCED_BRACKETS" for i in issues if i.severity == "error")


def test_blank_expression_is_error():
    m = _measure(expr="BLANK()")
    issues = DAXValidator().validate_measure(m)
    assert any(i.code == "EMPTY_EXPRESSION" for i in issues if i.severity == "error")


# ── Warnings ──────────────────────────────────────────────────────────

def test_bare_division_warns():
    m = _measure(expr="SUM(sales[profit]) / SUM(sales[revenue])")
    issues = DAXValidator().validate_measure(m)
    assert any(i.code == "BARE_DIVISION" for i in issues if i.severity == "warning")


def test_filter_antipattern_warns():
    m = _measure(expr="CALCULATE(SUM(sales[amount]), FILTER(sales, sales[region] = \"Rīga\"))")
    issues = DAXValidator().validate_measure(m)
    assert any(i.code == "CALCULATE_FILTER_ANTIPATTERN" for i in issues if i.severity == "warning")


# ── Unknown table/column ──────────────────────────────────────────────

def test_unknown_table_is_error():
    validator = DAXValidator(known_tables={"sales"})
    m = _measure(expr="SUM(orders[amount])")  # 'orders' not in known tables
    issues = validator.validate_measure(m)
    assert any(i.code == "UNKNOWN_TABLE" for i in issues if i.severity == "error")


def test_unknown_column_is_error():
    validator = DAXValidator(
        known_tables={"sales"},
        known_columns={"sales": {"qty", "unit_price"}},
    )
    m = _measure(expr="SUM(sales[nonexistent_column])")
    issues = validator.validate_measure(m)
    assert any(i.code == "UNKNOWN_COLUMN" for i in issues if i.severity == "error")


# ── Measure set ───────────────────────────────────────────────────────

def test_duplicate_measure_name_is_error():
    ms = DAXMeasureSet(fact_table="sales", measures=[
        _measure("Revenue", "SUM(sales[amount])"),
        _measure("Revenue", "SUM(sales[amount])"),  # duplicate
    ])
    result = DAXValidator().validate_set(ms)
    assert not result.passed
    assert any(i.code == "DUPLICATE_NAME" for i in result.errors)


def test_clean_measure_set_passes():
    ms = DAXMeasureSet(fact_table="sales", measures=[
        _measure("Total Revenue", "SUM(sales[amount])"),
        _measure("Total Qty", "SUM(sales[qty])"),
    ])
    result = DAXValidator().validate_set(ms)
    assert result.passed


def test_bracket_in_string_literal_not_flagged():
    """Brackets inside string literals must not trigger UNBALANCED_BRACKETS."""
    # "Price [EUR]" has [ and ] inside a string — should NOT be a bracket error
    m = _measure("Label", 'SUM(sales[amount]) & " [EUR]"')
    issues = DAXValidator().validate_measure(m)
    assert not any(i.code == "UNBALANCED_BRACKETS" for i in issues), (
        "Bracket inside string literal falsely flagged as UNBALANCED_BRACKETS"
    )


def test_genuinely_unbalanced_bracket_still_caught():
    """Truly unbalanced brackets (not in strings) must still be flagged."""
    m = _measure("Bad", "SUM(sales[amount)")  # ] missing
    issues = DAXValidator().validate_measure(m)
    assert any(i.code == "UNBALANCED_BRACKETS" for i in issues)
