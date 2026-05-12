"""Tests for DAX golden-value test framework."""

import pytest

from tqm.dax.golden_tests import GoldenSuite, GoldenValue, TOLERANCE_PCT


def _suite() -> GoldenSuite:
    return GoldenSuite(
        client_name="Acme SIA",
        dataset_name="Acme Sales",
        reference_period="2024-03",
        tests=[
            GoldenValue("Total Revenue", "All data", "", 97650.0),
            GoldenValue("Total Qty", "All data", "", 1120.0),
            GoldenValue("Gross Margin %", "All data", "", 38.5),
        ],
    )


def test_exact_match_passes():
    suite = _suite()
    actuals = {"Total Revenue": 97650.0, "Total Qty": 1120.0, "Gross Margin %": 38.5}
    results = suite.compare(actuals)
    assert all(r.passed for r in results)


def test_within_tolerance_passes():
    suite = _suite()
    # 0.05% off — within the 0.1% tolerance
    actuals = {"Total Revenue": 97601.0, "Total Qty": 1120.0, "Gross Margin %": 38.5}
    results = suite.compare(actuals)
    assert all(r.passed for r in results)


def test_outside_tolerance_fails():
    suite = _suite()
    actuals = {"Total Revenue": 90000.0, "Total Qty": 1120.0, "Gross Margin %": 38.5}
    results = suite.compare(actuals)
    revenue_result = next(r for r in results if r.measure_name == "Total Revenue")
    assert not revenue_result.passed
    assert revenue_result.deviation_pct > TOLERANCE_PCT


def test_missing_measure_fails():
    suite = _suite()
    actuals = {"Total Qty": 1120.0}  # Total Revenue missing
    results = suite.compare(actuals)
    revenue_result = next(r for r in results if r.measure_name == "Total Revenue")
    assert not revenue_result.passed
    assert revenue_result.error != ""


def test_bootstrap_creates_tests():
    suite = GoldenSuite.bootstrap_from_dataframe(
        client_name="Acme",
        dataset_name="Acme Sales",
        reference_period="2024-03",
        measure_actuals={"Total Revenue": 97650.0, "Total Qty": 1120.0},
    )
    assert len(suite.tests) == 2
    assert suite.tests[0].expected_value == 97650.0


def test_save_and_load(tmp_path):
    suite = _suite()
    path = tmp_path / "golden.yaml"
    suite.save(path)
    loaded = GoldenSuite.load(path)
    assert loaded.client_name == suite.client_name
    assert len(loaded.tests) == len(suite.tests)
    assert loaded.tests[0].expected_value == suite.tests[0].expected_value


def test_report_string_contains_pass_count():
    suite = _suite()
    actuals = {"Total Revenue": 97650.0, "Total Qty": 1120.0, "Gross Margin %": 38.5}
    report = suite.report(actuals)
    assert "3/3" in report


def test_dax_query_script_generated():
    suite = _suite()
    script = suite.dax_query_script()
    assert "Total Revenue" in script
    assert "EVALUATE" in script
