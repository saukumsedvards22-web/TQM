"""KPI synonym tables for the semantic-leak check.

The CONTEXT_KPI_LEAK gate previously used naive token matching: a context
field for kpi_id=total_revenue passed if it didn't contain the literal
token "cost". That misses the actual failure mode:

    kpi_id="total_revenue"
    context="sales picked up after the price cut"
                ^^^^^                  ^^^^^
              synonym of revenue   synonym of price (different KPI)

"Sales" is a legitimate way to refer to revenue. "Price" is a different
KPI. Token matching reads both as foreign. Semantic matching reads
"sales" as a synonym of revenue (owned by this kpi_id) and "price" as
foreign (leaked).

This module ships DEFAULT_SYNONYMS as a starting point. Each client gets
their own copy in `config/<client>_synonyms.yaml` so finance terminology
can be tuned to the client's vocabulary without modifying code.

The check should produce ≈0 false positives on normal commentary and
catch the case where Claude swaps one KPI's name for another's synonym.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Each entry maps a canonical KPI noun to its accepted alternatives.
# Bi-directional: "sales" canonicalises to "revenue", and vice versa.
DEFAULT_SYNONYMS: dict[str, set[str]] = {
    "revenue":  {"sales", "turnover", "income", "topline", "bookings"},
    "sales":    {"revenue", "turnover", "income", "topline", "bookings"},
    "cost":     {"cogs", "expense", "spend", "outlay"},
    "cogs":     {"cost", "expense", "spend"},
    "qty":      {"units", "volume", "count", "quantity"},
    "quantity": {"qty", "units", "volume", "count"},
    "volume":   {"qty", "units", "quantity"},
    "units":    {"qty", "volume", "quantity", "count"},
    "margin":   {"profit", "gross", "contribution"},
    "profit":   {"margin", "earnings", "bottomline"},
    "discount": {"rebate", "markdown", "concession"},
    "price":    {"rate", "tariff", "asp"},
    "customer": {"client", "buyer", "account"},
    "supplier": {"vendor", "partner"},
    "order":    {"booking", "po"},
    "shipment": {"delivery", "dispatch"},
    "region":   {"territory", "area", "geography"},
    "product":  {"sku", "item", "article"},
}

# Tokens too generic to count as KPI leak signals — these appear in normal prose.
_NEUTRAL_TOKENS: frozenset[str] = frozenset({
    "total", "month", "period", "year", "data", "value", "number",
    "change", "increase", "decrease", "growth", "drop",
})


@dataclass
class SynonymTable:
    """Canonical → set of alternative spellings."""
    table: dict[str, set[str]] = field(default_factory=lambda: dict(DEFAULT_SYNONYMS))

    @classmethod
    def load(cls, path: Path) -> "SynonymTable":
        """Load from a YAML file. Falls back to defaults on missing file."""
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        merged = dict(DEFAULT_SYNONYMS)
        for canonical, alts in data.items():
            merged[canonical.lower()] = set(s.lower() for s in alts)
        return cls(table=merged)

    def expand(self, token: str) -> set[str]:
        """Return {token} ∪ all synonyms of token. Empty token → empty set."""
        if not token:
            return set()
        token = token.lower()
        return {token} | self.table.get(token, set())

    def kpi_token_set(self, kpi_id: str) -> set[str]:
        """All tokens owned by a kpi_id: its own words + their synonyms.

        Stopwords ("total", "month", "year", ...) are removed because they
        appear in normal prose and would produce false positives.
        """
        owned: set[str] = set()
        for token in kpi_id.replace("_", " ").split():
            t = token.lower()
            if len(t) <= 3 or t in _NEUTRAL_TOKENS:
                continue
            owned |= self.expand(t)
        return owned

    def find_leaks(
        self,
        this_kpi_id: str,
        all_kpi_ids: set[str],
        context: str,
    ) -> set[str]:
        """Return tokens in context that belong to a DIFFERENT KPI's owned set.

        A token is a leak iff:
          - it appears in context (case-insensitive)
          - it belongs to some other_kpi's owned_set
          - it does NOT belong to this_kpi's owned_set

        Returns the set of leaking tokens (empty = clean).
        """
        if not context or not this_kpi_id:
            return set()

        this_owned = self.kpi_token_set(this_kpi_id)
        other_kpis = all_kpi_ids - {this_kpi_id}
        # Aggregate owned tokens of all other KPIs (excluding tokens this kpi owns)
        other_owned: set[str] = set()
        for other in other_kpis:
            other_owned |= self.kpi_token_set(other) - this_owned

        ctx_lower = context.lower()
        leaks: set[str] = set()
        for tok in other_owned:
            # Word-boundary match — "cost" must not match "costing", "costume"
            import re
            if re.search(rf"\b{re.escape(tok)}\b", ctx_lower):
                leaks.add(tok)
        return leaks
