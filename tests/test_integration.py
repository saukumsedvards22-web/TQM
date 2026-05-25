"""Integration test: DataFrame → snapshot → comparison → gate → audit log.

Verifies that the component interfaces are compatible end-to-end. Unit tests
check each component in isolation; this test catches regressions that cross
component boundaries — e.g. a field renamed in MonthlySnapshot that the gate
accesses, or an AuditEntry field added without updating from_dict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tqm.ai.snapshot import MonthlySnapshot, SnapshotComparison
from tqm.ai.review_gate import ReviewGate
from tqm.ai.analyst import AICommentary, KeyFinding, RootCauseAnalysis, RootCauseClaim
from tqm.reporting.audit_log import AuditLog, AuditEntry


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_df(
    n_rows: int = 100,
    revenue_per_row: float = 1000.0,
    date_start: str = "2024-03-01",
) -> pd.DataFrame:
    dates = pd.date_range(date_start, periods=n_rows, freq="D") if n_rows > 1 else [pd.Timestamp(date_start)]
    return pd.DataFrame({
        "date": dates[:n_rows] if n_rows <= len(dates) else dates,
        "revenue": [revenue_per_row] * n_rows,
        "cost": [revenue_per_row * 0.6] * n_rows,
        "qty": [10] * n_rows,
        "region": ["Rīga"] * (n_rows // 2) + ["Vidzeme"] * (n_rows - n_rows // 2),
    })


def _make_commentary(comparison: SnapshotComparison) -> AICommentary:
    """Build a commentary whose findings exactly match the comparison data."""
    deltas = comparison.kpi_deltas
    rev_pct = deltas["total_revenue"]["pct"]
    direction = "up" if rev_pct > 3.0 else ("down" if rev_pct < -3.0 else "flat")
    return AICommentary(
        headline=f"Revenue {'grew' if direction == 'up' else 'fell' if direction == 'down' else 'was flat'} "
                 f"{abs(rev_pct):.1f}%",
        executive_summary=f"Revenue changed {rev_pct:+.1f}%.",
        key_findings=[
            KeyFinding(
                kpi_id="total_revenue",
                direction=direction,
                magnitude_pct=abs(rev_pct),
                context="seasonal pattern",
            ),
        ],
        root_cause_analysis=RootCauseAnalysis(
            claims=[RootCauseClaim(
                claim="Seasonal demand increase.",
                evidence_kpi="total_revenue",
                evidence_value=f"{rev_pct:+.1f}%",
            )],
            unsupported_factors=[],
        ),
        risks=[],
        opportunities=[],
        recommended_actions=[],
        outlook="Stable.",
        period_label=comparison.period_label,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_dataframe_to_snapshot_to_gate_passes(tmp_path):
    """Full path: two DataFrames → snapshots → comparison → gate → ReviewResult."""
    df_cur = _make_df(n_rows=100, revenue_per_row=1050.0)  # +5% vs prev
    df_prev = _make_df(n_rows=100, revenue_per_row=1000.0, date_start="2024-02-01")

    snap_cur = MonthlySnapshot.from_dataframe(df_cur, "date", ["revenue", "cost", "qty"], ["region"], "2024-03")
    snap_prev = MonthlySnapshot.from_dataframe(df_prev, "date", ["revenue", "cost", "qty"], ["region"], "2024-02")

    assert snap_cur.row_count == 100
    assert snap_cur.period_days > 0
    assert snap_cur.kpis["total_revenue"] == pytest.approx(105000.0)

    comparison = SnapshotComparison(current=snap_cur, previous=snap_prev)
    deltas = comparison.kpi_deltas
    assert deltas["total_revenue"]["pct"] == pytest.approx(5.0)

    commentary = _make_commentary(comparison)
    gate = ReviewGate(static_fallback_pct=50.0, mode="pending_file", pending_dir=None)
    result = gate.check(commentary, comparison, "Acme")

    assert result.passed, f"Expected gate to pass. Blockers: {[f.code for f in result.blockers]}"


def test_row_count_drop_blocks_at_gate(tmp_path):
    """Truncated current file (60 rows vs 100 prev) → ROW_COUNT_DROP block."""
    df_cur = _make_df(n_rows=60, revenue_per_row=1000.0)
    df_prev = _make_df(n_rows=100, revenue_per_row=1000.0, date_start="2024-02-01")

    snap_cur = MonthlySnapshot.from_dataframe(df_cur, "date", ["revenue"], [], "2024-03")
    snap_prev = MonthlySnapshot.from_dataframe(df_prev, "date", ["revenue"], [], "2024-02")

    commentary = _make_commentary(SnapshotComparison(current=snap_cur, previous=snap_prev))
    gate = ReviewGate(static_fallback_pct=200.0, mode="raise")

    with pytest.raises(Exception, match="ROW_COUNT_DROP"):
        gate.check(commentary, SnapshotComparison(current=snap_cur, previous=snap_prev), "Acme")


def test_period_days_flows_into_prompt_context():
    """period_days computed from DataFrame dates appears in to_prompt_context()."""
    df_cur = _make_df(n_rows=31)   # 31-day coverage
    df_prev = _make_df(n_rows=28, date_start="2024-02-01")  # 28-day coverage

    snap_cur = MonthlySnapshot.from_dataframe(df_cur, "date", ["revenue"], [], "2024-03")
    snap_prev = MonthlySnapshot.from_dataframe(df_prev, "date", ["revenue"], [], "2024-02")

    assert snap_cur.period_days == 31
    assert snap_prev.period_days == 28

    comparison = SnapshotComparison(current=snap_cur, previous=snap_prev)
    ctx = json.loads(comparison.to_prompt_context(sanitize=False))

    assert "period_days" in ctx
    assert ctx["period_days"]["current_days"] == 31
    assert ctx["period_days"]["previous_days"] == 28
    assert ctx["period_days"]["difference_days"] == 3


def test_audit_log_round_trip(tmp_path):
    """AuditLog.record() → lookup() produces a valid AuditEntry."""
    from tqm.ai.review_gate import ReviewResult, ReviewFlag

    audit = AuditLog(log_dir=tmp_path)
    df = _make_df(n_rows=50)

    gate_result = ReviewResult(passed=True, flags=[
        ReviewFlag(severity="warn", code="ROUND_NUMBER", message="test warn"),
    ])

    entry = audit.record(
        client_name="Acme SIA",
        period="2024-03",
        source_df=df,
        prompt="test prompt",
        raw_response="test response",
        kpi_snapshot={"total_revenue": {"pct": 5.0}},
        gate_result=gate_result,
        delivery="dry_run",
        cost_eur=0.012,
        model="claude-sonnet-4-6",
        date_column_used="date",
        schema_drift_clean=True,
        volatility_thresholds={"total_revenue": 15.0},
    )

    assert entry.gate_passed is True
    assert len(entry.gate_flags) == 1

    loaded = audit.lookup("Acme SIA", "2024-03")
    assert loaded is not None
    assert loaded.report_id == entry.report_id
    assert loaded.cost_eur == pytest.approx(0.012)
    assert loaded.late_correction is False


def test_audit_entry_from_dict_ignores_unknown_fields():
    """AuditEntry.from_dict() must not crash on entries with extra fields from future versions."""
    data = {
        "report_id": "abc123",
        "client_name": "Acme",
        "period": "2024-03",
        "generated_at": "2024-03-01T00:00:00Z",
        "source_data_hash": "hash1",
        "prompt_hash": "hash2",
        "response_hash": "hash3",
        "kpi_snapshot": {},
        "gate_passed": True,
        "gate_flags": [],
        "delivery": "dry_run",
        "cost_eur": 0.01,
        "model": "claude-sonnet-4-6",
        "date_column_used": "date",
        "schema_drift_clean": True,
        "volatility_thresholds": {},
        # Future fields not yet in the dataclass:
        "analyst_signoff": "bob@tqm.lv",
        "git_commit_hash": "deadbeef",
    }
    entry = AuditEntry.from_dict(data)
    assert entry.report_id == "abc123"
    assert entry.late_correction is False   # default applied


def test_audit_entry_from_dict_handles_missing_optional_fields():
    """Old log entries without late_correction / supersedes must load with defaults."""
    data = {
        "report_id": "old123",
        "client_name": "Acme",
        "period": "2023-11",
        "generated_at": "2023-11-01T00:00:00Z",
        "source_data_hash": "h1",
        "prompt_hash": "h2",
        "response_hash": "h3",
        "kpi_snapshot": {},
        "gate_passed": True,
        "gate_flags": [],
        "delivery": "email:ceo@acme.lv",
        "cost_eur": 0.008,
        "model": "claude-sonnet-4-5",
        "date_column_used": "date",
        "schema_drift_clean": True,
        "volatility_thresholds": {},
        # late_correction and supersedes intentionally absent (old entry)
    }
    entry = AuditEntry.from_dict(data)
    assert entry.late_correction is False
    assert entry.supersedes is None


def test_kpi_deltas_cached_property_consistent():
    """kpi_deltas returns the same dict object on repeated access (cached)."""
    snap_cur = MonthlySnapshot(period="2024-03", kpis={"total_revenue": 1000.0}, row_count=100)
    snap_prev = MonthlySnapshot(period="2024-02", kpis={"total_revenue": 900.0}, row_count=100)
    comp = SnapshotComparison(current=snap_cur, previous=snap_prev)

    first = comp.kpi_deltas
    second = comp.kpi_deltas
    assert first is second  # same object — cached, not recomputed
    assert first["total_revenue"]["pct"] == pytest.approx(11.11, rel=0.01)


def test_row_count_mutation_visible_after_kpi_deltas_cached():
    """Gate reads row_count directly from snapshot, not from cached kpi_deltas.

    If _check_row_count() ever started reading from kpi_deltas instead of
    comparison.current.row_count, this test would catch the regression:
    the cache is populated first, then the mutation is applied, and the
    gate must still fire.
    """
    from tqm.ai.review_gate import ReviewGate

    snap_cur = MonthlySnapshot(period="2024-03", kpis={"total_revenue": 1000.0}, row_count=1000, period_days=30)
    snap_prev = MonthlySnapshot(period="2024-02", kpis={"total_revenue": 1000.0}, row_count=1000, period_days=29)
    comp = SnapshotComparison(current=snap_cur, previous=snap_prev)

    # Warm the cache — kpi_deltas is now stored on the instance
    _ = comp.kpi_deltas
    assert comp.kpi_deltas is _  # confirms cache is hot

    # Now mutate row_count directly — simulates what ComparisonMutation does
    comp.current.row_count = 500  # 50% of 1000 → below the 70% DROP threshold

    commentary = _make_commentary(comp)
    gate = ReviewGate(static_fallback_pct=50.0, mode="pending_file", pending_dir=None)
    result = gate.check(commentary, comp, "Acme")

    block_codes = {f.code for f in result.flags if f.severity == "block"}
    assert "ROW_COUNT_DROP" in block_codes, (
        "_check_row_count reads from kpi_deltas (stale cache) instead of "
        "comparison.current.row_count — mutation invisible to gate"
    )
