"""Golden-value unit tests for DAX measures.

The static validator catches syntax errors. This catches semantic errors:
wrong filter context, missing USERELATIONSHIP, row-context propagation bugs,
time intelligence on the wrong date table. These compile fine. They produce
wrong numbers. Only execution against known-good data reveals them.

Workflow:
  1. For each generated measure, the analyst specifies expected values
     against a reference dataset (the first month of real client data).
  2. These expected values are stored as a golden file (YAML).
  3. On every subsequent deploy, the measures are executed via DAX Studio
     or the XMLA endpoint and results compared to golden values.
  4. Deviation > TOLERANCE_PCT is a deployment blocker.

Without golden tests, criterion 4 ("zero DAX errors") is syntactic safety only.
With them, you have positive verification that the math is correct.

This module handles:
  - Golden file schema (YAML)
  - Golden value capture from a reference query result
  - Golden value comparison
  - Report generation

Execution of DAX itself requires an XMLA-reachable dataset and is done
via the CLI (tqm dax golden-verify) or Tabular Editor CLI.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

TOLERANCE_PCT = 0.1  # 0.1% relative — for currency / count measures
TOLERANCE_ABS_DEFAULT_PP = 0.05  # 0.05 percentage points — for ratio / % measures

# Heuristic: measure names matching these are ratios where absolute tolerance is the right unit.
# Relative 0.1% on a margin of 12.4% means tolerance ≈ 0.0124pp — absurdly tight.
# Absolute 0.05pp on the same measure is the realistic floor (DAX rounding alone uses more).
_RATIO_NAME_PATTERNS = re.compile(r"(%|pct|percent|rate|ratio|margin|share|coverage|conversion)", re.I)


@dataclass
class GoldenValue:
    measure_name: str
    filter_context: str        # plain-English description e.g. "All data, no filter"
    dax_filter: str            # e.g. "ALL(sales)" or "sales[region] = \"Rīga\""
    expected_value: float
    # Exactly ONE of these should be set. tolerance_abs takes precedence if both present.
    tolerance_pct: float = TOLERANCE_PCT      # relative %, used for currency/count measures
    tolerance_abs: float | None = None        # absolute, in measure's own units (pp for ratios)
    notes: str = ""


@dataclass
class GoldenTestResult:
    measure_name: str
    filter_context: str
    expected: float
    actual: float | None
    passed: bool
    deviation_pct: float | None
    error: str = ""

    def summary_line(self) -> str:
        if self.error:
            return f"  ❌ [{self.measure_name}] ERROR: {self.error}"
        if self.actual is None:
            return f"  ⚠️  [{self.measure_name}] No result returned"
        icon = "✅" if self.passed else "❌"
        return (
            f"  {icon} [{self.measure_name}] ({self.filter_context}) "
            f"expected={self.expected:,.4f} actual={self.actual:,.4f} "
            f"deviation={self.deviation_pct:.3f}%"
        )


@dataclass
class GoldenSignoff:
    """Two-analyst rule: golden values must be seeded AND independently verified.

    A suite without complete signoff cannot be used for production verification.
    Refusing to run is the only honest behaviour — otherwise the seeder becomes
    the new single point of failure (acknowledged review hole).
    """
    seeded_by: str = ""
    seeded_at: str = ""
    verified_by: str = ""        # must differ from seeded_by
    verified_at: str = ""
    client_signoff_email: str = ""
    client_signoff_at: str = ""

    def is_complete(self) -> bool:
        return bool(
            self.seeded_by and self.verified_by
            and self.seeded_by != self.verified_by
            and self.client_signoff_email
        )

    def missing(self) -> list[str]:
        gaps: list[str] = []
        if not self.seeded_by:
            gaps.append("seeded_by")
        if not self.verified_by:
            gaps.append("verified_by")
        if self.seeded_by and self.verified_by and self.seeded_by == self.verified_by:
            gaps.append("verified_by must differ from seeded_by")
        if not self.client_signoff_email:
            gaps.append("client_signoff_email")
        return gaps


class GoldenSuiteUnsignedError(RuntimeError):
    """Raised when compare() is called on a suite without complete signoff."""


@dataclass
class GoldenSuite:
    client_name: str
    dataset_name: str
    reference_period: str
    tests: list[GoldenValue] = field(default_factory=list)
    signoff: GoldenSignoff = field(default_factory=GoldenSignoff)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        data = {
            "client_name": self.client_name,
            "dataset_name": self.dataset_name,
            "reference_period": self.reference_period,
            "signoff": {
                "seeded_by": self.signoff.seeded_by,
                "seeded_at": self.signoff.seeded_at,
                "verified_by": self.signoff.verified_by,
                "verified_at": self.signoff.verified_at,
                "client_signoff_email": self.signoff.client_signoff_email,
                "client_signoff_at": self.signoff.client_signoff_at,
            },
            "tests": [
                {
                    "measure_name": t.measure_name,
                    "filter_context": t.filter_context,
                    "dax_filter": t.dax_filter,
                    "expected_value": t.expected_value,
                    "tolerance_pct": t.tolerance_pct,
                    "tolerance_abs": t.tolerance_abs,
                    "notes": t.notes,
                }
                for t in self.tests
            ],
        }
        path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        log.info("Golden suite saved: %s (%d tests)", path, len(self.tests))

    @classmethod
    def load(cls, path: Path) -> "GoldenSuite":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        tests = [GoldenValue(**t) for t in data.get("tests", [])]
        signoff_data = data.get("signoff", {}) or {}
        return cls(
            client_name=data["client_name"],
            dataset_name=data["dataset_name"],
            reference_period=data["reference_period"],
            tests=tests,
            signoff=GoldenSignoff(**signoff_data),
        )

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(self, actuals: dict[str, float | None], *, allow_unsigned: bool = False) -> list[GoldenTestResult]:
        """Compare expected values against actuals dict (measure_name -> value).

        Raises GoldenSuiteUnsignedError if the two-analyst signoff is incomplete,
        unless allow_unsigned=True is passed (for unit tests and CI dry runs only).
        """
        if not allow_unsigned and not self.signoff.is_complete():
            raise GoldenSuiteUnsignedError(
                f"Golden suite for {self.client_name} is missing signoff: {self.signoff.missing()}. "
                "Production verification requires two-analyst signoff and client confirmation. "
                "Pass allow_unsigned=True only for unit tests or CI dry runs."
            )
        results: list[GoldenTestResult] = []
        for test in self.tests:
            actual = actuals.get(test.measure_name)
            if actual is None:
                results.append(GoldenTestResult(
                    measure_name=test.measure_name,
                    filter_context=test.filter_context,
                    expected=test.expected_value,
                    actual=None,
                    passed=False,
                    deviation_pct=None,
                    error="Measure not found in actuals — not deployed or name mismatch",
                ))
                continue

            # Choose tolerance band: absolute takes precedence, else relative %
            abs_diff = abs(actual - test.expected_value)
            if test.tolerance_abs is not None:
                passed = abs_diff <= test.tolerance_abs
                # deviation_pct reported for display only
                if test.expected_value == 0:
                    deviation_pct = abs_diff * 100
                else:
                    deviation_pct = abs_diff / abs(test.expected_value) * 100
            else:
                if test.expected_value == 0:
                    deviation_pct = abs(actual) * 100  # anything non-zero = infinite relative deviation
                    passed = abs(actual) <= test.tolerance_pct  # interpret as absolute when expected is 0
                else:
                    deviation_pct = abs_diff / abs(test.expected_value) * 100
                    passed = deviation_pct <= test.tolerance_pct
            results.append(GoldenTestResult(
                measure_name=test.measure_name,
                filter_context=test.filter_context,
                expected=test.expected_value,
                actual=actual,
                passed=passed,
                deviation_pct=deviation_pct,
            ))
        return results

    def report(self, actuals: dict[str, float | None], *, allow_unsigned: bool = False) -> str:
        results = self.compare(actuals, allow_unsigned=allow_unsigned)
        passed = sum(1 for r in results if r.passed)
        lines = [
            f"Golden test results — {self.client_name} / {self.reference_period}",
            f"{passed}/{len(results)} passed  (tolerance ≤ {TOLERANCE_PCT}%)",
            "",
        ]
        lines += [r.summary_line() for r in results]
        failed = [r for r in results if not r.passed]
        if failed:
            lines += [
                "",
                "FAILED MEASURES — do not deploy until these pass:",
                *[f"  {r.measure_name}: expected {r.expected:.4f}, got {r.actual}" for r in failed],
            ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Bootstrap helper — generate a golden file from a known-good run
    # ------------------------------------------------------------------

    @classmethod
    def bootstrap_from_dataframe(
        cls,
        client_name: str,
        dataset_name: str,
        reference_period: str,
        measure_actuals: dict[str, float],
        tolerance_pct: float = TOLERANCE_PCT,
        seeded_by: str = "",
    ) -> "GoldenSuite":
        """Create a golden suite from a trusted first-run result.

        IMPORTANT: this is the SEEDING step only. The resulting suite cannot be used
        for production verification until a second analyst fills in `verified_by` /
        `verified_at` after independently reproducing each value, AND the client
        confirms by email (`client_signoff_email` / `client_signoff_at`).

        Call compare(allow_unsigned=True) for dry-run testing only.
        """
        tests: list[GoldenValue] = []
        for name, value in measure_actuals.items():
            if _RATIO_NAME_PATTERNS.search(name):
                # Ratio/percentage measure → absolute tolerance in pp
                tests.append(GoldenValue(
                    measure_name=name,
                    filter_context="All data, no filter",
                    dax_filter="",
                    expected_value=value,
                    tolerance_abs=TOLERANCE_ABS_DEFAULT_PP,
                    notes=f"Auto-classified as ratio measure (tolerance_abs={TOLERANCE_ABS_DEFAULT_PP}pp). Verify manually.",
                ))
            else:
                tests.append(GoldenValue(
                    measure_name=name,
                    filter_context="All data, no filter",
                    dax_filter="",
                    expected_value=value,
                    tolerance_pct=tolerance_pct,
                    notes="Bootstrap — verify manually before treating as authoritative.",
                ))
        from datetime import datetime, timezone
        signoff = GoldenSignoff(
            seeded_by=seeded_by,
            seeded_at=datetime.now(timezone.utc).isoformat() if seeded_by else "",
        )
        suite = cls(
            client_name=client_name,
            dataset_name=dataset_name,
            reference_period=reference_period,
            tests=tests,
            signoff=signoff,
        )
        log.warning(
            "Bootstrapped golden suite for %s with %d measures. "
            "Signoff is INCOMPLETE — a second analyst must independently verify "
            "and the client must confirm before this suite can be used in production.",
            client_name, len(tests),
        )
        return suite

    def dax_query_script(self) -> str:
        """Generate a DAX Studio query script to evaluate all test measures."""
        lines = ["// Golden test queries — paste into DAX Studio", ""]
        for test in self.tests:
            filter_clause = f"CALCULATETABLE(ROW(\"{test.measure_name}\", [{test.measure_name}]), {test.dax_filter})" \
                if test.dax_filter else f"ROW(\"{test.measure_name}\", [{test.measure_name}])"
            lines.append(f"// {test.filter_context}")
            lines.append(f"EVALUATE {filter_clause}")
            lines.append("")
        return "\n".join(lines)
