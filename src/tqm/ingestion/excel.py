"""Excel workbook ingestion — handles .xlsx and .xls, multi-sheet, named ranges."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .base import IngestionResult, RawTable

# Sheets that are almost certainly metadata noise
_SKIP_SHEETS: frozenset[str] = frozenset({"cover", "readme", "instructions", "legend", "help"})

# Minimum populated cells to treat a sheet as data
_MIN_CELLS = 10


class ExcelIngester:
    """Parse one or more Excel files into RawTable objects.

    Handles:
    - Multiple sheets per workbook
    - Auto-detecting the header row (first row with ≥3 non-empty values)
    - Stripping trailing empty rows/columns
    - Basic type coercion (dates, numbers)
    """

    def __init__(self, skip_sheets: frozenset[str] = _SKIP_SHEETS, min_cells: int = _MIN_CELLS):
        self.skip_sheets = {s.lower() for s in skip_sheets}
        self.min_cells = min_cells

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, path: Path | str) -> IngestionResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        tables: list[RawTable] = []
        warnings: list[str] = []

        xl = pd.ExcelFile(path, engine=self._engine(path))
        for sheet in xl.sheet_names:
            if sheet.strip().lower() in self.skip_sheets:
                continue
            try:
                df, warn = self._read_sheet(xl, sheet, path)
                warnings.extend(warn)
                if df is not None:
                    name = _slugify(sheet)
                    tables.append(RawTable(name=name, df=df, source_file=path, sheet_or_segment=sheet))
            except Exception as exc:
                warnings.append(f"Sheet '{sheet}' in {path.name} skipped: {exc}")

        return IngestionResult(tables=tables, source_path=path, warnings=warnings)

    def ingest_directory(self, directory: Path | str, glob: str = "**/*.xlsx") -> IngestionResult:
        directory = Path(directory)
        all_tables: list[RawTable] = []
        all_warnings: list[str] = []

        for file in sorted(directory.glob(glob)):
            result = self.ingest(file)
            all_tables.extend(result.tables)
            all_warnings.extend(result.warnings)

        return IngestionResult(tables=all_tables, source_path=directory, warnings=all_warnings)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _engine(self, path: Path) -> str:
        return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"

    def _read_sheet(
        self, xl: pd.ExcelFile, sheet: str, path: Path
    ) -> tuple[pd.DataFrame | None, list[str]]:
        warnings: list[str] = []

        # Read raw without assuming header
        raw = xl.parse(sheet, header=None, dtype=str)
        raw = raw.dropna(how="all").dropna(axis=1, how="all")

        if raw.size < self.min_cells:
            return None, []

        header_row = self._detect_header(raw)
        df = xl.parse(sheet, header=header_row, dtype=object)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        df.columns = [_slugify(str(c)) for c in df.columns]

        # Remove unnamed trailing columns that openpyxl adds
        df = df.loc[:, ~df.columns.str.startswith("unnamed_")]

        if df.empty:
            return None, []

        df = _coerce_types(df, warnings)
        return df, warnings

    def _detect_header(self, raw: pd.DataFrame) -> int:
        """Find the first row index where ≥3 cells are non-empty strings."""
        for i, row in raw.iterrows():
            non_empty = row.dropna()
            if len(non_empty) >= 3:
                return int(i)  # type: ignore[arg-type]
        return 0


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\s\-/\\]+", "_", text)
    text = re.sub(r"[^\w]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "col"


def _coerce_types(df: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    for col in df.columns:
        series = df[col]
        # Try numeric first
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() / max(len(series), 1) > 0.7:
            df[col] = numeric
            continue
        # Try datetime
        try:
            dates = pd.to_datetime(series, dayfirst=True, errors="coerce")
            if dates.notna().sum() / max(len(series), 1) > 0.7:
                df[col] = dates
        except Exception:
            pass
    return df
