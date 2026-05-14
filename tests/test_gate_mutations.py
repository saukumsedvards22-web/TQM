"""Mutation tests: verify the gate catches every documented failure mode.

Each mutation in MUTATIONS represents one way the LLM (or upstream code)
could produce wrong output. The gate must catch each. If a mutation slips
past, it's a gate hole that must be fixed before release.

COMPARISON_MUTATIONS test data-integrity failure modes (FM-12, FM-13): truncated
source files and period-length mismatches. These mutate the SnapshotComparison,
not the commentary, so they need separate parametrisation.
"""

import pytest

from tqm.ai.mutations import (
    MUTATIONS, COMPARISON_MUTATIONS, run_mutations,
    baseline_commentary, baseline_comparison,
)
from tqm.ai.review_gate import ReviewGate


def test_baseline_passes_gate():
    """Sanity check: the unmutated baseline should pass."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    result = gate.check(baseline_commentary(), baseline_comparison(), "Test")
    assert result.passed, f"Baseline blocked unexpectedly: {[f.code for f in result.blockers]}"


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_each_commentary_mutation_caught(mutation):
    """Every commentary mutation must produce the expected block code."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    mutated = mutation.apply(baseline_commentary())
    result = gate.check(mutated, baseline_comparison(), "Test")
    block_codes = [f.code for f in result.blockers]
    assert mutation.expected_block_code in block_codes, (
        f"GATE HOLE: mutation '{mutation.name}' produced block codes {block_codes}, "
        f"expected {mutation.expected_block_code}. {mutation.description}"
    )


@pytest.mark.parametrize("mutation", COMPARISON_MUTATIONS, ids=lambda m: m.name)
def test_each_comparison_mutation_caught(mutation):
    """Every data-integrity mutation must produce the expected block code (FM-12/13)."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    mutated_comp = mutation.apply(baseline_comparison())
    result = gate.check(baseline_commentary(), mutated_comp, "Test")
    block_codes = [f.code for f in result.blockers]
    assert mutation.expected_block_code in block_codes, (
        f"GATE HOLE: comparison mutation '{mutation.name}' produced block codes {block_codes}, "
        f"expected {mutation.expected_block_code}. {mutation.description}"
    )


def test_full_mutation_report_runs():
    """The runner covers both commentary and comparison mutations."""
    report = run_mutations()
    assert len(report.results) == len(MUTATIONS) + len(COMPARISON_MUTATIONS)
    assert report.passed, "Gate has holes:\n" + report.text()
