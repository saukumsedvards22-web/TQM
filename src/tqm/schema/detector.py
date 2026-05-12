"""Auto-detect schema and build a dimensional model from raw tables."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pandas as pd

from ..ingestion.base import RawTable
from .model import (
    ColumnRole,
    DimTable,
    DimensionalModel,
    FactTable,
    ModelColumn,
    Relationship,
)

if TYPE_CHECKING:
    pass

# Heuristic thresholds
_DATE_DTYPE_MATCH = re.compile(r"datetime|date", re.I)
_ID_PATTERNS = re.compile(r"(^id$|_id$|^code$|_code$|_no$|^no_|_key$|^key_)", re.I)
_IGNORE_PATTERNS = re.compile(r"(unnamed|empty|blank|filler)", re.I)
# High-cardinality numeric columns are likely measures, low-cardinality are categorical
_MAX_DIM_CARDINALITY_RATIO = 0.05  # ≤5% unique = dimension


class SchemaDetector:
    """Classify columns and assemble a star schema from one or more RawTables."""

    def detect(self, tables: list[RawTable]) -> DimensionalModel:
        if not tables:
            raise ValueError("Need at least one table")

        # Pick the largest table as the fact table
        fact_raw = max(tables, key=lambda t: t.row_count)
        fact = self._build_fact(fact_raw)

        # Build dimension tables from remaining tables + dimension columns
        dims: list[DimTable] = []
        relationships: list[Relationship] = []

        for raw in tables:
            if raw.name == fact_raw.name:
                continue
            dim = self._build_dim(raw)
            if dim:
                dims.append(dim)

        # Also extract inline dimension columns from the fact
        dims += self._extract_inline_dims(fact)
        relationships += self._infer_relationships(fact, dims)

        return DimensionalModel(fact=fact, dims=dims, relationships=relationships)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _classify_column(self, series: pd.Series, name: str) -> ModelColumn:
        if _IGNORE_PATTERNS.search(name):
            return ModelColumn(name=name, role=ColumnRole.IGNORE, dtype=str(series.dtype), cardinality=0)

        cardinality = series.nunique()
        n = max(len(series), 1)
        sample = [str(v) for v in series.dropna().unique()[:5]]

        # Date
        if _DATE_DTYPE_MATCH.search(str(series.dtype)) or pd.api.types.is_datetime64_any_dtype(series):
            return ModelColumn(name=name, role=ColumnRole.DATE, dtype="datetime", cardinality=cardinality, sample_values=sample)

        # ID / Key
        if _ID_PATTERNS.search(name):
            return ModelColumn(name=name, role=ColumnRole.ID_KEY, dtype=str(series.dtype), cardinality=cardinality, sample_values=sample)

        # Numeric measure vs categorical
        if pd.api.types.is_numeric_dtype(series):
            if cardinality / n > _MAX_DIM_CARDINALITY_RATIO:
                return ModelColumn(name=name, role=ColumnRole.NUMERIC_MEASURE, dtype="numeric", cardinality=cardinality, sample_values=sample)
            else:
                return ModelColumn(name=name, role=ColumnRole.TEXT_DIMENSION, dtype="numeric_cat", cardinality=cardinality, sample_values=sample)

        # Text — low cardinality = dimension
        return ModelColumn(name=name, role=ColumnRole.TEXT_DIMENSION, dtype="text", cardinality=cardinality, sample_values=sample, is_nullable=bool(series.isna().any()))

    def _build_fact(self, raw: RawTable) -> FactTable:
        cols: list[ModelColumn] = []
        for col in raw.df.columns:
            mc = self._classify_column(raw.df[col], col)
            if mc.role != ColumnRole.IGNORE:
                cols.append(mc)

        measures = [c for c in cols if c.role == ColumnRole.NUMERIC_MEASURE]
        dates = [c for c in cols if c.role == ColumnRole.DATE]
        dims = [c for c in cols if c.role == ColumnRole.TEXT_DIMENSION]

        return FactTable(
            name=raw.name,
            df=raw.df,
            measures=measures,
            date_columns=dates,
            dimension_columns=dims,
            all_columns=cols,
        )

    def _build_dim(self, raw: RawTable) -> DimTable | None:
        if raw.row_count < 2:
            return None
        # First text or ID column is the key
        key_col = next(
            (c for c in raw.df.columns if _ID_PATTERNS.search(c) or raw.df[c].nunique() == raw.row_count),
            raw.df.columns[0],
        )
        label_cols = [c for c in raw.df.columns if c != key_col]
        return DimTable(name=raw.name, df=raw.df, key_column=key_col, label_cols=label_cols)

    def _extract_inline_dims(self, fact: FactTable) -> list[DimTable]:
        """Materialise low-cardinality dimension columns as small lookup tables."""
        dims: list[DimTable] = []
        for mc in fact.dimension_columns:
            if mc.cardinality <= 200:
                unique_vals = fact.df[mc.name].dropna().unique()
                dim_df = pd.DataFrame({mc.name: unique_vals}).reset_index(drop=True)
                dims.append(DimTable(name=f"dim_{mc.name}", df=dim_df, key_column=mc.name, label_cols=[]))
        return dims

    def _infer_relationships(self, fact: FactTable, dims: list[DimTable]) -> list[Relationship]:
        rels: list[Relationship] = []
        for dim in dims:
            # Match dim key column name to a fact column
            if dim.key_column in fact.df.columns:
                rels.append(
                    Relationship(
                        from_table=fact.name,
                        from_column=dim.key_column,
                        to_table=dim.name,
                        to_column=dim.key_column,
                    )
                )
        return rels
