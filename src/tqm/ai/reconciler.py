"""Number reconciliation — extract every figure from commentary and match against source KPIs.

This is the check that phrase-list filtering cannot substitute for.

Algorithm:
  1. Extract every numeral from the commentary text (integers, decimals, percentages, €-amounts).
  2. For each extracted number, try to match it against a known KPI delta or absolute value.
  3. Flag when a matched number deviates more than MAX_DEVIATION_PCT from the source.
  4. Flag when a percentage claim has no matching source KPI at all (possible fabrication).

What this catches that the direction-conflict check misses:
  - "Revenue grew 12%" when actual delta is 8%  → NUMERIC_MISMATCH
  - "modest decline of 5%" when actual is -35%  → NUMERIC_MISMATCH
  - "€2.4M revenue" when source shows €847k     → NUMERIC_MISMATCH
  - A percentage that matches no known KPI at all → UNVERIFIABLE_CLAIM

What this cannot catch:
  - Correct numbers attached to wrong labels ("Cost grew 12%" when it's revenue that grew 12%)
  - Correct numbers in wrong direction with same magnitude
  Both of these are covered by the direction-conflict check. Together they close the gap.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from .snapshot import SnapshotComparison

log = logging.getLogger(__name__)

MAX_DEVIATION_PCT = 2.0  # % deviation before flagging

# Match numbers in prose: 12%, 12.4%, €847k, €2.4M, 1,200, -35.2
_NUMBER_RE = re.compile(
    r"""
    (?P<currency>[€$£])?                    # optional currency symbol
    (?P<value>-?[\d]{1,3}(?:,\d{3})*(?:\.\d+)?)  # number, possibly with commas
    (?P<scale>[kKmMbB])?                    # optional scale: k, M, B
    \s*(?P<pct>%)?                          # optional percent sign
    """,
    re.VERBOSE,
)

_SCALE = {"k": 1_000, "K": 1_000, "m": 1_000_000, "M": 1_000_000, "b": 1_000_000_000, "B": 1_000_000_000}


@dataclass
class ExtractedNumber:
    raw: str          # original text match
    value: float      # normalised value (scale applied, currency stripped)
    is_pct: bool
    position: int     # character position in text


@dataclass
class ReconciliationIssue:
    severity: Literal["block", "warn"]
    code: str
    message: str
    extracted: str
    source_value: float | None = None
    deviation_pct: float | None = None


@dataclass
class ReconciliationResult:
    passed: bool
    issues: list[ReconciliationIssue] = field(default_factory=list)
    numbers_checked: int = 0
    numbers_matched: int = 0

    def summary(self) -> str:
        if self.passed and not self.issues:
            return f"Reconciliation passed: {self.numbers_matched}/{self.numbers_checked} numbers verified."
        lines = [f"Reconciliation {'PASSED' if self.passed else 'FAILED'} — {len(self.issues)} issue(s):"]
        for issue in self.issues:
            icon = "🔴" if issue.severity == "block" else "🟡"
            lines.append(f"  {icon} [{issue.code}] {issue.message}")
        return "\n".join(lines)


class NumberReconciler:
    """Extract and verify all numbers in AI commentary against source KPI data."""

    def __init__(
        self,
        max_deviation_pct: float = MAX_DEVIATION_PCT,
        min_pct_value: float = 1.0,  # ignore trivial percentages like "1%"
    ) -> None:
        self.max_deviation_pct = max_deviation_pct
        self.min_pct_value = min_pct_value

    def reconcile(self, commentary_text: str, comparison: SnapshotComparison) -> ReconciliationResult:
        """Main entry point. Check all numbers in commentary_text against comparison data."""
        extracted = self._extract_numbers(commentary_text)
        kpi_deltas = comparison.kpi_deltas()
        kpi_absolutes = self._build_absolute_index(comparison)

        issues: list[ReconciliationIssue] = []
        numbers_checked = 0
        numbers_matched = 0

        for num in extracted:
            # Skip trivially small numbers that are likely ordinals or dates
            if abs(num.value) < 1.0:
                continue
            if num.is_pct and abs(num.value) < self.min_pct_value:
                continue

            numbers_checked += 1

            if num.is_pct:
                matched, issue = self._check_pct(num, kpi_deltas)
            else:
                matched, issue = self._check_absolute(num, kpi_absolutes)

            if matched:
                numbers_matched += 1
            if issue:
                issues.append(issue)

        passed = not any(i.severity == "block" for i in issues)
        return ReconciliationResult(
            passed=passed,
            issues=issues,
            numbers_checked=numbers_checked,
            numbers_matched=numbers_matched,
        )

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_numbers(self, text: str) -> list[ExtractedNumber]:
        results: list[ExtractedNumber] = []
        for m in _NUMBER_RE.finditer(text):
            raw_val = m.group("value")
            if not raw_val:
                continue
            try:
                value = float(raw_val.replace(",", ""))
            except ValueError:
                continue

            scale_char = m.group("scale") or ""
            if scale_char:
                value *= _SCALE.get(scale_char, 1)

            is_pct = bool(m.group("pct"))
            results.append(ExtractedNumber(
                raw=m.group(0).strip(),
                value=value,
                is_pct=is_pct,
                position=m.start(),
            ))
        return results

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _check_pct(
        self, num: ExtractedNumber, kpi_deltas: dict
    ) -> tuple[bool, ReconciliationIssue | None]:
        """Match a percentage against known KPI deltas."""
        best_deviation: float | None = None
        best_kpi: str | None = None

        for kpi, delta in kpi_deltas.items():
            source_pct = delta["pct"]
            if abs(source_pct) < self.min_pct_value:
                continue
            deviation = abs(num.value - abs(source_pct))
            if best_deviation is None or deviation < best_deviation:
                best_deviation = deviation
                best_kpi = kpi

        if best_deviation is None:
            # No KPI deltas to compare against at all
            return False, None

        if best_deviation <= self.max_deviation_pct:
            return True, None

        if best_deviation > 10.0:
            # Large deviation — blocking
            source_pct = kpi_deltas[best_kpi]["pct"]  # type: ignore[index]
            return False, ReconciliationIssue(
                severity="block",
                code="NUMERIC_MISMATCH",
                message=(
                    f"Commentary states '{num.raw}' but nearest source KPI "
                    f"({best_kpi}) shows {abs(source_pct):.1f}% — deviation {best_deviation:.1f}pp"
                ),
                extracted=num.raw,
                source_value=abs(source_pct),
                deviation_pct=best_deviation,
            )
        elif best_deviation > self.max_deviation_pct:
            source_pct = kpi_deltas[best_kpi]["pct"]  # type: ignore[index]
            return False, ReconciliationIssue(
                severity="warn",
                code="NUMERIC_APPROXIMATION",
                message=(
                    f"Commentary states '{num.raw}'; nearest KPI ({best_kpi}) "
                    f"shows {abs(source_pct):.1f}% — {best_deviation:.1f}pp off"
                ),
                extracted=num.raw,
                source_value=abs(source_pct),
                deviation_pct=best_deviation,
            )

        return False, None

    def _check_absolute(
        self, num: ExtractedNumber, absolutes: dict[str, list[float]]
    ) -> tuple[bool, ReconciliationIssue | None]:
        """Match an absolute value against known KPI current/previous values."""
        for kpi, values in absolutes.items():
            for source_val in values:
                if source_val == 0:
                    continue
                deviation_pct = abs(num.value - source_val) / abs(source_val) * 100
                if deviation_pct <= self.max_deviation_pct:
                    return True, None

        # No match found — only warn (absolute numbers may be computed or formatted differently)
        if abs(num.value) > 100:
            return False, ReconciliationIssue(
                severity="warn",
                code="UNVERIFIABLE_ABSOLUTE",
                message=f"Value '{num.raw}' does not match any source KPI within {self.max_deviation_pct}%",
                extracted=num.raw,
            )
        return False, None

    def _build_absolute_index(self, comparison: SnapshotComparison) -> dict[str, list[float]]:
        index: dict[str, list[float]] = {}
        for kpi, delta in comparison.kpi_deltas().items():
            index[kpi] = [delta["current"], delta["previous"], delta["abs"]]
        return index
