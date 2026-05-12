"""Shared types for the ingestion layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class RawTable:
    name: str
    df: pd.DataFrame
    source_file: Path
    sheet_or_segment: str = ""
    row_count: int = field(init=False)
    col_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.row_count = len(self.df)
        self.col_count = len(self.df.columns)

    def __repr__(self) -> str:
        return f"RawTable({self.name!r}, {self.row_count}r×{self.col_count}c)"


@dataclass
class IngestionResult:
    tables: list[RawTable]
    source_path: Path
    warnings: list[str] = field(default_factory=list)

    @property
    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]

    def get(self, name: str) -> RawTable | None:
        for t in self.tables:
            if t.name == name:
                return t
        return None
