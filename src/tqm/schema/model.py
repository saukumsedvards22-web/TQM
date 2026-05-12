"""Dimensional model representation (star schema)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class ColumnRole(str, Enum):
    DATE = "date"
    NUMERIC_MEASURE = "numeric_measure"
    TEXT_DIMENSION = "text_dimension"
    ID_KEY = "id_key"
    IGNORE = "ignore"


@dataclass
class ModelColumn:
    name: str
    role: ColumnRole
    dtype: str
    cardinality: int
    sample_values: list[str] = field(default_factory=list)
    is_nullable: bool = False


@dataclass
class FactTable:
    name: str
    df: pd.DataFrame
    measures: list[ModelColumn]
    date_columns: list[ModelColumn]
    dimension_columns: list[ModelColumn]
    all_columns: list[ModelColumn]

    @property
    def measure_names(self) -> list[str]:
        return [m.name for m in self.measures]

    @property
    def date_column_names(self) -> list[str]:
        return [d.name for d in self.date_columns]


@dataclass
class DimTable:
    name: str
    df: pd.DataFrame
    key_column: str
    label_cols: list[str]


@dataclass
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "many_to_one"


@dataclass
class DimensionalModel:
    fact: FactTable
    dims: list[DimTable] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Fact table: {self.fact.name} ({len(self.fact.df):,} rows)",
            f"  Measures:   {', '.join(self.fact.measure_names) or 'none'}",
            f"  Date cols:  {', '.join(self.fact.date_column_names) or 'none'}",
            f"  Dim tables: {len(self.dims)}",
        ]
        for dim in self.dims:
            lines.append(f"    - {dim.name} (key={dim.key_column})")
        return "\n".join(lines)
