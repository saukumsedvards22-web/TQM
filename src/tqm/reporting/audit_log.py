"""Immutable audit log for every report run.

report_id is a composite identity, not a pure content hash:
  sha256( client_name | period | source_data_hash | extraction_ts_utc | late_correction )

This means:
  - Two runs on the same data for the same period produce the same report_id
    (deterministic replay for dispute resolution).
  - A re-run on *corrected* data produces a new report_id because the source
    hash differs. The new entry carries supersedes=<original_report_id> so the
    correction chain is auditable without overwriting the original.
  - late_correction=True in the id key signals the entry was generated after the
    original delivery date — audit reviewers can filter these separately.

Retained 12+ months. Append-only JSONL — never modify existing entries.

When a client disputes a number four months later:
  1. Look up report_id by client+period (returns most recent entry by default).
  2. Retrieve kpi_snapshot — these are the exact numbers the pipeline saw.
  3. Retrieve response_hash — verify Claude's response hasn't been altered.
  4. Re-run gate against stored kpi_snapshot to reproduce the review decision.
  5. If supersedes is set, walk the chain to see the original and any corrections.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _df_hash(df: pd.DataFrame) -> str:
    """Stable hash of DataFrame contents regardless of index."""
    canonical = df.sort_index(axis=1).to_csv(index=False)
    return _sha256(canonical)


@dataclass
class AuditEntry:
    report_id: str
    client_name: str
    period: str
    generated_at: str
    source_data_hash: str
    prompt_hash: str
    response_hash: str
    kpi_snapshot: dict          # exact deltas used
    gate_passed: bool
    gate_flags: list[dict]      # serialised ReviewFlag list
    delivery: str               # "email:ceo@x.lv", "dry_run", "held:pending/file.json"
    cost_eur: float
    model: str
    date_column_used: str
    schema_drift_clean: bool
    volatility_thresholds: dict  # kpi -> threshold_pct used
    late_correction: bool = False  # re-run on corrected source data after original delivery
    supersedes: str | None = None  # report_id of the entry this one replaces

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "client_name": self.client_name,
            "period": self.period,
            "generated_at": self.generated_at,
            "source_data_hash": self.source_data_hash,
            "prompt_hash": self.prompt_hash,
            "response_hash": self.response_hash,
            "kpi_snapshot": self.kpi_snapshot,
            "gate_passed": self.gate_passed,
            "gate_flags": self.gate_flags,
            "delivery": self.delivery,
            "cost_eur": self.cost_eur,
            "model": self.model,
            "date_column_used": self.date_column_used,
            "schema_drift_clean": self.schema_drift_clean,
            "volatility_thresholds": self.volatility_thresholds,
            "late_correction": self.late_correction,
            "supersedes": self.supersedes,
        }


class AuditLog:
    """Append-only audit log. One file per year per client."""

    def __init__(self, log_dir: Path = Path(".tqm_audit")) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def record(
        self,
        client_name: str,
        period: str,
        source_df: pd.DataFrame,
        prompt: str,
        raw_response: str,
        kpi_snapshot: dict,
        gate_result: Any,                   # ReviewResult
        delivery: str,
        cost_eur: float,
        model: str,
        date_column_used: str,
        schema_drift_clean: bool,
        volatility_thresholds: dict,
        late_correction: bool = False,
        supersedes: str | None = None,
    ) -> AuditEntry:
        report_id = self._make_id(client_name, period, source_df, late_correction)

        entry = AuditEntry(
            report_id=report_id,
            client_name=client_name,
            period=period,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source_data_hash=_df_hash(source_df),
            prompt_hash=_sha256(prompt),
            response_hash=_sha256(raw_response),
            kpi_snapshot=kpi_snapshot,
            gate_passed=gate_result.passed,
            gate_flags=[
                {"severity": f.severity, "code": f.code, "message": f.message}
                for f in gate_result.flags
            ],
            delivery=delivery,
            cost_eur=round(cost_eur, 6),
            model=model,
            date_column_used=date_column_used,
            schema_drift_clean=schema_drift_clean,
            volatility_thresholds=volatility_thresholds,
            late_correction=late_correction,
            supersedes=supersedes,
        )

        self._append(client_name, period, entry)
        log.info("Audit entry written: report_id=%s", report_id)
        return entry

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def lookup(
        self,
        client_name: str,
        period: str,
        *,
        include_corrections: bool = False,
    ) -> AuditEntry | None:
        """Return the most recent audit entry for client + period.

        By default returns the latest entry (which may be a late correction).
        Pass include_corrections=False and check .late_correction on the result
        if you need to distinguish the original from re-runs.
        """
        year = period[:4] if len(period) >= 4 else datetime.now().strftime("%Y")
        path = self._path(client_name, year)
        if not path.exists():
            return None
        matches: list[AuditEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                if data.get("client_name") == client_name and data.get("period") == period:
                    matches.append(AuditEntry(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        if not matches:
            return None
        # Return the last-written entry (chronological order in append-only log)
        return matches[-1]

    def lookup_original(self, client_name: str, period: str) -> AuditEntry | None:
        """Return the original (non-corrected) entry for client + period."""
        year = period[:4] if len(period) >= 4 else datetime.now().strftime("%Y")
        path = self._path(client_name, year)
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                if (data.get("client_name") == client_name
                        and data.get("period") == period
                        and not data.get("late_correction", False)):
                    return AuditEntry(**data)
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def history(self, client_name: str) -> list[AuditEntry]:
        """All audit entries for a client, all years, chronological."""
        entries: list[AuditEntry] = []
        safe = client_name.lower().replace(" ", "_")
        for path in sorted(self.log_dir.glob(f"{safe}_*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    data = json.loads(line)
                    entries.append(AuditEntry(**data))
                except (json.JSONDecodeError, TypeError):
                    continue
        return entries

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_id(
        self,
        client_name: str,
        period: str,
        df: pd.DataFrame,
        late_correction: bool = False,
    ) -> str:
        correction_flag = "corrected" if late_correction else "original"
        key = f"{client_name}|{period}|{_df_hash(df)}|{correction_flag}"
        return _sha256(key)

    def _path(self, client_name: str, year: str) -> Path:
        safe = client_name.lower().replace(" ", "_").replace("/", "_")
        return self.log_dir / f"{safe}_{year}.jsonl"

    def _append(self, client_name: str, period: str, entry: AuditEntry) -> None:
        year = period[:4] if len(period) >= 4 else datetime.now().strftime("%Y")
        path = self._path(client_name, year)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
