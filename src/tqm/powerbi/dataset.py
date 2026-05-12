"""Build Power BI Push Dataset schema from a DimensionalModel."""

from __future__ import annotations

import pandas as pd

from ..schema.model import DimensionalModel, FactTable


_PBI_TYPE_MAP: dict[str, str] = {
    "int64": "Int64",
    "float64": "Double",
    "datetime64[ns]": "DateTime",
    "object": "String",
    "bool": "Boolean",
    "numeric": "Double",
    "datetime": "DateTime",
    "text": "String",
    "numeric_cat": "String",
}


def _pbi_type(dtype: str) -> str:
    for key, val in _PBI_TYPE_MAP.items():
        if key in dtype.lower():
            return val
    return "String"


class DatasetBuilder:
    """Convert a DimensionalModel to a Power BI Push Dataset schema dict."""

    def build(self, model: DimensionalModel, dataset_name: str) -> dict:
        tables = []

        # Fact table
        tables.append(self._fact_table_schema(model.fact))

        # Dim tables
        for dim in model.dims:
            cols = [{"name": dim.key_column, "dataType": "String"}]
            for label in dim.label_cols:  # noqa: E501
                cols.append({"name": label, "dataType": "String"})
            tables.append({"name": dim.name, "columns": cols})

        relationships = [
            {
                "name": f"rel_{r.from_table}_{r.from_column}",
                "fromTable": r.from_table,
                "fromColumn": r.from_column,
                "toTable": r.to_table,
                "toColumn": r.to_column,
            }
            for r in model.relationships
        ]

        return {
            "name": dataset_name,
            "defaultMode": "Push",
            "tables": tables,
            "relationships": relationships,
        }

    def _fact_table_schema(self, fact: FactTable) -> dict:
        columns = []
        for col in fact.all_columns:
            columns.append({
                "name": col.name,
                "dataType": _pbi_type(col.dtype),
            })
        return {"name": fact.name, "columns": columns}

    def rows_from_dataframe(self, df: pd.DataFrame) -> list[dict]:
        """Convert a DataFrame to a list of row dicts for the Push API."""
        # Serialise dates as ISO strings for JSON
        df = df.copy()
        for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
        return df.where(pd.notna(df), None).to_dict(orient="records")  # type: ignore[return-value]
