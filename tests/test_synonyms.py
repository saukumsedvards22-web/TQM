"""Tests for KPI synonym table and semantic leak detection."""

import pytest

from tqm.ai.kpi_synonyms import SynonymTable, DEFAULT_SYNONYMS


def test_expand_returns_token_and_synonyms():
    t = SynonymTable()
    expanded = t.expand("revenue")
    assert "revenue" in expanded
    assert "sales" in expanded
    assert "turnover" in expanded


def test_expand_empty_returns_empty():
    assert SynonymTable().expand("") == set()


def test_kpi_token_set_excludes_neutral_tokens():
    """'total' is too generic to be a KPI signal."""
    t = SynonymTable()
    owned = t.kpi_token_set("total_revenue")
    assert "total" not in owned
    assert "revenue" in owned
    assert "sales" in owned


def test_kpi_token_set_handles_underscores():
    t = SynonymTable()
    owned = t.kpi_token_set("total_unit_cost")
    assert "cost" in owned
    assert "cogs" in owned


# ── Leak detection ────────────────────────────────────────────────────

def test_no_leak_when_context_only_uses_this_kpi_words():
    t = SynonymTable()
    leaks = t.find_leaks(
        this_kpi_id="total_revenue",
        all_kpi_ids={"total_revenue", "total_cost", "total_qty"},
        context="revenue uplift from seasonal demand",
    )
    assert leaks == set()


def test_no_leak_when_context_uses_synonym_of_this_kpi():
    """The point of the synonym table: 'sales' is a legitimate ref to revenue."""
    t = SynonymTable()
    leaks = t.find_leaks(
        this_kpi_id="total_revenue",
        all_kpi_ids={"total_revenue", "total_cost", "total_qty"},
        context="sales picked up after the rebrand",
    )
    assert leaks == set()


def test_leak_when_context_mentions_other_kpi_synonym():
    """The FM-09 case: revenue finding mentions 'cogs' (synonym of cost)."""
    t = SynonymTable()
    leaks = t.find_leaks(
        this_kpi_id="total_revenue",
        all_kpi_ids={"total_revenue", "total_cost", "total_qty"},
        context="cogs compression supported the result",
    )
    assert "cogs" in leaks


def test_leak_when_context_mentions_other_kpi_native():
    t = SynonymTable()
    leaks = t.find_leaks(
        this_kpi_id="total_revenue",
        all_kpi_ids={"total_revenue", "total_cost", "total_qty"},
        context="cost compression contributed",
    )
    assert "cost" in leaks


def test_word_boundary_prevents_false_positives():
    """'costume' should not match 'cost'."""
    t = SynonymTable()
    leaks = t.find_leaks(
        this_kpi_id="total_revenue",
        all_kpi_ids={"total_revenue", "total_cost"},
        context="costume sales picked up",
    )
    assert leaks == set()


def test_neutral_tokens_dont_leak():
    """'total' appears in every KPI name; it must not be a leak signal."""
    t = SynonymTable()
    leaks = t.find_leaks(
        this_kpi_id="total_revenue",
        all_kpi_ids={"total_revenue", "total_cost"},
        context="total volume in the period was higher",  # 'volume' IS a leak though
    )
    assert "total" not in leaks
    # 'volume' is a synonym of qty, but 'total_qty' is not in this set,
    # so this test specifically checks 'total' alone doesn't trigger.


# ── YAML round-trip ──────────────────────────────────────────────────

def test_load_missing_yaml_uses_defaults(tmp_path):
    missing = tmp_path / "nope.yaml"
    t = SynonymTable.load(missing)
    assert "revenue" in t.table


def test_load_custom_yaml_merges_with_defaults(tmp_path):
    import yaml as yamllib
    path = tmp_path / "syn.yaml"
    path.write_text(yamllib.dump({"widget": ["doohickey", "gizmo"]}))
    t = SynonymTable.load(path)
    assert "widget" in t.table
    assert "doohickey" in t.table["widget"]
    # Defaults still present
    assert "revenue" in t.table
