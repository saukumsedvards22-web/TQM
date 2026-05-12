"""Immutable audit log for every report run.

Keyed by a deterministic report_id (sha256 of client+period+source hash).
Retained 12+ months. Append-only JSONL — never modify existing entries.

Each entry captures:
  - report_id        — deterministic, reproducible
  - client_name / period
  - source_data_hash — sha256 of the ingested DataFrame rows (not the file,
                       which may be renamed/re-sent; the actual data content)
  - prompt_hash      — sha256 of the user message sent to Claude
  - response_hash    — sha256 of Claude's raw response
  - kpi_snapshot     — the exact KPI deltas used for comparison
  - gate_result      — pass/fail + all flags
  - delivery         — where it was sent and when, or "held" / "dry_run"
  - cost_eur         — API cost for this run

When a client disputes a number four months later:
  1. Look up report_id by client+period.
  2. Retrieve kpi_snapshot — these are the exact numbers the pipeline saw.
  3. Retrieve response_hash — verify Claude's response hasn't been altered.
  4. Re-run gate against stored kpi_snapshot to reproduce the review decision.
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
    ) -> AuditEntry:
        report_id = self._make_id(client_name, period, source_df)

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
        )

        self._append(client_name, period, entry)
        log.info("Audit entry written: report_id=%s", report_id)
        return entry

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def lookup(self, client_name: str, period: str) -> AuditEntry | None:
        """Find an audit entry by client + period."""
        year = period[:4] if len(period) >= 4 else datetime.now().strftime("%Y")
        path = self._path(client_name, year)
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                if data.get("client_name") == client_name and data.get("period") == period:
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

    def _make_id(self, client_name: str, period: str, df: pd.DataFrame) -> str:
        key = f"{client_name}|{period}|{_df_hash(df)}"
        return _sha256(key)

    def _path(self, client_name: str, year: str) -> Path:
        safe = client_name.lower().replace(" ", "_").replace("/", "_")
        return self.log_dir / f"{safe}_{year}.jsonl"

    def _append(self, client_name: str, period: str, entry: AuditEntry) -> None:
        year = period[:4] if len(period) >= 4 else datetime.now().strftime("%Y")
        path = self._path(client_name, year)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
