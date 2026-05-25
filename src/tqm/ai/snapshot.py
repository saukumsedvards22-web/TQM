"""Monthly data snapshot — compute KPIs and period-over-period deltas."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from functools import cached_property

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class MonthlySnapshot:
    """Aggregated KPIs for a single calendar month."""

    period: str  # "2024-03"
    kpis: dict[str, float]
    dimension_breakdowns: dict[str, dict[str, float]] = field(default_factory=dict)
    row_count: int = 0
    period_days: int = 0  # actual coverage = (max_date - min_date).days + 1

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        date_col: str,
        measure_cols: list[str],
        dimension_cols: list[str],
        period: str,
    ) -> "MonthlySnapshot":
        kpis: dict[str, float] = {}
        for col in measure_cols:
            if col not in df.columns:
                continue
            total = float(df[col].sum())
            avg = float(df[col].mean())
            mx = float(df[col].max())
            # Skip columns that are 100% null — NaN silently bypasses all gate comparisons
            if math.isnan(avg):
                log.warning("Column %r is all-null; skipping KPI aggregates", col)
                continue
            kpis[f"total_{col}"] = total
            kpis[f"avg_{col}"] = avg
            kpis[f"max_{col}"] = mx if not math.isnan(mx) else 0.0

        breakdowns: dict[str, dict[str, float]] = {}
        for dim in dimension_cols:
            if dim in df.columns and measure_cols:
                primary = measure_cols[0]
                grouped = df.groupby(dim)[primary].sum().nlargest(10)
                breakdowns[dim] = {str(k): float(v) for k, v in grouped.items()}

        period_days = 0
        if date_col in df.columns and len(df):
            try:
                dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if len(dates):
                    period_days = int((dates.max() - dates.min()).days) + 1
            except (TypeError, ValueError):
                period_days = 0

        return cls(
            period=period,
            kpis=kpis,
            dimension_breakdowns=breakdowns,
            row_count=len(df),
            period_days=period_days,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "period": self.period,
                "row_count": self.row_count,
                "period_days": self.period_days,
                "kpis": self.kpis,
                "dimension_breakdowns": self.dimension_breakdowns,
            },
            indent=2,
            ensure_ascii=False,
        )


@dataclass
class SnapshotComparison:
    """Delta between two monthly snapshots."""

    current: MonthlySnapshot
    previous: MonthlySnapshot

    @property
    def period_label(self) -> str:
        return f"{self.current.period} vs {self.previous.period}"

    @cached_property
    def kpi_deltas(self) -> dict[str, dict[str, float]]:  # type: ignore[override]
        """Compute absolute and % change for every shared KPI. Cached — computed once per instance."""
        deltas: dict[str, dict[str, float]] = {}
        for key in self.current.kpis:
            cur = self.current.kpis[key]
            prev = self.previous.kpis.get(key)
            if prev is None:
                continue
            abs_delta = cur - prev
            pct_delta = (abs_delta / prev * 100) if prev != 0 else 0.0
            deltas[key] = {"current": cur, "previous": prev, "abs": abs_delta, "pct": pct_delta}
        return deltas

    def top_movers(self, n: int = 5) -> list[tuple[str, float]]:
        """Return top N KPIs by absolute % change."""
        ranked = sorted(self.kpi_deltas.items(), key=lambda x: abs(x[1]["pct"]), reverse=True)
        return [(k, v["pct"]) for k, v in ranked[:n]]

    def to_prompt_context(self, sanitize: bool = True) -> str:
        """Serialise comparison to a compact JSON string for the AI prompt.

        sanitize=True applies the prompt-injection sanitizer to all string
        values (customer names, segment labels, etc.). Disable only for
        debugging or unit tests that need raw output.
        """
        period_days_note: dict | None = None
        if self.current.period_days > 0 and self.previous.period_days > 0:
            diff = self.current.period_days - self.previous.period_days
            period_days_note = {
                "current_days": self.current.period_days,
                "previous_days": self.previous.period_days,
                "difference_days": diff,
                "analyst_note": (
                    f"Period length differs by {abs(diff)} day(s). "
                    "Attribute up to "
                    f"{abs(diff / max(self.previous.period_days, 1)) * 100:.1f}% "
                    "of any revenue delta to period length, not business change."
                    if abs(diff) >= 2 else "Period lengths match."
                ),
            }

        payload: dict = {
            "period": self.period_label,
            "kpi_deltas": self.kpi_deltas,
            "top_movers": self.top_movers(),
            "current_breakdowns": self.current.dimension_breakdowns,
            "previous_breakdowns": self.previous.dimension_breakdowns,
        }
        if period_days_note:
            payload["period_days"] = period_days_note

        if sanitize:
            from .sanitizer import PromptSanitizer
            sanitized, redactions = PromptSanitizer().sanitize_dict(payload)
            if redactions:
                import logging
                logging.getLogger(__name__).warning(
                    "Prompt sanitizer redacted %d field(s): %s",
                    len(redactions), redactions[:5],
                )
                sanitized["_sanitizer_redactions"] = redactions
            payload = sanitized

        return json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
