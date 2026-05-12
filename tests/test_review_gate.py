"""Tests for the human review gate."""

import pytest

from tqm.ai.analyst import AICommentary
from tqm.ai.review_gate import ReviewGate, ReviewBlockedError
from tqm.ai.snapshot import MonthlySnapshot, SnapshotComparison


def _snap(period: str, qty: float, revenue: float) -> MonthlySnapshot:
    return MonthlySnapshot(period=period, kpis={"total_qty": qty, "total_revenue": revenue})


def _commentary(**kwargs) -> AICommentary:
    defaults = dict(
        headline="Revenue grew 5%",
        executive_summary="Revenue increased 5% driven by higher volumes.",
        key_findings=["Volume up 5%"],
        root_cause_analysis="Higher seasonal demand in Q1.",
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
    gate = ReviewGate(delta_block_pct=40.0, mode="pending_file", pending_dir=tmp_path / "pending")
    comp = _comparison(cur_rev=200000, prev_rev=90000)  # +122% revenue
    result = gate.check(_commentary(), comp, "Acme")
    assert not result.passed
    assert any(f.code == "LARGE_DELTA" for f in result.blockers)


def test_small_delta_passes():
    gate = ReviewGate(delta_block_pct=40.0, mode="pending_file", pending_dir=None)
    comp = _comparison()  # ~5% changes
    result = gate.check(_commentary(), comp, "Acme")
    assert result.passed


# ── Hallucination language detection ─────────────────────────────────

def test_speculative_language_blocks(tmp_path):
    gate = ReviewGate(mode="pending_file", pending_dir=tmp_path / "pending")
    comp = _comparison()
    commentary = _commentary(
        root_cause_analysis="This may have been driven by Baltic supply chain disruption perhaps."
    )
    result = gate.check(commentary, comp, "Acme")
    assert any(f.code == "SPECULATIVE_LANGUAGE" for f in result.blockers)


def test_confident_language_passes():
    gate = ReviewGate(mode="pending_file", pending_dir=None)
    comp = _comparison()
    commentary = _commentary(root_cause_analysis="Customer Acme added 3 new locations in March.")
    result = gate.check(commentary, comp, "Acme")
    assert not any(f.code == "SPECULATIVE_LANGUAGE" for f in result.flags)


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
    gate = ReviewGate(delta_block_pct=10.0, mode="raise")
    comp = _comparison(cur_rev=200000, prev_rev=90000)
    with pytest.raises(ReviewBlockedError, match="LARGE_DELTA"):
        gate.check(_commentary(), comp, "Acme")


# ── Pending file written ──────────────────────────────────────────────

def test_pending_file_created_on_block(tmp_path):
    gate = ReviewGate(delta_block_pct=10.0, mode="pending_file", pending_dir=tmp_path)
    comp = _comparison(cur_rev=200000, prev_rev=90000)
    result = gate.check(_commentary(), comp, "Acme SIA")
    assert not result.passed
    pending_files = list(tmp_path.glob("*.pending.json"))
    assert len(pending_files) == 1
