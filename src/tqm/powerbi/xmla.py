"""XMLA endpoint client — proper semantic model deployment.

Push Datasets are deprecated for serious use:
  - 200k rows/hour limit
  - No calculated columns
  - Neutered DAX (no USERELATIONSHIP, limited time-intelligence)
  - Cannot be published as certified datasets

The correct path for SME dashboards is:
  1. Build a Tabular model (.bim / TMDL) locally
  2. Deploy via XMLA endpoint using Analysis Services REST API
  3. Refresh via Power BI REST API (which does work on real datasets)

This module handles XMLA deployment using the Analysis Services
client library (which speaks TOM — Tabular Object Model).

For environments without the .NET Analysis Services client:
  - Falls back to Tabular Editor CLI (cross-platform, free)
  - Or exports a .bim file for manual deployment

Reference:
  https://learn.microsoft.com/en-us/analysis-services/xmla/xml-elements-commands/
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from ..schema.model import DimensionalModel

log = logging.getLogger(__name__)


class XMLAClient:
    """Deploy Tabular models via XMLA endpoint.

    XMLA endpoint format:
      powerbi://api.powerbi.com/v1.0/myorg/<WorkspaceName>
    """

    def __init__(
        self,
        xmla_endpoint: str,
        database_name: str,
        tabular_editor_path: str = "TabularEditor",
    ) -> None:
        self.xmla_endpoint = xmla_endpoint
        self.database_name = database_name
        self.te_path = tabular_editor_path

    def deploy_model(self, bim_path: Path) -> bool:
        """Deploy a .bim file to the XMLA endpoint via Tabular Editor CLI."""
        if not bim_path.exists():
            raise FileNotFoundError(f"BIM file not found: {bim_path}")

        log.info("Deploying %s to %s / %s", bim_path.name, self.xmla_endpoint, self.database_name)

        try:
            result = subprocess.run(
                [
                    self.te_path,
                    str(bim_path),
                    "-S", self._deploy_script(),
                    "-C",  # Create/overwrite
                    self.xmla_endpoint,
                    self.database_name,
                ],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode != 0:
                log.error("Tabular Editor deployment error:\n%s", result.stderr)
                return False
            log.info("XMLA deployment succeeded")
            return True
        except FileNotFoundError:
            log.error("Tabular Editor not found. Install: https://github.com/TabularEditor/TabularEditor/releases")
            return False

    def build_bim(self, model: DimensionalModel, dataset_name: str) -> dict:
        """Build a Tabular Model BIM (JSON) from a DimensionalModel.

        This is a real Analysis Services Tabular model with:
          - Proper date tables (mark as date table)
          - Calculated columns support
          - Full DAX without restrictions
          - Relationships with cross-filter direction
        """
        tables = []

        # Fact table
        fact_cols = []
        for col in model.fact.all_columns:
            fact_cols.append({
                "name": col.name,
                "dataType": self._as_type(col.dtype),
                "isHidden": False,
                "summarizeBy": "sum" if col.dtype == "numeric" else "none",
            })
        tables.append({
            "name": model.fact.name,
            "columns": fact_cols,
            "partitions": [self._partition(model.fact.name)],
        })

        # Date table (mark as date table for time-intelligence)
        if model.fact.date_columns:
            date_col_name = model.fact.date_columns[0].name
            date_table = self._build_date_table(date_col_name)
            tables.append(date_table)

        # Dim tables
        for dim in model.dims:
            dim_cols = [
                {"name": dim.key_column, "dataType": "string", "isKey": True},
                *[{"name": lc, "dataType": "string"} for lc in dim.label_cols],
            ]
            tables.append({
                "name": dim.name,
                "columns": dim_cols,
                "partitions": [self._partition(dim.name)],
            })

        # Relationships
        relationships = []
        for rel in model.relationships:
            relationships.append({
                "name": f"rel_{rel.from_table}_{rel.from_column}",
                "fromTable": rel.from_table,
                "fromColumn": rel.from_column,
                "toTable": rel.to_table,
                "toColumn": rel.to_column,
                "crossFilteringBehavior": "oneDirection",
            })

        return {
            "name": dataset_name,
            "compatibilityLevel": 1605,
            "model": {
                "name": dataset_name,
                "tables": tables,
                "relationships": relationships,
                "cultures": [{"name": "lv-LV"}],
            },
        }

    def save_bim(self, bim: dict, path: Path) -> None:
        path.write_text(json.dumps(bim, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("BIM file written to %s", path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _as_type(self, dtype: str) -> str:
        mapping = {
            "numeric": "double",
            "datetime": "dateTime",
            "text": "string",
            "numeric_cat": "string",
            "int64": "int64",
            "float64": "double",
        }
        for k, v in mapping.items():
            if k in dtype.lower():
                return v
        return "string"

    def _partition(self, table_name: str) -> dict:
        """M-query partition — source filled in at load time."""
        return {
            "name": f"{table_name}_partition",
            "source": {
                "type": "m",
                "expression": f'let Source = #table({{}}, {{}}) in Source',
            },
        }

    def _build_date_table(self, date_col_name: str) -> dict:
        """Generate a proper Power BI date dimension table using DAX CALENDAR."""
        return {
            "name": "Date",
            "isDateTable": True,
            "columns": [
                {"name": "Date", "dataType": "dateTime", "isKey": True,
                 "summarizeBy": "none", "isHidden": False},
                {"name": "Year", "dataType": "int64", "summarizeBy": "none",
                 "expression": "YEAR([Date])"},
                {"name": "Month", "dataType": "int64", "summarizeBy": "none",
                 "expression": "MONTH([Date])"},
                {"name": "MonthName", "dataType": "string", "summarizeBy": "none",
                 "expression": 'FORMAT([Date], "MMMM")'},
                {"name": "Quarter", "dataType": "string", "summarizeBy": "none",
                 "expression": '"Q" & ROUNDUP(MONTH([Date])/3, 0)'},
                {"name": "YearMonth", "dataType": "string", "summarizeBy": "none",
                 "expression": 'FORMAT([Date], "YYYY-MM")'},
            ],
            "partitions": [{
                "name": "Date_partition",
                "source": {
                    "type": "calculated",
                    "expression": (
                        "ADDCOLUMNS("
                        "    CALENDAR(DATE(2020,1,1), DATE(2030,12,31)),"
                        '    "Year", YEAR([Date]),'
                        '    "Month", MONTH([Date]),'
                        '    "MonthName", FORMAT([Date], "MMMM"),'
                        '    "Quarter", "Q" & ROUNDUP(MONTH([Date])/3,0),'
                        '    "YearMonth", FORMAT([Date], "YYYY-MM")'
                        ")"
                    ),
                },
            }],
        }

    def _deploy_script(self) -> str:
        return 'Model.SaveChanges(); // Deploy via Tabular Editor'
