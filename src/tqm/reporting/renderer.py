"""Render AICommentary + KPI deltas into HTML and PDF reports."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..ai.analyst import AICommentary
from ..ai.snapshot import SnapshotComparison

log = logging.getLogger(__name__)

# Templates live at project-root/templates. Resolve relative to this file:
# src/tqm/reporting/renderer.py → ../../.. → src/ → .. → project root
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
if not _TEMPLATES_DIR.is_dir():
    raise RuntimeError(
        f"Templates directory not found: {_TEMPLATES_DIR}\n"
        "Expected layout: project_root/templates/report.html.j2"
    )


@dataclass
class KPICard:
    label: str
    value_fmt: str
    pct: float | None
    direction: str  # "up" | "down" | "flat"


class ReportRenderer:
    """Render management reports from AI commentary and KPI data."""

    def __init__(self, templates_dir: Path = _TEMPLATES_DIR) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def render_html(
        self,
        commentary: AICommentary,
        comparison: SnapshotComparison,
        client_name: str,
        output_path: Path | None = None,
    ) -> str:
        template = self.env.get_template("report.html.j2")
        kpi_cards = self._build_kpi_cards(comparison)

        html = template.render(
            client_name=client_name,
            period=comparison.period_label,
            generated_date=date.today().strftime("%d %B %Y"),
            commentary=commentary,
            kpis=kpi_cards,
        )

        if output_path:
            output_path.write_text(html, encoding="utf-8")
            log.info("HTML report written to %s", output_path)

        return html

    def render_pdf(
        self,
        commentary: AICommentary,
        comparison: SnapshotComparison,
        client_name: str,
        output_path: Path,
    ) -> None:
        try:
            import weasyprint
        except ImportError:
            raise RuntimeError(
                "weasyprint is required for PDF export. "
                "Install it with: pip install weasyprint"
            )

        html = self.render_html(commentary, comparison, client_name)
        weasyprint.HTML(string=html).write_pdf(str(output_path))
        log.info("PDF report written to %s", output_path)

    def render_markdown(
        self,
        commentary: AICommentary,
        comparison: SnapshotComparison,
        client_name: str,
        output_path: Path | None = None,
    ) -> str:
        lines = [f"# {client_name} — Management Report {comparison.period_label}\n"]
        lines.append(commentary.to_markdown())

        # Append KPI table
        lines.append("\n\n## KPI Summary\n")
        lines.append("| KPI | Current | Previous | Change |")
        lines.append("|-----|---------|----------|--------|")
        for kpi, delta in comparison.kpi_deltas.items():
            direction = "▲" if delta["pct"] > 0 else ("▼" if delta["pct"] < 0 else "–")
            lines.append(
                f"| {kpi} | {delta['current']:,.2f} | {delta['previous']:,.2f} "
                f"| {direction} {abs(delta['pct']):.1f}% |"
            )

        md = "\n".join(lines)
        if output_path:
            output_path.write_text(md, encoding="utf-8")
            log.info("Markdown report written to %s", output_path)

        return md

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_kpi_cards(self, comparison: SnapshotComparison) -> list[KPICard]:
        cards: list[KPICard] = []
        deltas = comparison.kpi_deltas

        for kpi, delta in deltas.items():
            label = kpi.replace("_", " ").title()
            current = delta["current"]
            pct = delta["pct"]

            # Format value: use € for revenue-sounding names, % for pct names
            if any(x in kpi for x in ("revenue", "sales", "cost", "margin", "profit", "amount")):
                value_fmt = f"€{current:,.0f}"
            elif "pct" in kpi or "rate" in kpi:
                value_fmt = f"{current:.1f}%"
            else:
                value_fmt = f"{current:,.0f}"

            direction = "flat" if abs(pct) < 3 else ("up" if pct > 0 else "down")
            cards.append(KPICard(label=label, value_fmt=value_fmt, pct=pct, direction=direction))

        return cards[:12]  # Cap at 12 cards per report page
