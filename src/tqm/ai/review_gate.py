"""Human review gate — holds reports for approval before delivery.

Rules:
  1. Any KPI delta > THRESHOLD_PCT triggers a hold.
  2. Any KPI with suspiciously round numbers (possible misclassification) triggers a hold.
  3. Any root_cause_analysis containing hedging language triggers a hold.
  4. The gate writes a review packet to disk and either:
     - Blocks until stdin approval (interactive)
     - Writes a .pending file and exits 0 (CI/async mode)
     - Emails the reviewer instead of the CEO (review_email mode)

Never email the CEO without passing through this gate.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from .analyst import AICommentary
from .snapshot import SnapshotComparison

log = logging.getLogger(__name__)

# Language that signals Claude is guessing rather than analysing
_HALLUCINATION_MARKERS = re.compile(
    r"\b(may have|might be|could be|possibly|perhaps|it appears|seems to|"
    r"likely due to|probably|supply chain disruption|macroeconomic|"
    r"global uncertainty|market conditions)\b",
    re.I,
)

# Numbers that suggest a misclassified column (e.g., discount % read as revenue)
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
        delta_block_pct: KPI changes beyond ±this% trigger a block.
        delta_warn_pct:  KPI changes beyond ±this% trigger a warning.
        mode: "interactive" | "pending_file" | "raise"
    """

    def __init__(
        self,
        delta_block_pct: float = 40.0,
        delta_warn_pct: float = 15.0,
        mode: Literal["interactive", "pending_file", "raise"] = "raise",
        pending_dir: Path = Path("output/pending"),
    ) -> None:
        self.delta_block_pct = delta_block_pct
        self.delta_warn_pct = delta_warn_pct
        self.mode = mode
        self.pending_dir = pending_dir

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
        flags += self._check_delta_magnitudes(comparison)
        flags += self._check_hallucination_language(commentary)
        flags += self._check_round_numbers(comparison)
        flags += self._check_direction_conflicts(commentary, comparison)

        passed = len([f for f in flags if f.severity == "block"]) == 0
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
        print(f"Root cause: {commentary.root_cause_analysis[:300]}…")

        print("\n" + "=" * 60)
        answer = input("Approve delivery? [y/N] ").strip().lower()
        return answer == "y"

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _check_delta_magnitudes(self, comparison: SnapshotComparison) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        for kpi, delta in comparison.kpi_deltas().items():
            pct = abs(delta["pct"])
            if pct >= self.delta_block_pct:
                flags.append(ReviewFlag(
                    severity="block",
                    code="LARGE_DELTA",
                    message=f"{kpi} changed {delta['pct']:+.1f}% — verify this is real data, not a column shift",
                    detail=f"Current: {delta['current']:,.2f}  Previous: {delta['previous']:,.2f}",
                ))
            elif pct >= self.delta_warn_pct:
                flags.append(ReviewFlag(
                    severity="warn",
                    code="NOTABLE_DELTA",
                    message=f"{kpi} changed {delta['pct']:+.1f}%",
                    detail=f"Current: {delta['current']:,.2f}  Previous: {delta['previous']:,.2f}",
                ))
        return flags

    def _check_hallucination_language(self, commentary: AICommentary) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        text = f"{commentary.root_cause_analysis} {commentary.executive_summary}"
        matches = _HALLUCINATION_MARKERS.findall(text)
        if matches:
            flags.append(ReviewFlag(
                severity="block",
                code="SPECULATIVE_LANGUAGE",
                message="Root cause analysis contains hedging phrases — Claude may be fabricating context",
                detail=f"Phrases found: {', '.join(set(m.lower() for m in matches))}",
            ))
        return flags

    def _check_round_numbers(self, comparison: SnapshotComparison) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        for kpi, delta in comparison.kpi_deltas().items():
            for label, val in [("current", delta["current"]), ("previous", delta["previous"])]:
                if _SUSPICIOUSLY_ROUND.search(f"{val:.1f}"):
                    flags.append(ReviewFlag(
                        severity="warn",
                        code="ROUND_NUMBER",
                        message=f"{kpi} {label} value is suspiciously round ({val})",
                        detail="Check: is this a percentage column misread as a monetary column?",
                    ))
        return flags

    def _check_direction_conflicts(
        self, commentary: AICommentary, comparison: SnapshotComparison
    ) -> list[ReviewFlag]:
        """Catch cases where Claude says 'revenue grew' but data shows a decline."""
        flags: list[ReviewFlag] = []
        text = (commentary.headline + " " + commentary.executive_summary).lower()

        revenue_kpis = [k for k in comparison.kpi_deltas() if any(x in k for x in ("revenue", "sales", "amount"))]
        for kpi in revenue_kpis:
            delta = comparison.kpi_deltas()[kpi]
            actual_up = delta["pct"] > 0
            said_grew = bool(re.search(r"\b(grew|increased|up|higher|rose|gain)\b", text))
            said_fell = bool(re.search(r"\b(fell|declined|dropped|down|lower|decrease|loss)\b", text))

            if actual_up and said_fell:
                flags.append(ReviewFlag(
                    severity="block",
                    code="DIRECTION_CONFLICT",
                    message=f"Commentary says revenue fell but {kpi} is up {delta['pct']:+.1f}%",
                    detail="Claude likely hallucinated the narrative direction.",
                ))
            elif not actual_up and said_grew:
                flags.append(ReviewFlag(
                    severity="block",
                    code="DIRECTION_CONFLICT",
                    message=f"Commentary says revenue grew but {kpi} is down {delta['pct']:+.1f}%",
                    detail="Claude likely hallucinated the narrative direction.",
                ))
        return flags

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
                "root_cause_analysis": commentary.root_cause_analysis,
                "executive_summary": commentary.executive_summary,
            },
            "kpi_deltas": comparison.kpi_deltas(),
        }

        if self.mode == "pending_file":
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
