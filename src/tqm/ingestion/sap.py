"""SAP flat-file ingestion.

Handles the most common SAP export formats:
- ALV grid exports (.txt / .csv with | or ; separator)
- FBL3N / FBL5N / MB51 style column-padded text reports
- Standard CSV downloads from SAP GUI
- .XLSX exports from SAP (delegated to ExcelIngester)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .base import IngestionResult, RawTable
from .excel import ExcelIngester, _coerce_types, _slugify

# SAP report header lines to skip
_SAP_HEADER_PATTERNS = [
    re.compile(r"^\s*(report|sap|created by|selection criteria|period|company code)", re.I),
    re.compile(r"^[-=|]+$"),
]

_SEPARATORS = ["|", "\t", ";", ","]


class SAPIngester:
    """Parse SAP flat-file exports into RawTable objects."""

    def __init__(self) -> None:
        self._excel = ExcelIngester()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, path: Path | str, table_name: str | None = None) -> IngestionResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        suffix = path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return self._excel.ingest(path)

        name = table_name or _slugify(path.stem)
        warnings: list[str] = []

        df, warn = self._parse_text(path)
        warnings.extend(warn)

        if df is None or df.empty:
            return IngestionResult(tables=[], source_path=path, warnings=warnings + ["No data found"])

        df = _coerce_types(df, warnings)
        table = RawTable(name=name, df=df, source_file=path, sheet_or_segment="sap_export")
        return IngestionResult(tables=[table], source_path=path, warnings=warnings)

    def ingest_directory(self, directory: Path | str) -> IngestionResult:
        directory = Path(directory)
        all_tables: list[RawTable] = []
        all_warnings: list[str] = []

        patterns = ["**/*.txt", "**/*.csv", "**/*.xlsx", "**/*.xls"]
        seen: set[Path] = set()
        for pattern in patterns:
            for file in sorted(directory.glob(pattern)):
                if file in seen:
                    continue
                seen.add(file)
                result = self.ingest(file)
                all_tables.extend(result.tables)
                all_warnings.extend(result.warnings)

        return IngestionResult(tables=all_tables, source_path=directory, warnings=all_warnings)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_text(self, path: Path) -> tuple[pd.DataFrame | None, list[str]]:
        warnings: list[str] = []
        lines = self._read_lines(path)
        if not lines:
            return None, warnings

        # Detect if it's pipe-aligned (ALV) or delimited
        sample = "\n".join(lines[:20])
        if sample.count("|") > sample.count(";") * 2:
            df, w = self._parse_pipe_delimited(lines)
        else:
            sep = self._detect_separator(lines)
            df, w = self._parse_csv_style(lines, sep)

        warnings.extend(w)
        return df, warnings

    def _read_lines(self, path: Path) -> list[str]:
        for enc in ("utf-8-sig", "latin-1", "cp1252"):
            try:
                return path.read_text(encoding=enc).splitlines()
            except UnicodeDecodeError:
                continue
        return []

    def _parse_pipe_delimited(self, lines: list[str]) -> tuple[pd.DataFrame | None, list[str]]:
        warnings: list[str] = []
        data_lines: list[str] = []

        for line in lines:
            if any(p.match(line) for p in _SAP_HEADER_PATTERNS):
                continue
            # Strip outer pipes, keep inner ones
            stripped = line.strip().strip("|")
            if not stripped:
                continue
            data_lines.append(stripped)

        if len(data_lines) < 2:
            return None, warnings

        header = [_slugify(c.strip()) for c in data_lines[0].split("|")]
        rows = []
        for line in data_lines[1:]:
            cells = [c.strip() for c in line.split("|")]
            if len(cells) == len(header):
                rows.append(cells)
            elif cells:
                # Pad or truncate
                padded = (cells + [""] * len(header))[: len(header)]
                rows.append(padded)

        if not rows:
            return None, warnings

        df = pd.DataFrame(rows, columns=header)
        df = df.replace("", pd.NA).dropna(how="all").dropna(axis=1, how="all")
        return df, warnings

    def _detect_separator(self, lines: list[str]) -> str:
        sample = "\n".join(lines[:10])
        counts = {sep: sample.count(sep) for sep in _SEPARATORS}
        return max(counts, key=lambda s: counts[s])

    def _parse_csv_style(
        self, lines: list[str], sep: str
    ) -> tuple[pd.DataFrame | None, list[str]]:
        warnings: list[str] = []
        data_lines = [l for l in lines if not any(p.match(l) for p in _SAP_HEADER_PATTERNS)]

        if len(data_lines) < 2:
            return None, warnings

        from io import StringIO

        text = "\n".join(data_lines)
        try:
            df = pd.read_csv(StringIO(text), sep=sep, dtype=str, on_bad_lines="skip")
            df.columns = [_slugify(str(c)) for c in df.columns]
            df = df.dropna(how="all").dropna(axis=1, how="all")
            return df, warnings
        except Exception as exc:
            warnings.append(f"CSV parse error: {exc}")
            return None, warnings
