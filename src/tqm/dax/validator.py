"""DAX measure validator — syntax and semantic checks before deployment.

Power BI's XMLA endpoint will reject malformed DAX at deployment time,
but by then you've already written a pending script and possibly confused
the client's dataset. Catch it here first.

Checks:
  1. Balanced parentheses (most common LLM DAX error)
  2. Balanced brackets (measure references)
  3. Known dangerous patterns (bare division, implicit CALCULATE filter)
  4. Table references exist in the model schema
  5. Column references exist in the named table
  6. Measure name uniqueness within the set
  7. Format string sanity

This is a static checker — it does NOT execute DAX. For execution
validation, use the XMLA endpoint's VertiPaq diagnostics or DAX Studio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .measures import DAXMeasure, DAXMeasureSet


@dataclass
class DAXIssue:
    severity: Literal["error", "warning"]
    code: str
    measure: str
    message: str
    snippet: str = ""


@dataclass
class DAXValidationResult:
    passed: bool
    issues: list[DAXIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[DAXIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[DAXIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def summary(self) -> str:
        if self.passed and not self.warnings:
            return f"DAX validation passed ({len(self.issues)} warnings)."
        lines = [f"DAX validation {'PASSED' if self.passed else 'FAILED'} — {len(self.errors)} errors, {len(self.warnings)} warnings:"]
        for issue in self.issues:
            icon = "🔴 ERROR  " if issue.severity == "error" else "🟡 WARNING"
            lines.append(f"  {icon} [{issue.measure}] [{issue.code}] {issue.message}")
            if issue.snippet:
                lines.append(f"           {issue.snippet[:120]}")
        return "\n".join(lines)


# ── Patterns ──────────────────────────────────────────────────────────

_BARE_DIVISION = re.compile(r"(?<![A-Z])/(?!/)(?!\*)", re.I)  # / not preceded by https or comment
_MISSING_DIVIDE = re.compile(r"\bDIVIDE\s*\(", re.I)
_CALCULATE = re.compile(r"\bCALCULATE\s*\(", re.I)
_FILTER_AS_SECOND_ARG = re.compile(r"CALCULATE\s*\([^,]+,\s*FILTER\s*\(", re.I)
_TABLE_REF = re.compile(r"'?([A-Za-z_][A-Za-z0-9_\s]*)'?\[([A-Za-z_][A-Za-z0-9_\s]*)\]")
_MEASURE_REF = re.compile(r"(?<!')\[([A-Za-z_][A-Za-z0-9_ %#]+)\]")
_FORMAT_STRINGS_NUMERIC = re.compile(r"^[#0,.\-+ ]*[€$%]?$")
_BLANK_EXPRESSION = re.compile(r"^\s*(BLANK\(\)|\"\"|\s*)$", re.I)
_DAX_STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')


def _strip_string_literals(expr: str) -> str:
    """Replace DAX string literals with empty strings before structural checks.

    Brackets and parentheses inside string literals must not be counted as
    structural tokens — "Price [EUR]" has a bracket that isn't a column ref.
    """
    return _DAX_STRING_LITERAL.sub('""', expr)


class DAXValidator:
    """Static DAX measure validator."""

    def __init__(self, known_tables: set[str] | None = None, known_columns: dict[str, set[str]] | None = None) -> None:
        self.known_tables = {t.lower() for t in (known_tables or set())}
        self.known_columns: dict[str, set[str]] = {
            t.lower(): {c.lower() for c in cols}
            for t, cols in (known_columns or {}).items()
        }

    def validate_set(self, measure_set: DAXMeasureSet) -> DAXValidationResult:
        all_issues: list[DAXIssue] = []

        # Name uniqueness
        names = [m.name for m in measure_set.measures]
        seen: set[str] = set()
        for name in names:
            if name.lower() in seen:
                all_issues.append(DAXIssue(
                    severity="error", code="DUPLICATE_NAME",
                    measure=name, message="Duplicate measure name — second will overwrite first in Power BI",
                ))
            seen.add(name.lower())

        for measure in measure_set.measures:
            all_issues += self.validate_measure(measure, set(names))

        passed = not any(i.severity == "error" for i in all_issues)
        return DAXValidationResult(passed=passed, issues=all_issues)

    def validate_measure(self, measure: DAXMeasure, all_measure_names: set[str] | None = None) -> list[DAXIssue]:
        issues: list[DAXIssue] = []
        expr = measure.expression
        name = measure.name
        # Strip string literals before structural checks so brackets/parens
        # inside "quoted strings" aren't counted as column/measure references
        structural_expr = _strip_string_literals(expr)

        # 1. Blank / trivially wrong expressions
        if _BLANK_EXPRESSION.match(expr):
            issues.append(DAXIssue(
                severity="error", code="EMPTY_EXPRESSION",
                measure=name, message="Expression is blank or trivially empty",
            ))
            return issues  # No point running further checks

        # 2. Balanced parentheses (check on string-stripped expression)
        depth = 0
        for ch in structural_expr:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth < 0:
                break
        if depth != 0:
            issues.append(DAXIssue(
                severity="error", code="UNBALANCED_PARENS",
                measure=name,
                message=f"Unbalanced parentheses (net depth={depth}) — DAX will not compile",
                snippet=expr[:100],
            ))

        # 3. Balanced brackets (check on string-stripped expression)
        brackets = structural_expr.count("[") - structural_expr.count("]")
        if brackets != 0:
            issues.append(DAXIssue(
                severity="error", code="UNBALANCED_BRACKETS",
                measure=name,
                message="Unbalanced square brackets — column/measure reference incomplete",
                snippet=expr[:100],
            ))

        # 4. Bare division (should use DIVIDE)
        if _BARE_DIVISION.search(expr) and not _MISSING_DIVIDE.search(expr):
            issues.append(DAXIssue(
                severity="warning", code="BARE_DIVISION",
                measure=name,
                message="Uses bare / operator — use DIVIDE(num, denom, 0) to handle zero denominators",
                snippet=re.search(r".{0,20}/.{0,20}", expr).group() if re.search(r".{0,20}/.{0,20}", expr) else "",
            ))

        # 5. CALCULATE with FILTER as second arg (performance anti-pattern)
        if _FILTER_AS_SECOND_ARG.search(expr):
            issues.append(DAXIssue(
                severity="warning", code="CALCULATE_FILTER_ANTIPATTERN",
                measure=name,
                message="CALCULATE(expr, FILTER(...)) is slow — prefer CALCULATE(expr, Table[Col] = value)",
            ))

        # 6. Table/column reference validation
        if self.known_tables or self.known_columns:
            for table_ref, col_ref in _TABLE_REF.findall(expr):
                t = table_ref.strip().lower()
                c = col_ref.strip().lower()
                if self.known_tables and t not in self.known_tables:
                    issues.append(DAXIssue(
                        severity="error", code="UNKNOWN_TABLE",
                        measure=name,
                        message=f"Table '{table_ref}' not found in schema",
                        snippet=f"'{table_ref}'[{col_ref}]",
                    ))
                elif self.known_columns and t in self.known_columns and c not in self.known_columns[t]:
                    issues.append(DAXIssue(
                        severity="error", code="UNKNOWN_COLUMN",
                        measure=name,
                        message=f"Column '{col_ref}' not found in table '{table_ref}'",
                        snippet=f"'{table_ref}'[{col_ref}]",
                    ))

        # 7. Format string sanity
        if measure.format_string and "%" in measure.format_string:
            if "0" not in measure.format_string and "#" not in measure.format_string:
                issues.append(DAXIssue(
                    severity="warning", code="FORMAT_STRING_SUSPECT",
                    measure=name,
                    message=f"Format string '{measure.format_string}' has % but no digit placeholders",
                ))

        # 8. Missing time-intelligence pair (warn if MoM exists but YoY doesn't)
        if all_measure_names:
            name_lower = name.lower()
            if "mom" in name_lower:
                yoy_equivalent = name.lower().replace("mom", "yoy")
                if not any(yoy_equivalent in n.lower() for n in all_measure_names):
                    issues.append(DAXIssue(
                        severity="warning", code="MISSING_YOY_PAIR",
                        measure=name,
                        message="MoM measure exists but no corresponding YoY measure found",
                    ))

        return issues
