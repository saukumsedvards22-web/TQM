"""Claude-powered DAX measure generator with prompt caching.

Strategy:
  - The system prompt (DAX best-practices guide) is cached once.
  - Each call sends the schema and asks Claude to generate a full measure set.
  - Returns structured DAXMeasureSet ready to push to Power BI.
"""

from __future__ import annotations

import json
import logging
import re

import anthropic

from ..schema.model import DimensionalModel
from .measures import DAXMeasure, DAXMeasureSet

log = logging.getLogger(__name__)

# The DAX domain knowledge injected as a cached system prompt.
_DAX_SYSTEM_PROMPT = """\
You are an expert Microsoft Power BI developer specialising in DAX (Data Analysis Expressions).
You have 10+ years of experience building financial and operational dashboards for SMEs.

## DAX Best Practices You Always Follow
1. Use CALCULATE() correctly — always place filter arguments as second+ parameters.
2. Prefer SUMX / AVERAGEX over SUM when per-row logic is needed.
3. Use DIVIDE(numerator, denominator, 0) instead of bare division to avoid blank errors.
4. All time-intelligence measures use DATEADD / SAMEPERIODLASTYEAR / TOTALYTD.
5. Format strings: currency "#,##0.00 €" (Latvian), percentage "0.00%", count "#,##0".
6. Name measures in English (snake_case is fine) but add Latvian descriptions.
7. Group related measures in Display Folders: "Revenue", "Cost", "Margin", "Volume", "YoY".
8. Never use implicit measures — always explicit.
9. Prefer variables (VAR … RETURN) for readability in complex expressions.
10. Always generate a _[Measure Name] MoM% and YoY% pair for every base measure.

## Output Format
Respond with a JSON array only — no prose, no markdown fences.
Each element:
{
  "name": "Total Revenue",
  "expression": "SUMX(sales, sales[qty] * sales[unit_price])",
  "table": "<fact_table_name>",
  "description": "Kopējie ieņēmumi (EUR)",
  "format_string": "#,##0.00 €",
  "display_folder": "Revenue"
}
"""


class DAXGenerator:
    """Generate DAX measures from a dimensional model using Claude."""

    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str | None = None) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(self, model: DimensionalModel, client_context: str = "") -> DAXMeasureSet:
        """Generate a full measure set for the given dimensional model.

        Args:
            model: The detected dimensional model.
            client_context: Optional free-text about the client industry / KPIs.
        """
        schema_json = self._model_to_schema_json(model)
        user_content = self._build_user_prompt(schema_json, client_context)

        log.info("Calling Claude to generate DAX measures…")
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": _DAX_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # Prompt caching
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )

        if not response.content:
            raise ValueError("API returned empty content block — cannot generate DAX measures")
        raw = response.content[0].text  # type: ignore[union-attr]
        measures = self._parse_response(raw, model.fact.name)

        log.info("Generated %d DAX measures", len(measures))
        return DAXMeasureSet(fact_table=model.fact.name, measures=measures)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _model_to_schema_json(self, model: DimensionalModel) -> str:
        schema: dict = {
            "fact_table": model.fact.name,
            "measures": [
                {
                    "column": m.name,
                    "dtype": m.dtype,
                    "cardinality": m.cardinality,
                    "sample": m.sample_values,
                }
                for m in model.fact.measures
            ],
            "date_columns": [d.name for d in model.fact.date_columns],
            "dimension_columns": [
                {
                    "column": d.name,
                    "cardinality": d.cardinality,
                    "sample": d.sample_values,
                }
                for d in model.fact.dimension_columns
            ],
            "dim_tables": [
                {"name": dim.name, "key": dim.key_column}
                for dim in model.dims
            ],
        }
        return json.dumps(schema, indent=2, ensure_ascii=False)

    def _build_user_prompt(self, schema_json: str, client_context: str) -> str:
        context_section = f"\n\n## Client Context\n{client_context}" if client_context else ""
        return (
            f"Generate a complete DAX measure set for this data model:{context_section}\n\n"
            f"## Schema\n```json\n{schema_json}\n```\n\n"
            "Generate ALL standard measures: totals, MoM%, YoY%, YTD, running totals, "
            "and any domain-specific KPIs implied by the column names. "
            "Output only the JSON array."
        )

    def _parse_response(self, raw: str, fact_table: str) -> list[DAXMeasure]:
        # Strip markdown fences if Claude adds them despite instructions
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract the JSON array from mixed content
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                log.error("Could not parse DAX response:\n%s", raw)
                return []
            items = json.loads(match.group())

        measures: list[DAXMeasure] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            measures.append(
                DAXMeasure(
                    name=item.get("name", "Unknown"),
                    expression=item.get("expression", "BLANK()"),
                    table=item.get("table", fact_table),
                    description=item.get("description", ""),
                    format_string=item.get("format_string", ""),
                    display_folder=item.get("display_folder", ""),
                )
            )
        return measures
