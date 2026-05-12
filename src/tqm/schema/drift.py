"""Schema drift detector — compare incoming data against a known-good schema.

Persists a schema fingerprint after first successful run.
On every subsequent run, checks for:
  - New columns (may be new data, may be a renamed column)
  - Missing columns (almost certainly a problem — silent data loss)
  - Type changes (numeric → text = formatting change in the export)
  - Cardinality explosions (dimension column that suddenly has 10x more values)

All drift is logged. Missing columns and type changes are blocking by default.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

log = logging.getLogger(__name__)

_SCHEMA_FILE = ".tqm_schema_{client}.json"


@dataclass
class DriftEvent:
    severity: Literal["block", "warn"]
    code: str
    column: str
    message: str
    previous: str = ""
    current: str = ""


@dataclass
class DriftReport:
    client_name: str
    events: list[DriftEvent] = field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        return any(e.severity == "block" for e in self.events)

    @property
    def is_clean(self) -> bool:
        return len(self.events) == 0

    def summary(self) -> str:
        if self.is_clean:
            return "Schema unchanged — no drift detected."
        lines = [f"Schema drift detected for {self.client_name}:"]
        for e in self.events:
            icon = "🔴" if e.severity == "block" else "🟡"
            lines.append(f"  {icon} [{e.code}] {e.column}: {e.message}")
        return "\n".join(lines)


class SchemaDriftDetector:
    """Compare a DataFrame's schema to a persisted fingerprint."""

    def __init__(self, schema_dir: Path = Path(".tqm_schemas")) -> None:
        self.schema_dir = schema_dir
        self.schema_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, df: pd.DataFrame, client_name: str) -> DriftReport:
        """Compare df against stored schema. Returns DriftReport."""
        current = self._fingerprint(df)
        path = self._path(client_name)

        if not path.exists():
            # First run — persist and return clean
            self._save(current, path)
            log.info("Schema fingerprint saved for %s (%d columns)", client_name, len(current["columns"]))
            return DriftReport(client_name=client_name)

        previous = json.loads(path.read_text(encoding="utf-8"))
        report = self._compare(previous, current, client_name)

        if report.is_clean:
            log.info("Schema check passed for %s", client_name)
        else:
            log.warning(report.summary())

        return report

    def update(self, df: pd.DataFrame, client_name: str) -> None:
        """Overwrite the stored fingerprint after a reviewed/approved run."""
        self._save(self._fingerprint(df), self._path(client_name))
        log.info("Schema fingerprint updated for %s", client_name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fingerprint(self, df: pd.DataFrame) -> dict:
        columns: dict[str, dict] = {}
        for col in df.columns:
            series = df[col]
            columns[col] = {
                "dtype": str(series.dtype),
                "cardinality": int(series.nunique()),
                "null_rate": float(series.isna().mean()),
                "is_numeric": bool(pd.api.types.is_numeric_dtype(series)),
                "is_datetime": bool(pd.api.types.is_datetime64_any_dtype(series)),
            }
        return {"columns": columns, "row_count": len(df)}

    def _compare(self, previous: dict, current: dict, client_name: str) -> DriftReport:
        report = DriftReport(client_name=client_name)
        prev_cols: dict = previous.get("columns", {})
        cur_cols: dict = current.get("columns", {})

        prev_names = set(prev_cols)
        cur_names = set(cur_cols)

        # Missing columns — blocking
        for col in prev_names - cur_names:
            report.events.append(DriftEvent(
                severity="block",
                code="COLUMN_MISSING",
                column=col,
                message="Column present last month is absent — data may be lost or renamed",
                previous=str(prev_cols[col]),
                current="(absent)",
            ))

        # New columns — warning only
        for col in cur_names - prev_names:
            report.events.append(DriftEvent(
                severity="warn",
                code="COLUMN_ADDED",
                column=col,
                message="New column not seen last month — verify it's intentional",
                previous="(absent)",
                current=str(cur_cols[col]),
            ))

        # Type changes — blocking
        for col in prev_names & cur_names:
            p = prev_cols[col]
            c = cur_cols[col]

            if p["is_numeric"] and not c["is_numeric"]:
                report.events.append(DriftEvent(
                    severity="block",
                    code="TYPE_REGRESSION",
                    column=col,
                    message="Column was numeric, now text — SAP export format may have changed",
                    previous=p["dtype"],
                    current=c["dtype"],
                ))
            elif p["is_datetime"] and not c["is_datetime"]:
                report.events.append(DriftEvent(
                    severity="block",
                    code="DATE_REGRESSION",
                    column=col,
                    message="Date column lost date type — time-intelligence measures will be wrong",
                    previous=p["dtype"],
                    current=c["dtype"],
                ))

            # Cardinality explosion on a dimension (>5x)
            if not c["is_numeric"] and p["cardinality"] > 0:
                ratio = c["cardinality"] / p["cardinality"]
                if ratio > 5:
                    report.events.append(DriftEvent(
                        severity="warn",
                        code="CARDINALITY_EXPLOSION",
                        column=col,
                        message=f"Cardinality increased {ratio:.0f}x ({p['cardinality']} → {c['cardinality']}) — possible free-text field or data quality issue",
                        previous=str(p["cardinality"]),
                        current=str(c["cardinality"]),
                    ))

        return report

    def _path(self, client_name: str) -> Path:
        safe = client_name.lower().replace(" ", "_").replace("/", "_")
        return self.schema_dir / f"{safe}_schema.json"

    def _save(self, fingerprint: dict, path: Path) -> None:
        path.write_text(json.dumps(fingerprint, indent=2, ensure_ascii=False), encoding="utf-8")
