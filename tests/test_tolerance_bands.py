"""Tests for per-KPI tolerance bands."""

import pytest

from tqm.dax.golden_tests import GoldenSuite, GoldenValue, TOLERANCE_PCT, TOLERANCE_ABS_DEFAULT_PP


def _suite_signed(tests: list[GoldenValue]) -> GoldenSuite:
    from tqm.dax.golden_tests import GoldenSignoff
    return GoldenSuite(
        client_name="Acme",
        dataset_name="Acme Sales",
        reference_period="2024-03",
        tests=tests,
        signoff=GoldenSignoff(
            seeded_by="alice@tqm.lv", seeded_at="2024-03-15T10:00:00Z",
            verified_by="bob@tqm.lv", verified_at="2024-03-15T14:30:00Z",
            client_signoff_email="cfo@acme.lv", client_signoff_at="2024-03-16T09:00:00Z",
        ),
    )


# ── Relative tolerance for currency ──────────────────────────────────

def test_currency_within_relative_tolerance_passes():
    suite = _suite_signed([
        GoldenValue("Total Revenue", "All", "", 100_000.0, tolerance_pct=0.1),
    ])
    # 0.05% off — passes
    results = suite.compare({"Total Revenue": 100_050.0})
    assert results[0].passed


def test_currency_outside_relative_tolerance_fails():
    suite = _suite_signed([
        GoldenValue("Total Revenue", "All", "", 100_000.0, tolerance_pct=0.1),
    ])
    # 1% off — fails
    results = suite.compare({"Total Revenue": 101_000.0})
    assert not results[0].passed


# ── Absolute tolerance for ratios ────────────────────────────────────

def test_margin_pct_with_relative_tolerance_too_strict_to_be_useful():
    """Demonstrate the reviewer's point: 0.1% relative on 12.4 margin is 0.0124pp.
    Even a normal DAX rounding could fail it.
    """
    suite = _suite_signed([
        GoldenValue("Margin %", "All", "", 12.4, tolerance_pct=0.1),
    ])
    # 12.42 — 0.16% relative deviation, beyond 0.1%
    results = suite.compare({"Margin %": 12.42})
    assert not results[0].passed  # would fail with relative — clearly too strict


def test_margin_pct_with_absolute_tolerance_passes():
    """Absolute 0.05pp tolerance: 12.40 → 12.42 is within band."""
    suite = _suite_signed([
        GoldenValue("Margin %", "All", "", 12.4, tolerance_abs=0.05),
    ])
    results = suite.compare({"Margin %": 12.42})
    assert results[0].passed


def test_margin_pct_outside_absolute_tolerance_fails():
    suite = _suite_signed([
        GoldenValue("Margin %", "All", "", 12.4, tolerance_abs=0.05),
    ])
    # 12.4 → 13.0 = 0.6pp absolute, outside 0.05pp
    results = suite.compare({"Margin %": 13.0})
    assert not results[0].passed


# ── Auto-classification at bootstrap ─────────────────────────────────

def test_bootstrap_auto_classifies_ratios_as_absolute():
    suite = GoldenSuite.bootstrap_from_dataframe(
        client_name="Acme", dataset_name="Acme Sales",
        reference_period="2024-03",
        measure_actuals={
            "Total Revenue": 97_650.0,
            "Margin %": 12.4,
            "Total Qty": 1120.0,
            "Conversion Rate": 0.23,
        },
        seeded_by="alice@tqm.lv",
    )
    by_name = {t.measure_name: t for t in suite.tests}
    # Currency / count: relative tolerance
    assert by_name["Total Revenue"].tolerance_abs is None
    assert by_name["Total Qty"].tolerance_abs is None
    # Ratios: absolute tolerance set
    assert by_name["Margin %"].tolerance_abs is not None
    assert by_name["Margin %"].tolerance_abs == TOLERANCE_ABS_DEFAULT_PP
    assert by_name["Conversion Rate"].tolerance_abs is not None


def test_save_and_load_preserves_tolerance_abs(tmp_path):
    suite = _suite_signed([
        GoldenValue("Margin %", "All", "", 12.4, tolerance_abs=0.05),
        GoldenValue("Revenue", "All", "", 100_000.0, tolerance_pct=0.1),
    ])
    path = tmp_path / "g.yaml"
    suite.save(path)
    loaded = GoldenSuite.load(path)
    by_name = {t.measure_name: t for t in loaded.tests}
    assert by_name["Margin %"].tolerance_abs == 0.05
    assert by_name["Revenue"].tolerance_abs is None


# ── tolerance_abs takes precedence when both set ─────────────────────

def test_tolerance_abs_takes_precedence_when_both_set():
    suite = _suite_signed([
        GoldenValue("Margin %", "All", "", 12.4, tolerance_pct=10.0, tolerance_abs=0.05),
    ])
    # 12.4 → 12.5 (0.1pp absolute, ~0.8% relative)
    # Under relative 10% would pass; under absolute 0.05pp it fails
    results = suite.compare({"Margin %": 12.5})
    assert not results[0].passed
