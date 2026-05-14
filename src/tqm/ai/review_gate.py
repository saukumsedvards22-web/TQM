"""Human review gate — holds reports for approval before delivery.

Checks (in order of severity):
  1. Row-count guard (FM-12): block when current < 70% of previous rows
  2. Period-length guard (FM-13): warn when coverage differs by ≥2 days
  3. Per-KPI volatility-based delta threshold (not fixed %)
  4. Structured KeyFinding validation (FM-09 family)
  5. Number reconciliation — every figure in prose matched against source data
  6. Citation enforcement — root_cause_analysis must have ≥1 grounded claim
  7. Direction conflict — sign of narrative must match sign of data
  8. Round-number smell — possible column misclassification
  9. No fallback commentary reaching delivery

Never email the CEO without passing through this gate.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .analyst import AICommentary
from .reconciler import NumberReconciler
from .snapshot import SnapshotComparison

if TYPE_CHECKING:
    from .volatility import VolatilityProfile

log = logging.getLogger(__name__)

_SUSPICIOUSLY_ROUND = re.compile(r"\b(100\.0|1000\.0|10000\.0|0\.0)\b")


@dataclass
class ReviewFlag:
    severity: Literal["block", "warn"]
    code: str
    message: str
    detail: str = ""


@dataclass
class ReviewResult:
    passed: bool
    flags: list[ReviewFlag] = field(default_factory=list)
    reviewed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def blockers(self) -> list[ReviewFlag]:
        return [f for f in self.flags if f.severity == "block"]

    @property
    def warnings(self) -> list[ReviewFlag]:
        return [f for f in self.flags if f.severity == "warn"]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reviewed_at": self.reviewed_at,
            "blockers": [{"code": f.code, "message": f.message, "detail": f.detail} for f in self.blockers],
            "warnings": [{"code": f.code, "message": f.message, "detail": f.detail} for f in self.warnings],
        }


class ReviewGate:
    """Automated pre-delivery review gate.

    Args:
        volatility_profile: Per-KPI thresholds from VolatilityTracker.
                            If None, falls back to static_fallback_pct.
        static_fallback_pct: Conservative threshold used when no history exists.
        mode: "interactive" | "pending_file" | "raise"
    """

    def __init__(
        self,
        volatility_profile: "VolatilityProfile | None" = None,
        static_fallback_pct: float = 15.0,
        flat_threshold_pct: float = 3.0,    # |pct| below this → "flat"; configurable per client
        mode: Literal["interactive", "pending_file", "raise"] = "raise",
        pending_dir: Path = Path("output/pending"),
        synonym_table: "object | None" = None,    # SynonymTable; deferred import
        # kept for backward-compat with CLI — ignored when profile present
        delta_block_pct: float | None = None,
    ) -> None:
        self.volatility_profile = volatility_profile
        self.static_fallback_pct = static_fallback_pct
        self.flat_threshold_pct = flat_threshold_pct
        self._synonym_table = synonym_table
        if delta_block_pct is not None:
            self.static_fallback_pct = delta_block_pct
        self.mode = mode
        self.pending_dir = pending_dir
        self._reconciler = NumberReconciler()

    def _direction_from_pct(self, pct: float) -> str:
        if abs(pct) < self.flat_threshold_pct:
            return "flat"
        return "up" if pct > 0 else "down"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        commentary: AICommentary,
        comparison: SnapshotComparison,
        client_name: str,
    ) -> ReviewResult:
        """Run all checks. Returns ReviewResult — never raises."""
        flags: list[ReviewFlag] = []
        flags += self._check_row_count(comparison)
        flags += self._check_period_length(comparison)
        flags += self._check_delta_magnitudes(comparison)
        flags += self._check_key_findings(commentary, comparison)
        flags += self._check_number_reconciliation(commentary, comparison)
        flags += self._check_citations(commentary)
        flags += self._check_direction_conflicts(commentary, comparison)
        flags += self._check_round_numbers(comparison)
        flags += self._check_fallback_marker(commentary)

        passed = not any(f.severity == "block" for f in flags)
        result = ReviewResult(passed=passed, flags=flags)

        if not passed:
            self._handle_failure(result, commentary, comparison, client_name)

        return result

    def require_human_approval(
        self,
        result: ReviewResult,
        commentary: AICommentary,
        comparison: SnapshotComparison,
        client_name: str,
    ) -> bool:
        """Interactive stdin approval. Returns True if human approves."""
        if result.passed and not result.warnings:
            return True

        print("\n" + "=" * 60)
        print(f"REVIEW REQUIRED — {client_name} / {comparison.period_label}")
        print("=" * 60)

        for flag in result.flags:
            icon = "🔴 BLOCK" if flag.severity == "block" else "🟡 WARN "
            print(f"\n{icon}  [{flag.code}] {flag.message}")
            if flag.detail:
                print(f"         {flag.detail}")

        print("\n--- AI Commentary ---")
        print(f"Headline: {commentary.headline}")
        rca = commentary.root_cause_analysis
        n_claims = rca.citation_count()
        print(f"Root cause: {n_claims} cited claim(s), {len(rca.unsupported_factors)} unsupported factor(s)")

        print("\n" + "=" * 60)
        answer = input("Approve delivery? [y/N] ").strip().lower()
        return answer == "y"

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _check_row_count(self, comparison: SnapshotComparison) -> list[ReviewFlag]:
        """Block on truncated source data — current row count <70% of previous.

        Closes FM-12. A partial SAP export can produce KPIs that look internally
        consistent (revenue down 30%, qty down 30%, margin% flat) and pass every
        downstream check. The only reliable signal is the row count itself.
        """
        cur = comparison.current.row_count
        prev = comparison.previous.row_count
        flags: list[ReviewFlag] = []

        if prev <= 0 or cur <= 0:
            return flags  # cannot judge without both sides

        ratio = cur / prev
        if ratio < 0.70:
            flags.append(ReviewFlag(
                severity="block",
                code="ROW_COUNT_DROP",
                message=(
                    f"Current row count ({cur:,}) is {ratio:.0%} of previous ({prev:,}) — "
                    "likely truncated source file"
                ),
                detail="Verify the export completed. Check file size against history before re-running.",
            ))
        elif ratio < 0.85:
            flags.append(ReviewFlag(
                severity="warn",
                code="ROW_COUNT_LOW",
                message=f"Current row count ({cur:,}) is {ratio:.0%} of previous ({prev:,})",
                detail="May be normal seasonal drop; confirm with the client.",
            ))
        elif ratio > 1.5:
            flags.append(ReviewFlag(
                severity="warn",
                code="ROW_COUNT_SPIKE",
                message=f"Current row count ({cur:,}) is {ratio:.0%} of previous ({prev:,})",
                detail="Possible duplicate ingestion or business-event spike — verify.",
            ))
        return flags

    def _check_period_length(self, comparison: SnapshotComparison) -> list[ReviewFlag]:
        """Warn when the two periods cover materially different numbers of days.

        Closes FM-13. A client who exports on the 30th gives you 30 days in
        most months and 31 in December. An extra day inflates revenue by
        ~3% — Claude will then confabulate a business reason. Flagging this
        forces an analyst to acknowledge the period-length effect.
        """
        cur_days = comparison.current.period_days
        prev_days = comparison.previous.period_days
        if cur_days <= 0 or prev_days <= 0:
            return []  # not computed (e.g. test fixture without dates)

        diff = abs(cur_days - prev_days)
        if diff >= 7:
            return [ReviewFlag(
                severity="block",
                code="PERIOD_LENGTH_MISMATCH",
                message=(
                    f"Period coverage differs by {diff} days "
                    f"(current={cur_days}, previous={prev_days})"
                ),
                detail="Likely partial-month extract. Resolve before comparison.",
            )]
        if diff >= 2:
            return [ReviewFlag(
                severity="warn",
                code="PERIOD_LENGTH_MISMATCH",
                message=(
                    f"Period coverage differs by {diff} days "
                    f"(current={cur_days}, previous={prev_days})"
                ),
                detail=(
                    f"~{(diff / max(prev_days, 1)) * 100:.1f}% of the delta may be a length effect, "
                    "not a business change. Analyst must acknowledge."
                ),
            )]
        return []

    def _check_delta_magnitudes(self, comparison: SnapshotComparison) -> list[ReviewFlag]:
        """Block on KPI changes beyond per-KPI volatility threshold."""
        flags: list[ReviewFlag] = []
        for kpi, delta in comparison.kpi_deltas.items():
            pct = abs(delta["pct"])

            if self.volatility_profile:
                t = self.volatility_profile.get_threshold(kpi)
                block_at = t.threshold_pct
                warn_at = block_at * 0.6
                method_note = f"threshold={block_at:.1f}% ({t.method}, n={t.history_count})"
            else:
                block_at = self.static_fallback_pct
                warn_at = block_at * 0.6
                method_note = f"threshold={block_at:.1f}% (static fallback — no history)"

            if pct >= block_at:
                flags.append(ReviewFlag(
                    severity="block",
                    code="ANOMALOUS_DELTA",
                    message=f"{kpi} changed {delta['pct']:+.1f}% — exceeds {method_note}",
                    detail=f"Current: {delta['current']:,.2f}  Previous: {delta['previous']:,.2f}",
                ))
            elif pct >= warn_at:
                flags.append(ReviewFlag(
                    severity="warn",
                    code="NOTABLE_DELTA",
                    message=f"{kpi} changed {delta['pct']:+.1f}% — above 60% of {method_note}",
                    detail=f"Current: {delta['current']:,.2f}  Previous: {delta['previous']:,.2f}",
                ))
        return flags

    def _check_key_findings(
        self, commentary: AICommentary, comparison: SnapshotComparison
    ) -> list[ReviewFlag]:
        """Validate structured KeyFindings — closes FM-09.

        For each finding:
          1. kpi_id must be a real key in comparison.kpi_deltas
          2. direction must match the sign of source pct
          3. magnitude_pct must match |source pct| within 2pp
          4. context must NOT mention any other KPI name (label transposition)
        """
        from .kpi_synonyms import SynonymTable
        synonym_table = getattr(self, "_synonym_table", None) or SynonymTable()

        flags: list[ReviewFlag] = []
        kpi_deltas = comparison.kpi_deltas
        known_kpis = set(kpi_deltas.keys())

        for i, finding in enumerate(commentary.key_findings):
            if not finding.kpi_id:
                flags.append(ReviewFlag(
                    severity="block",
                    code="MALFORMED_FINDING",
                    message=f"key_finding[{i}] has empty kpi_id — likely legacy prose format",
                    detail=f"Context: {finding.context[:80]}",
                ))
                continue

            if finding.kpi_id not in known_kpis:
                flags.append(ReviewFlag(
                    severity="block",
                    code="UNKNOWN_KPI",
                    message=f"key_finding[{i}] references kpi_id='{finding.kpi_id}' which is not in source data",
                    detail=f"Available KPIs: {sorted(known_kpis)}",
                ))
                continue

            source_pct = kpi_deltas[finding.kpi_id]["pct"]
            source_direction = self._direction_from_pct(source_pct)

            if finding.direction != source_direction:
                flags.append(ReviewFlag(
                    severity="block",
                    code="FINDING_DIRECTION_MISMATCH",
                    message=(
                        f"key_finding[{i}] for '{finding.kpi_id}' says '{finding.direction}' "
                        f"but source pct is {source_pct:+.1f}% (direction='{source_direction}')"
                    ),
                ))

            if finding.direction != "flat":
                deviation = abs(finding.magnitude_pct - abs(source_pct))
                if deviation > 2.0:
                    flags.append(ReviewFlag(
                        severity="block",
                        code="FINDING_MAGNITUDE_MISMATCH",
                        message=(
                            f"key_finding[{i}] for '{finding.kpi_id}' claims {finding.magnitude_pct:.1f}% "
                            f"but source is {abs(source_pct):.1f}% (delta {deviation:.1f}pp)"
                        ),
                    ))

            # Semantic leak check via synonym table (FM-09 belt-and-braces)
            if finding.context:
                leaked = synonym_table.find_leaks(
                    this_kpi_id=finding.kpi_id,
                    all_kpi_ids=known_kpis,
                    context=finding.context,
                )
                if leaked:
                    flags.append(ReviewFlag(
                        severity="block",
                        code="CONTEXT_KPI_LEAK",
                        message=(
                            f"key_finding[{i}] for '{finding.kpi_id}' mentions other KPI tokens in context: {leaked}"
                        ),
                        detail=f"Context: '{finding.context}' — possible label transposition (FM-09)",
                    ))

        if not commentary.key_findings:
            flags.append(ReviewFlag(
                severity="warn",
                code="NO_FINDINGS",
                message="key_findings is empty — report has no headline movements",
            ))

        return flags

    def _check_number_reconciliation(
        self, commentary: AICommentary, comparison: SnapshotComparison
    ) -> list[ReviewFlag]:
        """Extract every number from commentary prose and match against source KPIs."""
        # Only reconcile prose fields. key_findings are structured and
        # validated by _check_key_findings — reconciling them would
        # double-flag every legitimate magnitude.
        text = " ".join([commentary.headline, commentary.executive_summary])
        result = self._reconciler.reconcile(text, comparison)

        flags: list[ReviewFlag] = []
        for issue in result.issues:
            flags.append(ReviewFlag(
                severity=issue.severity,
                code=issue.code,
                message=issue.message,
                detail=f"Extracted: '{issue.extracted}'"
                + (f"  Source: {issue.source_value:.1f}" if issue.source_value is not None else ""),
            ))

        if result.numbers_checked > 0:
            log.info(
                "Number reconciliation: %d/%d verified, %d issue(s)",
                result.numbers_matched, result.numbers_checked, len(result.issues),
            )
        return flags

    def _check_citations(self, commentary: AICommentary) -> list[ReviewFlag]:
        """Require at least one cited, evidence-backed causal claim."""
        rca = commentary.root_cause_analysis
        flags: list[ReviewFlag] = []

        if rca.citation_count() == 0:
            flags.append(ReviewFlag(
                severity="block",
                code="NO_CITATIONS",
                message="root_cause_analysis has zero KPI-backed claims — all factors are unsupported",
                detail=(
                    f"{len(rca.unsupported_factors)} unsupported factor(s) present. "
                    "Claude could not ground causation in the data, or returned the old string format."
                ),
            ))
        elif rca.citation_count() < 2:
            flags.append(ReviewFlag(
                severity="warn",
                code="WEAK_CITATION",
                message=f"Only {rca.citation_count()} cited claim(s) — verify it's sufficient for the narrative",
            ))
        return flags

    def _check_direction_conflicts(
        self, commentary: AICommentary, comparison: SnapshotComparison
    ) -> list[ReviewFlag]:
        """Catch sign errors: commentary says grew, data shows decline (or vice versa)."""
        flags: list[ReviewFlag] = []
        text = (commentary.headline + " " + commentary.executive_summary).lower()

        revenue_kpis = [
            k for k in comparison.kpi_deltas
            if any(x in k for x in ("revenue", "sales", "amount"))
        ]
        for kpi in revenue_kpis:
            delta = comparison.kpi_deltas[kpi]
            actual_up = delta["pct"] > 0
            said_grew = bool(re.search(r"\b(grew|increased|up|higher|rose|gain)\b", text))
            said_fell = bool(re.search(r"\b(fell|declined|dropped|down|lower|decrease|loss)\b", text))

            # Only flag when ONE direction word appears unambiguously.
            # Mixed wording (e.g. "revenue rose; costs fell") is normal prose
            # and is now caught precisely by _check_key_findings per-KPI.
            if actual_up and said_fell and not said_grew:
                flags.append(ReviewFlag(
                    severity="block",
                    code="DIRECTION_CONFLICT",
                    message=f"Commentary says revenue fell but {kpi} is {delta['pct']:+.1f}%",
                    detail="Claude likely hallucinated the narrative direction.",
                ))
            elif not actual_up and said_grew and not said_fell:
                flags.append(ReviewFlag(
                    severity="block",
                    code="DIRECTION_CONFLICT",
                    message=f"Commentary says revenue grew but {kpi} is {delta['pct']:+.1f}%",
                    detail="Claude likely hallucinated the narrative direction.",
                ))
        return flags

    def _check_round_numbers(self, comparison: SnapshotComparison) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        for kpi, delta in comparison.kpi_deltas.items():
            for label, val in [("current", delta["current"]), ("previous", delta["previous"])]:
                if _SUSPICIOUSLY_ROUND.search(f"{val:.1f}"):
                    flags.append(ReviewFlag(
                        severity="warn",
                        code="ROUND_NUMBER",
                        message=f"{kpi} {label} is suspiciously round ({val})",
                        detail="Check: percentage column misread as monetary?",
                    ))
        return flags

    def _check_fallback_marker(self, commentary: AICommentary) -> list[ReviewFlag]:
        """Block delivery of the API-unavailable fallback commentary."""
        if "[AI UNAVAILABLE" in commentary.headline:
            return [ReviewFlag(
                severity="block",
                code="FALLBACK_COMMENTARY",
                message="Commentary is the API-unavailable fallback — do not deliver",
                detail="Anthropic API was unreachable during generation. Complete the narrative manually.",
            )]
        return []

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        result: ReviewResult,
        commentary: AICommentary,
        comparison: SnapshotComparison,
        client_name: str,
    ) -> None:
        packet = {
            "client": client_name,
            "period": comparison.period_label,
            "review": result.to_dict(),
            "commentary": {
                "headline": commentary.headline,
                "root_cause_claims": [
                    {"claim": c.claim, "kpi": c.evidence_kpi, "value": c.evidence_value}
                    for c in commentary.root_cause_analysis.claims
                ],
                "unsupported_factors": commentary.root_cause_analysis.unsupported_factors,
                "executive_summary": commentary.executive_summary,
            },
            "kpi_deltas": comparison.kpi_deltas,
        }

        if self.mode == "pending_file":
            if self.pending_dir is None:
                log.warning("pending_file mode but no pending_dir set — skipping file write")
                return
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{client_name.replace(' ', '_')}_{comparison.current.period}.pending.json"
            path = self.pending_dir / fname
            path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
            log.warning("Report held for review — see %s", path)

        elif self.mode == "raise":
            codes = ", ".join(f.code for f in result.blockers)
            raise ReviewBlockedError(
                f"Report blocked ({codes}) — human review required before delivery.\n"
                + "\n".join(f"  [{f.code}] {f.message}" for f in result.blockers)
            )

        elif self.mode == "interactive":
            pass  # caller drives require_human_approval()


class ReviewBlockedError(RuntimeError):
    """Raised when a report fails automated review in non-interactive mode."""
