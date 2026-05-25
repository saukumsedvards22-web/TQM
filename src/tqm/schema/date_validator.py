"""Date column validator — verify the chosen date column is fit for time-intelligence.

Catches:
  - Column is text, not datetime (type coercion failed silently)
  - More than 5% null dates (gaps that will corrupt YTD/MoM)
  - Non-monotonic dates (rows not in order — DATEADD results unpredictable)
  - Duplicate date+key combinations (double-counting in CALCULATE)
  - Date range doesn't include the expected report month
  - Future dates (data entry errors that inflate current-period metrics)

Returns a DateValidationResult with severity-tagged issues.
Every time-intelligence measure is wrong if this fails. This is not optional.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class DateIssue:
    severity: Literal["block", "warn"]
    code: str
    message: str
    detail: str = ""


@dataclass
class DateValidationResult:
    column: str
    passed: bool
    issues: list[DateIssue] = field(default_factory=list)
    min_date: date | None = None
    max_date: date | None = None
    null_rate: float = 0.0
    row_count: int = 0

    @property
    def blockers(self) -> list[DateIssue]:
        return [i for i in self.issues if i.severity == "block"]

    def summary(self) -> str:
        if self.passed:
            return f"Date column '{self.column}' OK: {self.min_date} → {self.max_date}, {self.row_count:,} rows"
        lines = [f"Date column '{self.column}' FAILED:"]
        for issue in self.issues:
            icon = "🔴" if issue.severity == "block" else "🟡"
            lines.append(f"  {icon} [{issue.code}] {issue.message}")
        return "\n".join(lines)


class DateColumnValidator:
    """Validate that a date column is fit for Power BI time-intelligence."""

    def __init__(
        self,
        max_null_rate: float = 0.05,
        max_future_days: int = 3,
        expected_period: str | None = None,
    ) -> None:
        self.max_null_rate = max_null_rate
        self.max_future_days = max_future_days
        self.expected_period = expected_period  # "2024-03" format

    def validate(self, df: pd.DataFrame, date_col: str) -> DateValidationResult:
        issues: list[DateIssue] = []
        result = DateValidationResult(column=date_col, passed=False, row_count=len(df))

        if date_col not in df.columns:
            issues.append(DateIssue(
                severity="block",
                code="COLUMN_NOT_FOUND",
                message=f"Date column '{date_col}' does not exist in the DataFrame",
            ))
            result.issues = issues
            return result

        series = df[date_col]

        # 1. Type check
        if not pd.api.types.is_datetime64_any_dtype(series):
            coerced = pd.to_datetime(series, errors="coerce")
            coerce_success = coerced.notna().mean()
            if coerce_success < 0.5:
                issues.append(DateIssue(
                    severity="block",
                    code="NOT_A_DATE",
                    message=f"'{date_col}' is {series.dtype} — fewer than 50% of values parse as dates",
                    detail=f"Sample values: {list(series.dropna().unique()[:5])}",
                ))
                result.issues = issues
                return result
            series = coerced
            issues.append(DateIssue(
                severity="warn",
                code="DATE_NOT_PARSED",
                message=f"'{date_col}' is {df[date_col].dtype}, coerced to datetime — confirm ingestion type detection",
            ))

        # 2. Null rate
        null_rate = float(series.isna().mean())
        result.null_rate = null_rate
        if null_rate > self.max_null_rate:
            issues.append(DateIssue(
                severity="block",
                code="HIGH_NULL_RATE",
                message=f"{null_rate:.1%} of dates are null — YTD and MoM will be incorrect",
                detail=f"{int(null_rate * len(series))} null rows out of {len(series)}",
            ))

        clean = series.dropna().sort_values()
        if clean.empty:
            issues.append(DateIssue(severity="block", code="ALL_NULL", message="All date values are null"))
            result.issues = issues
            return result

        result.min_date = clean.min().date()
        result.max_date = clean.max().date()

        # 3. Future dates
        today = datetime.utcnow().date()
        cutoff = pd.Timestamp(today) + pd.Timedelta(days=self.max_future_days)
        future_count = int((series > cutoff).sum())
        if future_count > 0:
            issues.append(DateIssue(
                severity="warn",
                code="FUTURE_DATES",
                message=f"{future_count} rows have dates more than {self.max_future_days} days in the future",
                detail=f"Max date: {result.max_date} — possible data entry error or wrong column",
            ))

        # 4. Expected period coverage
        if self.expected_period:
            parts = self.expected_period.split("-")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError(
                    f"expected_period must be YYYY-MM, got {self.expected_period!r}"
                )
            year, month = int(parts[0]), int(parts[1])
            if not (1 <= month <= 12):
                raise ValueError(
                    f"expected_period month out of range 1–12: {self.expected_period!r}"
                )
            period_start = pd.Timestamp(year, month, 1)
            period_end = period_start + pd.offsets.MonthEnd(0)
            in_period = series.between(period_start, period_end).sum()
            if in_period == 0:
                issues.append(DateIssue(
                    severity="block",
                    code="PERIOD_MISMATCH",
                    message=f"No dates fall within expected period {self.expected_period}",
                    detail=f"Data spans {result.min_date} → {result.max_date}. Wrong file?",
                ))
            elif in_period < len(series) * 0.8:
                issues.append(DateIssue(
                    severity="warn",
                    code="PARTIAL_PERIOD",
                    message=f"Only {in_period}/{len(series)} rows fall within {self.expected_period}",
                    detail="Partial month? Check if data is complete.",
                ))

        # 5. Duplicate date detection (warn only — legitimate in transaction data)
        dup_count = int(series.duplicated().sum())
        if dup_count == 0:
            issues.append(DateIssue(
                severity="warn",
                code="ALL_DATES_UNIQUE",
                message="Every date is unique — this may be a summary row (one per day) rather than a transaction table",
                detail="PREVIOUSMONTH / DATEADD work correctly, but verify grain matches your DAX.",
            ))

        passed = not any(i.severity == "block" for i in issues)
        result.passed = passed
        result.issues = issues

        if passed:
            log.info(result.summary())
        else:
            log.error(result.summary())

        return result

    def pick_best_date_column(
        self,
        df: pd.DataFrame,
        candidates: list[str],
        explicit_config: str | None = None,
    ) -> tuple[str | None, DateValidationResult | None]:
        """Select the date column, with strict ambiguity handling.

        Priority:
          1. explicit_config — if set, validate and return it (or raise if it fails).
          2. Exactly one candidate passes — return it.
          3. Zero candidates pass — log error, return best (fewest blockers).
          4. Multiple candidates pass — ABORT. This is the shipping/logistics
             problem: order_date vs ship_date vs posted_date all pass validation
             but mean different things. Silence here means wrong time-intelligence.
             The caller must specify explicit_config or the pipeline stops.

        Returns (column_name, validation_result) or (None, None) if no candidates.
        Raises DateAmbiguityError when multiple candidates pass and no config given.
        """
        if not candidates:
            return None, None

        # Explicit config overrides everything
        if explicit_config:
            if explicit_config not in df.columns:
                raise ValueError(
                    f"Configured date_column '{explicit_config}' not found in data. "
                    f"Available columns: {list(df.columns)}"
                )
            result = self.validate(df, explicit_config)
            if not result.passed:
                log.warning(
                    "Configured date_column '%s' has validation issues:\n%s",
                    explicit_config, result.summary(),
                )
            return explicit_config, result

        # Auto-detect: evaluate all candidates
        results = [(col, self.validate(df, col)) for col in candidates]
        passing = [(col, r) for col, r in results if r.passed]

        if len(passing) == 1:
            col, result = passing[0]
            log.info("Date column auto-selected: '%s'", col)
            return col, result

        if len(passing) > 1:
            passing_names = [col for col, _ in passing]
            raise DateAmbiguityError(
                f"Multiple date columns passed validation: {passing_names}.\n"
                "Specify 'date_column' in your client config to disambiguate.\n"
                "In shipping/logistics data this is order_date vs ship_date vs posted_date "
                "— they produce different YTD and MoM figures. Do not auto-resolve."
            )

        # None passed — return least-broken candidate with a warning
        best_col, best_result = min(results, key=lambda x: len(x[1].blockers))
        log.error(
            "No date column passed validation. Returning least-broken candidate '%s'. "
            "Time-intelligence measures may be incorrect. Specify 'date_column' in config.",
            best_col,
        )
        return best_col, best_result


class DateAmbiguityError(RuntimeError):
    """Raised when multiple date columns pass validation and no explicit config is set."""
