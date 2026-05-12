"""Mutation testing for the review gate.

Standard pytest tests verify the gate flags known failures. This module
inverts the question: given a known-good commentary, can we systematically
mutate it into every documented failure mode and confirm the gate catches
each one? If not, the gate has a hole.

Run via:
    pytest tests/test_gate_mutations.py
    tqm mutate-gate                          # CLI for ad-hoc verification

Each mutation is (name, mutate_fn, expected_block_code). A mutation that
fails to produce the expected block code = a gate hole that must be fixed
before the next release.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Callable

from .analyst import AICommentary, KeyFinding, RootCauseAnalysis, RootCauseClaim
from .review_gate import ReviewGate, ReviewResult
from .snapshot import MonthlySnapshot, SnapshotComparison

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Baseline known-good fixture
# ------------------------------------------------------------------

def baseline_comparison() -> SnapshotComparison:
    """A clean SnapshotComparison: revenue +5.6%, cost -8%, qty +5%."""
    cur = MonthlySnapshot(period="2024-03", kpis={
        "total_revenue": 95600.0,
        "total_cost": 46000.0,
        "total_qty": 1050.0,
    })
    prev = MonthlySnapshot(period="2024-02", kpis={
        "total_revenue": 90531.0,
        "total_cost": 50000.0,
        "total_qty": 1000.0,
    })
    return SnapshotComparison(current=cur, previous=prev)


def baseline_commentary() -> AICommentary:
    """A clean, gate-passing commentary for the baseline_comparison."""
    return AICommentary(
        headline="Revenue rose 5.6% on flat volume; margin improved as costs fell 8%.",
        executive_summary=(
            "Revenue increased 5.6% while cost base fell 8%. Quantity was broadly stable."
        ),
        key_findings=[
            KeyFinding(kpi_id="total_revenue", direction="up", magnitude_pct=5.6,
                       context="three new B2B contracts closed in week 2"),
            KeyFinding(kpi_id="total_cost", direction="down", magnitude_pct=8.0,
                       context="renegotiated freight contract"),
            KeyFinding(kpi_id="total_qty", direction="up", magnitude_pct=5.0,
                       context="seasonal pattern matched plan"),
        ],
        root_cause_analysis=RootCauseAnalysis(
            claims=[
                RootCauseClaim(
                    claim="New B2B contracts drove revenue growth.",
                    evidence_kpi="total_revenue",
                    evidence_value="+5.6%",
                ),
            ],
            unsupported_factors=[],
        ),
        risks=[],
        opportunities=[],
        recommended_actions=[],
        outlook="Stable.",
        period_label="2024-03 vs 2024-02",
    )


# ------------------------------------------------------------------
# Mutations
# ------------------------------------------------------------------

@dataclass
class Mutation:
    name: str
    apply: Callable[[AICommentary], AICommentary]
    expected_block_code: str
    description: str = ""


def _clone(c: AICommentary) -> AICommentary:
    return copy.deepcopy(c)


def _mutate_finding_direction(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.key_findings[0].direction = "down"  # revenue actually up
    return out


def _mutate_finding_magnitude(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.key_findings[0].magnitude_pct = 50.0  # claim 50% growth when actual ~5.6%
    return out


def _mutate_finding_kpi_id(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.key_findings[0].kpi_id = "nonexistent_kpi"
    return out


def _mutate_empty_kpi_id(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.key_findings[0].kpi_id = ""
    return out


def _mutate_context_kpi_leak_semantic(c: AICommentary) -> AICommentary:
    """The FM-09 canonical case: revenue finding mentions 'cogs' in context."""
    out = _clone(c)
    out.key_findings[0].context = "cogs compression supported the result"
    return out


def _mutate_context_kpi_leak_synonym(c: AICommentary) -> AICommentary:
    """Synonym-table case: cost finding mentions 'sales' (revenue synonym)."""
    out = _clone(c)
    out.key_findings[1].context = "matched the uplift in sales last quarter"
    return out


def _mutate_remove_citations(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.root_cause_analysis = RootCauseAnalysis(
        claims=[],
        unsupported_factors=["Customer purchased more"],
    )
    return out


def _mutate_direction_conflict_in_summary(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.headline = "Revenue fell sharply this month"
    out.executive_summary = "Revenue declined significantly across all segments."
    return out


def _mutate_inject_speculative_in_summary(c: AICommentary) -> AICommentary:
    """Reconciliation should flag the fabricated number in the summary."""
    out = _clone(c)
    out.executive_summary = "Revenue grew 35% driven by macroeconomic tailwinds."
    return out


def _mutate_fallback_marker(c: AICommentary) -> AICommentary:
    out = _clone(c)
    out.headline = "[AI UNAVAILABLE — HUMAN REVIEW REQUIRED]"
    return out


# ------------------------------------------------------------------
# Registry — the canonical set of mutations we expect the gate to catch
# ------------------------------------------------------------------

MUTATIONS: list[Mutation] = [
    Mutation("flip_direction", _mutate_finding_direction, "FINDING_DIRECTION_MISMATCH",
             "Finding says down, source pct is positive"),
    Mutation("inflate_magnitude", _mutate_finding_magnitude, "FINDING_MAGNITUDE_MISMATCH",
             "Finding claims 50%, source is +5.6%"),
    Mutation("unknown_kpi_id", _mutate_finding_kpi_id, "UNKNOWN_KPI",
             "Finding kpi_id not in source data"),
    Mutation("empty_kpi_id", _mutate_empty_kpi_id, "MALFORMED_FINDING",
             "Finding kpi_id is empty string (legacy prose)"),
    Mutation("context_leak_simple", _mutate_context_kpi_leak_semantic, "CONTEXT_KPI_LEAK",
             "Finding context mentions another KPI token"),
    Mutation("context_leak_synonym", _mutate_context_kpi_leak_synonym, "CONTEXT_KPI_LEAK",
             "Finding context mentions synonym of another KPI"),
    Mutation("remove_citations", _mutate_remove_citations, "NO_CITATIONS",
             "All causal claims pushed to unsupported_factors"),
    Mutation("direction_conflict_summary", _mutate_direction_conflict_in_summary, "DIRECTION_CONFLICT",
             "Summary says fell when revenue rose"),
    Mutation("inflated_number_in_summary", _mutate_inject_speculative_in_summary, "NUMERIC_MISMATCH",
             "Summary states 35% when source is ~5.6%"),
    Mutation("fallback_commentary", _mutate_fallback_marker, "FALLBACK_COMMENTARY",
             "Headline indicates AI fallback"),
]


@dataclass
class MutationResult:
    mutation: Mutation
    caught: bool
    actual_block_codes: list[str]

    @property
    def summary(self) -> str:
        icon = "✅" if self.caught else "❌"
        return (
            f"  {icon} {self.mutation.name:<32} "
            f"expected={self.mutation.expected_block_code:<28} "
            f"actual={','.join(self.actual_block_codes) or '(nothing — GATE HOLE)'}"
        )


@dataclass
class MutationReport:
    results: list[MutationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.caught for r in self.results)

    @property
    def holes(self) -> list[MutationResult]:
        return [r for r in self.results if not r.caught]

    def text(self) -> str:
        lines = [
            "Gate Mutation Test Report",
            "=" * 60,
            f"{len(self.results) - len(self.holes)}/{len(self.results)} mutations caught",
            "",
        ]
        lines += [r.summary for r in self.results]
        if self.holes:
            lines += [
                "",
                f"❌ {len(self.holes)} GATE HOLE(S) — these mutations were NOT caught:",
                *[f"  - {h.mutation.name}: {h.mutation.description}" for h in self.holes],
                "",
                "The gate must be strengthened before the next release.",
            ]
        return "\n".join(lines)


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

def run_mutations(
    gate: ReviewGate | None = None,
    mutations: list[Mutation] | None = None,
) -> MutationReport:
    """Apply each mutation to the baseline commentary and verify the gate catches it.

    Returns a MutationReport listing which mutations were caught and which slipped past.
    """
    gate = gate or ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    muts = mutations or MUTATIONS
    comparison = baseline_comparison()

    results: list[MutationResult] = []
    for mutation in muts:
        mutated = mutation.apply(baseline_commentary())
        gate_result: ReviewResult = gate.check(mutated, comparison, "Mutation Test Client")
        block_codes = [f.code for f in gate_result.blockers]
        caught = mutation.expected_block_code in block_codes
        results.append(MutationResult(mutation=mutation, caught=caught, actual_block_codes=block_codes))

    return MutationReport(results=results)
