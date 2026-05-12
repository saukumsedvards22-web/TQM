"""Tests for KeyFinding structural validation — closes FM-09."""

import pytest

from tqm.ai.analyst import AICommentary, KeyFinding, RootCauseAnalysis, RootCauseClaim
from tqm.ai.review_gate import ReviewGate
from tqm.ai.snapshot import MonthlySnapshot, SnapshotComparison


# ── Fixtures ──────────────────────────────────────────────────────────

def _rca():
    return RootCauseAnalysis(
        claims=[RootCauseClaim(claim="ok", evidence_kpi="total_revenue", evidence_value="+5.6%")],
        unsupported_factors=[],
    )


def _commentary(findings: list[KeyFinding]) -> AICommentary:
    return AICommentary(
        headline="Revenue grew 5.6%",
        executive_summary="Revenue increased 5.6%.",
        key_findings=findings,
        root_cause_analysis=_rca(),
        risks=[], opportunities=[], recommended_actions=[],
        outlook="Stable.",
        period_label="2024-03 vs 2024-02",
    )


def _comparison():
    """total_revenue +5.6%, total_cost -8%, total_qty +5%."""
    cur = MonthlySnapshot(period="2024-03", kpis={
        "total_revenue": 95600.0, "total_cost": 46000.0, "total_qty": 1050.0,
    })
    prev = MonthlySnapshot(period="2024-02", kpis={
        "total_revenue": 90531.0, "total_cost": 50000.0, "total_qty": 1000.0,
    })
    return SnapshotComparison(current=cur, previous=prev)


# ── Rendering ─────────────────────────────────────────────────────────

def test_render_up_with_magnitude():
    kf = KeyFinding(kpi_id="total_revenue", direction="up", magnitude_pct=12.4)
    assert "rose 12.4%" in kf.render()
    assert "Total Revenue" in kf.render()


def test_render_down_with_magnitude():
    kf = KeyFinding(kpi_id="total_cost", direction="down", magnitude_pct=8.0)
    assert "fell 8.0%" in kf.render()


def test_render_flat_omits_magnitude():
    kf = KeyFinding(kpi_id="total_qty", direction="flat", magnitude_pct=1.5)
    rendered = kf.render()
    assert "stable" in rendered
    assert "1.5%" not in rendered  # flat doesn't show magnitude


def test_render_with_context_suffix():
    kf = KeyFinding(kpi_id="total_revenue", direction="up", magnitude_pct=5.0, context="driven by Q-end")
    rendered = kf.render()
    assert "5.0%" in rendered
    assert "driven by Q-end" in rendered


# ── Gate: kpi_id must exist ───────────────────────────────────────────

def test_unknown_kpi_blocks():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([
        KeyFinding(kpi_id="nonexistent_kpi", direction="up", magnitude_pct=5.6),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert any(f.code == "UNKNOWN_KPI" for f in result.blockers)


def test_empty_kpi_id_blocks():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([
        KeyFinding(kpi_id="", direction="up", magnitude_pct=5.6, context="legacy prose finding"),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert any(f.code == "MALFORMED_FINDING" for f in result.blockers)


# ── Gate: direction must match ────────────────────────────────────────

def test_direction_mismatch_blocks():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    # total_revenue is +5.6%, but finding claims down
    commentary = _commentary([
        KeyFinding(kpi_id="total_revenue", direction="down", magnitude_pct=5.6),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert any(f.code == "FINDING_DIRECTION_MISMATCH" for f in result.blockers)


def test_correct_direction_passes_direction_check():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([
        KeyFinding(kpi_id="total_revenue", direction="up", magnitude_pct=5.6),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert not any(f.code == "FINDING_DIRECTION_MISMATCH" for f in result.flags)


# ── Gate: magnitude must match within 2pp ─────────────────────────────

def test_magnitude_mismatch_blocks():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    # source is +5.6%, finding claims 25% — way off
    commentary = _commentary([
        KeyFinding(kpi_id="total_revenue", direction="up", magnitude_pct=25.0),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert any(f.code == "FINDING_MAGNITUDE_MISMATCH" for f in result.blockers)


def test_magnitude_within_tolerance_passes():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    # source is +5.6%, finding claims 5.6 — within 2pp
    commentary = _commentary([
        KeyFinding(kpi_id="total_revenue", direction="up", magnitude_pct=5.6),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert not any(f.code == "FINDING_MAGNITUDE_MISMATCH" for f in result.flags)


def test_flat_magnitude_not_checked():
    """For flat direction, magnitude is informational only — no mismatch flag."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    # total_qty is +5% (just above flat threshold of 3%)
    # Use a different KPI that's actually flat-ish — modify comparison or pick lower delta
    cur = MonthlySnapshot(period="2024-03", kpis={"stable_kpi": 101.0})
    prev = MonthlySnapshot(period="2024-02", kpis={"stable_kpi": 100.0})
    comp = SnapshotComparison(current=cur, previous=prev)
    commentary = AICommentary(
        headline="Stable", executive_summary="Stable.",
        key_findings=[KeyFinding(kpi_id="stable_kpi", direction="flat", magnitude_pct=999.0)],
        root_cause_analysis=_rca(),
        risks=[], opportunities=[], recommended_actions=[],
        outlook="Stable.", period_label="2024-03",
    )
    result = gate.check(commentary, comp, "Acme")
    # magnitude on flat is not checked
    assert not any(f.code == "FINDING_MAGNITUDE_MISMATCH" for f in result.flags)


# ── Gate: context cannot leak other KPI names (the FM-09 core case) ──

def test_context_kpi_leak_blocks():
    """The core FM-09 case: kpi_id=total_revenue but context mentions 'cost'."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([
        KeyFinding(
            kpi_id="total_revenue",
            direction="up",
            magnitude_pct=5.6,
            context="cost compression contributed to margin",  # mentions 'cost'
        ),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert any(f.code == "CONTEXT_KPI_LEAK" for f in result.blockers)


def test_context_with_only_this_kpi_tokens_passes():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([
        KeyFinding(
            kpi_id="total_revenue",
            direction="up",
            magnitude_pct=5.6,
            context="revenue uplift from seasonal demand",  # only mentions 'revenue', which IS this KPI
        ),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert not any(f.code == "CONTEXT_KPI_LEAK" for f in result.flags)


def test_context_free_of_kpi_names_passes():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([
        KeyFinding(
            kpi_id="total_revenue",
            direction="up",
            magnitude_pct=5.6,
            context="three new B2B contracts closed in week 2",
        ),
    ])
    result = gate.check(commentary, _comparison(), "Acme")
    assert not any(f.code == "CONTEXT_KPI_LEAK" for f in result.flags)


# ── Empty findings warns ──────────────────────────────────────────────

def test_empty_findings_warns():
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    commentary = _commentary([])
    result = gate.check(commentary, _comparison(), "Acme")
    assert any(f.code == "NO_FINDINGS" for f in result.warnings)


# ── Parser tolerates legacy string format ─────────────────────────────

def test_legacy_string_finding_becomes_malformed_finding():
    """If Claude returns a string instead of dict, it becomes a flagged KeyFinding."""
    from tqm.ai.analyst import AIAnalyst
    analyst = AIAnalyst.__new__(AIAnalyst)  # avoid __init__ (needs API key)
    findings = analyst._parse_key_findings(["Revenue grew 12%"])
    assert len(findings) == 1
    assert findings[0].kpi_id == ""
    assert findings[0].context == "Revenue grew 12%"
