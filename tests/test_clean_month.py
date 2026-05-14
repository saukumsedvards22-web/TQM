"""Tests for clean-month checker and corrections log."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tqm.reporting.clean_month import (
    ClientCorrection,
    CorrectionsLog,
    CleanMonthChecker,
)


def _make_audit_entry(
    audit_dir: Path,
    client: str,
    period: str,
    generated_at: str,
    *,
    gate_passed: bool = True,
    gate_flags: list[dict] | None = None,
    delivery: str = "email:cfo@acme.lv",
    source_data_hash: str = "abc123",
    response_hash: str | None = None,
    schema_drift_clean: bool = True,
    late_correction: bool = False,
    supersedes: str | None = None,
) -> str:
    """Append an AuditEntry-shaped dict to the audit log JSONL."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    safe = client.lower().replace(" ", "_")
    year = generated_at[:4]
    path = audit_dir / f"{safe}_{year}.jsonl"
    report_id = f"rid_{period}_{response_hash or 'x'}{'_corr' if late_correction else ''}"
    entry = {
        "report_id": report_id,
        "client_name": client,
        "period": period,
        "generated_at": generated_at,
        "source_data_hash": source_data_hash,
        "prompt_hash": "p1",
        "response_hash": response_hash or "r1",
        "kpi_snapshot": {},
        "gate_passed": gate_passed,
        "gate_flags": gate_flags or [],
        "delivery": delivery,
        "cost_eur": 0.01,
        "model": "claude-sonnet-4-6",
        "date_column_used": "date",
        "schema_drift_clean": schema_drift_clean,
        "volatility_thresholds": {},
        "late_correction": late_correction,
        "supersedes": supersedes,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return report_id


# ── CorrectionsLog ────────────────────────────────────────────────────

def test_corrections_log_round_trip(tmp_path):
    log = CorrectionsLog(log_dir=tmp_path)
    c = ClientCorrection(
        report_id="abc", logged_at="2024-05-01T10:00:00Z", logged_by="bob@tqm.lv",
        field="kpi_deltas.total_revenue.current", claimed_value=100.0, actual_value=95.0,
        source_of_truth="internal_sheet.xlsx", severity="material", client_name="Acme",
    )
    log.log(c)
    loaded = log.for_client("Acme")
    assert len(loaded) == 1
    assert loaded[0].report_id == "abc"


def test_corrections_log_empty_for_unknown_client(tmp_path):
    log = CorrectionsLog(log_dir=tmp_path)
    assert log.for_client("Nobody") == []


# ── Clean month criteria ──────────────────────────────────────────────

def test_clean_month_passes_with_one_clean_delivery(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z")

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert result.is_clean


def test_blocker_in_delivered_report_fails_clean(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z", gate_passed=False)

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    assert any("C1" in c for c in result.failed_criteria)


def test_client_correction_fails_clean(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    report_id = _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z")

    corr_log = CorrectionsLog(log_dir=corrections)
    corr_log.log(ClientCorrection(
        report_id=report_id, logged_at="2024-07-22T10:00:00Z", logged_by="alice",
        field="x", claimed_value=1.0, actual_value=2.0,
        source_of_truth="y", severity="material", client_name="Acme",
    ))

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    assert any("C2" in c for c in result.failed_criteria)


def test_no_delivery_fails_clean(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    # No entries at all
    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    assert any("C5" in c for c in result.failed_criteria)


def test_schema_drift_unclean_fails_clean(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z", schema_drift_clean=False)

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    assert any("C3" in c for c in result.failed_criteria)


def test_non_deterministic_rerun_fails_clean(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    # Two entries, same source_data_hash, different response_hash
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z",
                      source_data_hash="same_data", response_hash="r1")
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-02T10:00:00Z",
                      source_data_hash="same_data", response_hash="r2")

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    assert any("C4" in c for c in result.failed_criteria)


def test_fallback_commentary_shipped_fails_clean(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    _make_audit_entry(
        audit, "Acme", "2024-07", "2024-07-01T10:00:00Z",
        gate_flags=[{"code": "FALLBACK_COMMENTARY", "severity": "block", "message": "fallback"}],
        gate_passed=False,
    )
    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    # C1 (blocker delivered) fires; C7 also fires
    assert any("C7" in c or "C1" in c for c in result.failed_criteria)


# ── Rolling window ────────────────────────────────────────────────────

def test_late_correction_fails_c4(tmp_path):
    """A late_correction rerun on a delivered period invalidates C4."""
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z",
                      source_data_hash="original_data", response_hash="r1")
    # Client sends corrected file; pipeline re-runs after original delivery
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-15T10:00:00Z",
                      source_data_hash="corrected_data", response_hash="r2",
                      late_correction=True, supersedes="rid_2024-07_r1")

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    assert not result.is_clean
    assert any("C4" in c and "late_correction" in c for c in result.failed_criteria)


def test_late_correction_excluded_from_nondeterminism_check(tmp_path):
    """A correction with different source data must NOT trigger C4 non-determinism."""
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-01T10:00:00Z",
                      source_data_hash="original", response_hash="r1")
    # Correction has different source hash — would look non-deterministic if not excluded
    _make_audit_entry(audit, "Acme", "2024-07", "2024-07-15T10:00:00Z",
                      source_data_hash="corrected", response_hash="r2",
                      late_correction=True)

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    result = checker.check_month("Acme", "2024-07")
    # C4 fires because late_correction is present — but the reason is "late_correction",
    # not "multiple response_hashes for same source hash"
    c4_reasons = [c for c in result.failed_criteria if "C4" in c]
    assert c4_reasons
    assert not any("multiple response_hashes" in c for c in c4_reasons)


def test_rolling_window_six_clean_months_eligible(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    # Generate 6 months of clean entries leading up to but excluding current month
    import datetime as dt
    anchor = dt.date(2024, 11, 15)
    y, m = anchor.year, anchor.month
    for _ in range(6):
        m -= 1
        if m == 0:
            m = 12; y -= 1
        period = f"{y:04d}-{m:02d}"
        _make_audit_entry(audit, "Acme", period, f"{period}-15T10:00:00Z",
                          response_hash=f"r{period}")

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    eligible, results = checker.rolling_window("Acme", anchor_date=anchor)
    assert eligible
    assert all(r.is_clean for r in results)


def test_rolling_window_one_dirty_month_not_eligible(tmp_path):
    audit = tmp_path / "audit"
    corrections = tmp_path / "corrections"
    import datetime as dt
    anchor = dt.date(2024, 11, 15)
    y, m = anchor.year, anchor.month
    for i in range(6):
        m -= 1
        if m == 0:
            m = 12; y -= 1
        period = f"{y:04d}-{m:02d}"
        _make_audit_entry(audit, "Acme", period, f"{period}-15T10:00:00Z",
                          gate_passed=(i != 2),  # one month has a delivered blocker
                          response_hash=f"r{period}")

    checker = CleanMonthChecker(audit_log_dir=audit, corrections_log_dir=corrections)
    eligible, results = checker.rolling_window("Acme", anchor_date=anchor)
    assert not eligible
    assert sum(1 for r in results if not r.is_clean) == 1
