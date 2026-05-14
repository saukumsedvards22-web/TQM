"""Clean-month checker — determines tier eligibility from the audit log.

See docs/clean_month.md for the rationale behind each criterion. This
module is the executable form: it reads the audit log and corrections log,
applies the seven criteria, and produces a CleanMonthResult per month.

Importantly, this code does NOT change a client's tier. That's a billing
decision. This produces evidence — receipts the operations lead can show
when downgrading or refusing a downgrade.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)


# ---------- ClientCorrection ----------

@dataclass
class ClientCorrection:
    """A logged dispute: client says report number X is wrong."""
    report_id: str
    logged_at: str
    logged_by: str
    field: str                                  # e.g. "kpi_deltas.total_revenue.current"
    claimed_value: float                        # what the report said
    actual_value: float                         # what the client says is correct
    source_of_truth: str                        # where actual_value comes from
    severity: Literal["material", "cosmetic"]   # >2% of field magnitude = material
    client_name: str = ""

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "logged_at": self.logged_at,
            "logged_by": self.logged_by,
            "field": self.field,
            "claimed_value": self.claimed_value,
            "actual_value": self.actual_value,
            "source_of_truth": self.source_of_truth,
            "severity": self.severity,
            "client_name": self.client_name,
        }


class CorrectionsLog:
    """Append-only log of client-disputed numbers."""

    def __init__(self, log_dir: Path = Path(".tqm_corrections")) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, client_name: str) -> Path:
        safe = client_name.lower().replace(" ", "_").replace("/", "_")
        return self.log_dir / f"{safe}_corrections.jsonl"

    def log(self, correction: ClientCorrection) -> None:
        path = self._path(correction.client_name)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(correction.to_dict(), ensure_ascii=False) + "\n")
        log.warning(
            "Client correction logged: %s field=%s claimed=%s actual=%s (%s)",
            correction.report_id, correction.field, correction.claimed_value,
            correction.actual_value, correction.severity,
        )

    def for_client(self, client_name: str) -> list[ClientCorrection]:
        path = self._path(client_name)
        if not path.exists():
            return []
        corrections: list[ClientCorrection] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                corrections.append(ClientCorrection(**data))
            except (json.JSONDecodeError, TypeError) as exc:
                log.warning("Skipping malformed correction line: %s", exc)
        return corrections


# ---------- Clean-month result ----------

@dataclass
class CleanMonthResult:
    client_name: str
    year_month: str            # "2024-07"
    is_clean: bool
    failed_criteria: list[str] = field(default_factory=list)
    delivered_reports: int = 0
    corrections_count: int = 0
    blocker_count: int = 0


# ---------- Checker ----------

class CleanMonthChecker:
    """Apply the 7-criterion clean-month definition.

    Constructor takes the audit log and corrections log paths. The actual
    audit reading uses AuditLog from reporting.audit_log; we delegate to it.
    """

    WINDOW_MONTHS = 6  # Spot-Check eligibility requires this many consecutive clean months

    def __init__(
        self,
        audit_log_dir: Path = Path(".tqm_audit"),
        corrections_log_dir: Path = Path(".tqm_corrections"),
    ) -> None:
        from .audit_log import AuditLog
        self.audit = AuditLog(log_dir=audit_log_dir)
        self.corrections = CorrectionsLog(log_dir=corrections_log_dir)

    def check_month(self, client_name: str, year_month: str) -> CleanMonthResult:
        """Apply all 7 criteria to one calendar month."""
        result = CleanMonthResult(client_name=client_name, year_month=year_month, is_clean=False)

        all_entries = self.audit.history(client_name)
        month_entries = [e for e in all_entries if e.generated_at.startswith(year_month)]
        delivered = [e for e in month_entries if e.delivery.startswith("email:")]
        result.delivered_reports = len(delivered)

        # Criterion 1: zero gate blockers in any DELIVERED report
        blockers = [e for e in delivered if not e.gate_passed]
        result.blocker_count = len(blockers)
        if blockers:
            result.failed_criteria.append(
                f"C1: {len(blockers)} delivered report(s) shipped with gate blockers — "
                f"report_id(s): {', '.join(b.report_id for b in blockers[:3])}"
            )

        # Criterion 2: zero client corrections logged for any report from this month
        delivered_ids = {e.report_id for e in delivered}
        month_corrections = [
            c for c in self.corrections.for_client(client_name)
            if c.report_id in delivered_ids
        ]
        result.corrections_count = len(month_corrections)
        if month_corrections:
            result.failed_criteria.append(
                f"C2: {len(month_corrections)} ClientCorrection record(s) logged — "
                f"report_id(s): {', '.join(c.report_id for c in month_corrections[:3])}"
            )

        # Criterion 3: zero schema drift blocking events
        drift_failures = [e for e in delivered if not e.schema_drift_clean]
        if drift_failures:
            result.failed_criteria.append(
                f"C3: {len(drift_failures)} report(s) ran with schema drift not clean"
            )

        # Criterion 4: deterministic pipeline — no late corrections, no hash divergence.
        # A late_correction entry means the original source data was wrong and the pipeline
        # was re-run after delivery. That is not a "clean" month regardless of whether the
        # corrected output is now correct.
        late_corrections = [e for e in month_entries if getattr(e, "late_correction", False)]
        if late_corrections:
            result.failed_criteria.append(
                f"C4: {len(late_corrections)} late_correction rerun(s) — source data was wrong "
                f"after original delivery: report_id(s) {', '.join(e.report_id for e in late_corrections[:3])}"
            )
        # Also check for non-determinism: same source hash, different Claude response.
        by_hash: dict[str, set[str]] = {}
        for e in month_entries:
            if not getattr(e, "late_correction", False):  # exclude corrections from this check
                by_hash.setdefault(e.source_data_hash, set()).add(e.response_hash)
        non_deterministic = {h: rs for h, rs in by_hash.items() if len(rs) > 1}
        if non_deterministic:
            result.failed_criteria.append(
                f"C4: {len(non_deterministic)} source_data_hash(es) produced multiple response_hashes — "
                "pipeline non-determinism"
            )

        # Criterion 5: at least one delivery happened
        if not delivered:
            result.failed_criteria.append("C5: no email delivery in month")

        # Criterion 6: golden signoff is complete — best-effort check via gate flags
        # (we don't have direct GoldenSuite access here; we check that no entry
        # flagged signoff as incomplete)
        signoff_breaks = [
            e for e in delivered
            if any(f.get("code") == "GOLDEN_SUITE_UNSIGNED" for f in e.gate_flags)
        ]
        if signoff_breaks:
            result.failed_criteria.append(
                f"C6: {len(signoff_breaks)} report(s) ran with incomplete golden signoff"
            )

        # Criterion 7: no FALLBACK_COMMENTARY in delivered entries
        fallback_shipped = [
            e for e in delivered
            if any(f.get("code") == "FALLBACK_COMMENTARY" for f in e.gate_flags)
        ]
        if fallback_shipped:
            result.failed_criteria.append(
                f"C7: {len(fallback_shipped)} report(s) shipped with FALLBACK_COMMENTARY — "
                "API was unavailable, fallback should have been blocked"
            )

        result.is_clean = not result.failed_criteria
        return result

    def rolling_window(self, client_name: str, anchor_date: date | None = None) -> tuple[bool, list[CleanMonthResult]]:
        """Check the most recent WINDOW_MONTHS months. Returns (eligible, [per-month results])."""
        anchor = anchor_date or date.today()
        months: list[str] = []
        y, m = anchor.year, anchor.month
        # Move one month back to exclude the in-progress current month
        for _ in range(self.WINDOW_MONTHS):
            m -= 1
            if m == 0:
                m = 12
                y -= 1
            months.append(f"{y:04d}-{m:02d}")
        months.reverse()

        results = [self.check_month(client_name, ym) for ym in months]
        eligible = all(r.is_clean for r in results)
        return eligible, results

    def report(self, client_name: str, anchor_date: date | None = None) -> str:
        eligible, results = self.rolling_window(client_name, anchor_date)
        lines = [
            f"Client: {client_name}",
            f"Audit window: {results[0].year_month} → {results[-1].year_month}",
            "",
            f"{'Month':<10} {'Clean?':<8} {'Reports':>8} {'Failures'}",
            "-" * 60,
        ]
        for r in results:
            icon = "✓" if r.is_clean else "✗"
            failure = r.failed_criteria[0] if r.failed_criteria else ""
            lines.append(f"{r.year_month:<10} {icon:<8} {r.delivered_reports:>8}  {failure[:60]}")
        lines.append("")
        lines.append(f"{self.WINDOW_MONTHS}-month rolling window: {'CLEAN ✓' if eligible else 'NOT CLEAN ✗'}")
        lines.append(
            f"Current tier eligibility: "
            f"{'Spot-Check (€390/mo) available' if eligible else 'Reviewed tier required (€690/mo)'}"
        )
        return "\n".join(lines)
