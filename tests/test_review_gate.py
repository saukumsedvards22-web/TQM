"""Tests for the human review gate."""

import pytest

from tqm.ai.analyst import AICommentary, KeyFinding, RootCauseAnalysis, RootCauseClaim
from tqm.ai.review_gate import ReviewGate, ReviewBlockedError
from tqm.ai.snapshot import MonthlySnapshot, SnapshotComparison


def _snap(period: str, qty: float, revenue: float) -> MonthlySnapshot:
    return MonthlySnapshot(period=period, kpis={"total_qty": qty, "total_revenue": revenue})


def _rca(claim: str = "Seasonal demand drove volume.", kpi: str = "total_qty", value: str = "+5.0%") -> RootCauseAnalysis:
    return RootCauseAnalysis(
        claims=[RootCauseClaim(claim=claim, evidence_kpi=kpi, evidence_value=value)],
        unsupported_factors=[],
    )


def _kf(kpi_id: str = "total_revenue", direction: str = "up", magnitude_pct: float = 5.6, context: str = "") -> KeyFinding:
    return KeyFinding(kpi_id=kpi_id, direction=direction, magnitude_pct=magnitude_pct, context=context)


def _commentary(**kwargs) -> AICommentary:
    defaults = dict(
        headline="Revenue grew 5.6%",
        executive_summary="Revenue increased 5.6% driven by higher volumes.",
        key_findings=[_kf()],
        root_cause_analysis=_rca(),
        risks=[],
        opportunities=[],
        recommended_actions=[],
        outlook="Stable outlook.",
        period_label="2024-03 vs 2024-02",
    )
    defaults.update(kwargs)
    return AICommentary(**defaults)


def _comparison(cur_qty=1050, cur_rev=95000, prev_qty=1000, prev_rev=90000):
    cur = _snap("2024-03", cur_qty, cur_rev)
    prev = _snap("2024-02", prev_qty, prev_rev)
    return SnapshotComparison(current=cur, previous=prev)


# ── Large delta blocking ──────────────────────────────────────────────

def test_large_delta_blocks(tmp_path):
    gate = ReviewGate(static_fallback_pct=40.0, mode="pending_file", pending_dir=tmp_path / "pending")
    comp = _comparison(cur_rev=200000, prev_rev=90000)  # +122% revenue
    result = gate.check(_commentary(), comp, "Acme")
    assert not result.passed
    assert any(f.code == "ANOMALOUS_DELTA" for f in result.blockers)


def test_small_delta_passes():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    comp = _comparison()  # ~5% changes, high threshold to avoid triggering
    result = gate.check(_commentary(), comp, "Acme")
    # May still fail on reconciliation for numbers in commentary — just check no delta block
    assert not any(f.code == "ANOMALOUS_DELTA" for f in result.blockers)


# ── Citation checks ──────────────────────────────────────────────────

def test_no_citations_blocks(tmp_path):
    gate = ReviewGate(mode="pending_file", pending_dir=tmp_path / "pending")
    comp = _comparison()
    # RCA with zero cited claims
    no_cite_rca = RootCauseAnalysis(claims=[], unsupported_factors=["seasonal demand"])
    commentary = _commentary(root_cause_analysis=no_cite_rca)
    result = gate.check(commentary, comp, "Acme")
    assert any(f.code == "NO_CITATIONS" for f in result.blockers)


def test_with_citations_passes_citation_check():
    gate = ReviewGate(mode="pending_file", pending_dir=None)
    comp = _comparison()
    result = gate.check(_commentary(), comp, "Acme")  # _commentary() includes _rca() with 1 claim
    assert not any(f.code == "NO_CITATIONS" for f in result.blockers)


# ── Direction conflict detection ──────────────────────────────────────

def test_direction_conflict_revenue_said_grew_but_fell(tmp_path):
    gate = ReviewGate(mode="pending_file", pending_dir=tmp_path / "pending")
    # Revenue fell 10%
    cur = _snap("2024-03", 1000, 81000)
    prev = _snap("2024-02", 1000, 90000)
    comp = SnapshotComparison(current=cur, previous=prev)
    # Commentary says revenue grew
    commentary = _commentary(
        headline="Revenue grew strongly this month",
        executive_summary="Revenue increased significantly.",
    )
    result = gate.check(commentary, comp, "Acme")
    assert any(f.code == "DIRECTION_CONFLICT" for f in result.blockers)


def test_direction_conflict_not_triggered_when_correct():
    gate = ReviewGate(mode="pending_file", pending_dir=None)
    comp = _comparison(cur_rev=95000, prev_rev=90000)  # revenue up
    commentary = _commentary(headline="Revenue grew 5%", executive_summary="Revenue increased.")
    result = gate.check(commentary, comp, "Acme")
    assert not any(f.code == "DIRECTION_CONFLICT" for f in result.flags)


# ── Raise mode ────────────────────────────────────────────────────────

def test_raise_mode_raises_on_block():
    gate = ReviewGate(static_fallback_pct=10.0, mode="raise")
    comp = _comparison(cur_rev=200000, prev_rev=90000)
    with pytest.raises(ReviewBlockedError, match="ANOMALOUS_DELTA"):
        gate.check(_commentary(), comp, "Acme")


# ── Pending file written ──────────────────────────────────────────────

def test_pending_file_created_on_block(tmp_path):
    gate = ReviewGate(static_fallback_pct=10.0, mode="pending_file", pending_dir=tmp_path)
    comp = _comparison(cur_rev=200000, prev_rev=90000)
    result = gate.check(_commentary(), comp, "Acme SIA")
    assert not result.passed
    pending_files = list(tmp_path.glob("*.pending.json"))
    assert len(pending_files) == 1
