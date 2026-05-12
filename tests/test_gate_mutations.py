"""Mutation tests: verify the gate catches every documented failure mode.

Each mutation in MUTATIONS represents one way the LLM (or upstream code)
could produce wrong output. The gate must catch each. If a mutation slips
past, it's a gate hole that must be fixed before release.
"""

import pytest

from tqm.ai.mutations import MUTATIONS, run_mutations, baseline_commentary, baseline_comparison
from tqm.ai.review_gate import ReviewGate


def test_baseline_passes_gate():
    """Sanity check: the unmutated baseline should pass."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    result = gate.check(baseline_commentary(), baseline_comparison(), "Test")
    assert result.passed, f"Baseline blocked unexpectedly: {[f.code for f in result.blockers]}"


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_each_mutation_caught_by_gate(mutation):
    """Every documented mutation must produce the expected block code."""
    gate = ReviewGate(static_fallback_pct=200.0, mode="pending_file", pending_dir=None)
    mutated = mutation.apply(baseline_commentary())
    result = gate.check(mutated, baseline_comparison(), "Test")
    block_codes = [f.code for f in result.blockers]
    assert mutation.expected_block_code in block_codes, (
        f"GATE HOLE: mutation '{mutation.name}' produced block codes {block_codes}, "
        f"expected {mutation.expected_block_code}. {mutation.description}"
    )


def test_full_mutation_report_runs():
    """The runner produces a report; useful for CLI."""
    report = run_mutations()
    assert len(report.results) == len(MUTATIONS)
    # If any holes exist, surface them in the assertion message
    assert report.passed, "Gate has holes:\n" + report.text()
