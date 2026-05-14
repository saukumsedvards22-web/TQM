"""TQM command-line interface.

Commands:
  tqm ingest       — Parse Excel / SAP files and show schema
  tqm dax          — Generate DAX measures from ingested data
  tqm deploy       — Push dataset + measures to Power BI
  tqm report       — Generate monthly AI commentary report
  tqm run          — End-to-end: ingest → dax → deploy → report
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

load_dotenv()

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


# ──────────────────────────────────────────────
# Root group
# ──────────────────────────────────────────────

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """TQM — AI-powered Power BI automation for SMEs."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# ──────────────────────────────────────────────
# ingest
# ──────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--source", "-s", type=click.Choice(["excel", "sap", "auto"]), default="auto")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write schema JSON to file")
@click.pass_context
def ingest(ctx: click.Context, path: str, source: str, output: str | None) -> None:
    """Parse Excel or SAP files and display the detected schema."""
    from .ingestion import ExcelIngester, SAPIngester
    from .schema import SchemaDetector

    p = Path(path)
    source_type = source

    if source_type == "auto":
        source_type = "sap" if p.suffix.lower() in {".txt", ".csv"} else "excel"

    console.print(f"[bold]Ingesting[/bold] {p} as [cyan]{source_type}[/cyan]…")

    if source_type == "excel":
        result = ExcelIngester().ingest(p) if p.is_file() else ExcelIngester().ingest_directory(p)
    else:
        result = SAPIngester().ingest(p) if p.is_file() else SAPIngester().ingest_directory(p)

    if result.warnings:
        for w in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}")

    table = Table(title="Detected Tables", show_header=True)
    table.add_column("Table", style="cyan")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Source")

    for t in result.tables:
        table.add_row(t.name, str(t.row_count), str(t.col_count), t.source_file.name)

    console.print(table)

    model = SchemaDetector().detect(result.tables)
    console.print(Panel(model.summary(), title="Dimensional Model"))

    if output:
        schema_data = {
            "fact": model.fact.name,
            "measures": model.fact.measure_names,
            "date_columns": model.fact.date_column_names,
            "dims": [d.name for d in model.dims],
        }
        Path(output).write_text(json.dumps(schema_data, indent=2))
        console.print(f"[green]Schema written to {output}[/green]")


# ──────────────────────────────────────────────
# dax
# ──────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--client-context", "-c", default="", help="Client industry / KPI context")
@click.option("--output-dir", "-o", type=click.Path(), default="output", help="Output directory")
@click.option("--api-key", default=None, envvar="ANTHROPIC_API_KEY")
@click.pass_context
def dax(ctx: click.Context, path: str, client_context: str, output_dir: str, api_key: str | None) -> None:
    """Generate DAX measures from Excel/SAP data using Claude."""
    from .ingestion import ExcelIngester, SAPIngester
    from .schema import SchemaDetector
    from .dax import DAXGenerator
    from .powerbi import MeasureDeployer

    p = Path(path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Step 1/3:[/bold] Ingesting data…")
    source = "sap" if p.suffix.lower() in {".txt", ".csv"} else "excel"
    ingester = SAPIngester() if source == "sap" else ExcelIngester()
    result = ingester.ingest(p) if p.is_file() else ingester.ingest_directory(p)  # type: ignore[union-attr]

    console.print("[bold]Step 2/3:[/bold] Detecting schema…")
    model = SchemaDetector().detect(result.tables)
    console.print(Panel(model.summary(), title="Schema"))

    console.print("[bold]Step 3/3:[/bold] Generating DAX measures with Claude…")
    generator = DAXGenerator(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
    measure_set = generator.generate(model, client_context=client_context)

    deployer = MeasureDeployer()
    script_path = out / "measures.cs"
    dax_path = out / "measures.dax"
    deployer.export_script(measure_set, script_path)
    deployer.export_dax_file(measure_set, dax_path)

    console.print(f"[green]✓[/green] Generated [bold]{len(measure_set.measures)}[/bold] measures")
    console.print(f"  Tabular Editor script → {script_path}")
    console.print(f"  DAX file              → {dax_path}")

    # Print measure table
    t = Table(title="Generated Measures", show_header=True)
    t.add_column("Name", style="cyan")
    t.add_column("Folder")
    t.add_column("Format")
    for m in measure_set.measures:
        t.add_row(m.name, m.display_folder, m.format_string)
    console.print(t)


# ──────────────────────────────────────────────
# deploy
# ──────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--dataset-name", "-n", required=True, help="Power BI dataset name")
@click.option("--workspace-id", envvar="PBI_WORKSPACE_ID", required=True)
@click.option("--tenant-id", envvar="PBI_TENANT_ID", required=True)
@click.option("--client-id", envvar="PBI_CLIENT_ID", required=True)
@click.option("--client-secret", envvar="PBI_CLIENT_SECRET", required=True)
@click.pass_context
def deploy(
    ctx: click.Context,
    path: str,
    dataset_name: str,
    workspace_id: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> None:
    """Push ingested data to a Power BI Push Dataset."""
    from .ingestion import ExcelIngester, SAPIngester
    from .schema import SchemaDetector
    from .powerbi import PowerBIClient, DatasetBuilder

    p = Path(path)
    ingester = SAPIngester() if p.suffix.lower() in {".txt", ".csv"} else ExcelIngester()
    result = ingester.ingest(p) if p.is_file() else ingester.ingest_directory(p)  # type: ignore[union-attr]
    model = SchemaDetector().detect(result.tables)

    pbi = PowerBIClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        workspace_id=workspace_id,
    )
    builder = DatasetBuilder()
    schema = builder.build(model, dataset_name)

    console.print(f"Creating dataset [cyan]{dataset_name}[/cyan]…")
    ds = pbi.create_dataset(schema)
    ds_id = ds["id"]
    console.print(f"[green]✓[/green] Dataset created: {ds_id}")

    console.print("Pushing rows…")
    rows = builder.rows_from_dataframe(model.fact.df)
    pbi.push_rows(ds_id, model.fact.name, rows)
    console.print(f"[green]✓[/green] Pushed {len(rows):,} rows to {model.fact.name}")


# ──────────────────────────────────────────────
# report
# ──────────────────────────────────────────────

@main.command()
@click.argument("current_file", type=click.Path(exists=True))
@click.argument("previous_file", type=click.Path(exists=True))
@click.option("--client-name", "-n", required=True, help="Client company name")
@click.option("--client-profile", "-p", default="", help="Client industry / context for AI")
@click.option("--output-dir", "-o", type=click.Path(), default="output")
@click.option("--format", "fmt", type=click.Choice(["html", "pdf", "md", "all"]), default="all")
@click.option("--email-to", multiple=True, help="Email addresses to send report to")
@click.option("--api-key", default=None, envvar="ANTHROPIC_API_KEY")
@click.option("--dry-run", is_flag=True, help="Generate report but do not email. Writes to output-dir.")
@click.option("--require-approval", is_flag=True, default=True, help="Block delivery on anomalies (default: on)")
@click.option("--delta-block-pct", default=40.0, show_default=True, help="% change that blocks delivery for review")
@click.option("--expected-period", default=None, help="Expected period for date validation e.g. 2024-03")
@click.option(
    "--confirm-dpa", is_flag=True, default=False,
    help=(
        "Confirm that a Data Processing Agreement covering Anthropic as a sub-processor "
        "is in place with this client (required for email delivery — FM-07)."
    ),
)
@click.pass_context
def report(
    ctx: click.Context,
    current_file: str,
    previous_file: str,
    client_name: str,
    client_profile: str,
    output_dir: str,
    fmt: str,
    email_to: tuple[str, ...],
    api_key: str | None,
    dry_run: bool,
    require_approval: bool,
    delta_block_pct: float,
    expected_period: str | None,
    confirm_dpa: bool,
) -> None:
    """Generate a monthly AI commentary report from two months of data.

    Runs schema drift detection, date column validation, AI review gate,
    and cost tracking before any delivery. Use --dry-run to generate
    without emailing.

    Email delivery requires --confirm-dpa to be set, confirming a Data
    Processing Agreement covering Anthropic as a sub-processor is in place.
    See FM-07 in config/fmea.yaml and https://www.anthropic.com/legal/dpa
    """
    # FM-07 gate: block email delivery when no DPA confirmation
    if email_to and not dry_run and not confirm_dpa:
        console.print(
            "[red bold]DPA GATE BLOCKED[/red bold]\n"
            "Email delivery requires --confirm-dpa.\n\n"
            "Before sending client data to the Anthropic API:\n"
            "  1. Confirm Anthropic is listed as a sub-processor in your DPA with this client.\n"
            "  2. Anthropic's DPA: https://www.anthropic.com/legal/dpa\n"
            "  3. Re-run with --confirm-dpa once the DPA is in place.\n\n"
            "Use --dry-run to generate the report without emailing."
        )
        sys.exit(1)

    from .ingestion import ExcelIngester, SAPIngester
    from .schema import SchemaDetector, SchemaDriftDetector, DateColumnValidator
    from .ai import AIAnalyst, MonthlySnapshot, SnapshotComparison, ReviewGate, ReviewBlockedError, CostTracker
    from .reporting import ReportRenderer

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cost_tracker = CostTracker(log_path=out / ".tqm_costs.jsonl")
    drift_detector = SchemaDriftDetector(schema_dir=out / ".tqm_schemas")

    def _ingest(fp: str):
        p = Path(fp)
        ingester = SAPIngester() if p.suffix.lower() in {".txt", ".csv"} else ExcelIngester()
        return ingester.ingest(p)

    # ── 1. Ingest ────────────────────────────────────────────────────
    console.print("[bold]Step 1/5:[/bold] Ingesting data…")
    cur_result = _ingest(current_file)
    prev_result = _ingest(previous_file)

    model_cur = SchemaDetector().detect(cur_result.tables)
    model_prev = SchemaDetector().detect(prev_result.tables)

    fact = model_cur.fact

    # ── 2. Schema drift check ────────────────────────────────────────
    console.print("[bold]Step 2/5:[/bold] Checking schema drift…")
    drift_report = drift_detector.check(fact.df, client_name)
    if drift_report.has_blockers:
        console.print(f"[red bold]SCHEMA DRIFT DETECTED — aborting[/red bold]\n{drift_report.summary()}")
        sys.exit(1)
    elif not drift_report.is_clean:
        console.print(f"[yellow]{drift_report.summary()}[/yellow]")
    else:
        console.print("[green]✓[/green] Schema unchanged")

    # ── 3. Date column validation ────────────────────────────────────
    console.print("[bold]Step 3/5:[/bold] Validating date column…")
    date_cols = fact.date_column_names
    measure_cols = fact.measure_names
    dim_cols = [d.name for d in fact.dimension_columns]

    date_validator = DateColumnValidator(expected_period=expected_period)
    if date_cols:
        chosen_date, date_result = date_validator.pick_best_date_column(fact.df, date_cols)
        if date_result and not date_result.passed:
            console.print(f"[red bold]DATE VALIDATION FAILED:[/red bold]\n{date_result.summary()}")
            if any(i.severity == "block" for i in date_result.issues):
                console.print("[red]Time-intelligence measures will be wrong. Aborting.[/red]")
                sys.exit(1)
    else:
        chosen_date = None
        console.print("[yellow]⚠[/yellow] No date column found — time-intelligence measures will be unavailable")

    # ── 4. Build snapshots + AI commentary ──────────────────────────
    console.print("[bold]Step 4/5:[/bold] Generating AI commentary…")
    cur_period = Path(current_file).stem
    prev_period = Path(previous_file).stem

    snap_cur = MonthlySnapshot.from_dataframe(
        fact.df, chosen_date or "", measure_cols, dim_cols, cur_period
    )
    snap_prev = MonthlySnapshot.from_dataframe(
        model_prev.fact.df, chosen_date or "", measure_cols, dim_cols, prev_period
    )
    comparison = SnapshotComparison(current=snap_cur, previous=snap_prev)

    analyst = AIAnalyst(
        api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
        client_profile=client_profile,
    )
    commentary = analyst.analyse(comparison, cost_tracker=cost_tracker, client_name=client_name)
    cost_tracker.print_session_summary()
    console.print(Panel(commentary.headline, title="AI Headline"))

    # ── 5. Review gate ───────────────────────────────────────────────
    console.print("[bold]Step 5/5:[/bold] Running review gate…")
    gate_mode = "interactive" if (email_to and not dry_run) else "pending_file"
    gate = ReviewGate(
        delta_block_pct=delta_block_pct,
        mode=gate_mode,
        pending_dir=out / "pending",
    )
    review_result = gate.check(commentary, comparison, client_name)

    if not review_result.passed:
        console.print(f"[red bold]REVIEW GATE BLOCKED — {len(review_result.blockers)} issue(s)[/red bold]")
        for flag in review_result.blockers:
            console.print(f"  🔴 [{flag.code}] {flag.message}")
            if flag.detail:
                console.print(f"       {flag.detail}")

        if email_to and not dry_run and require_approval:
            approved = gate.require_human_approval(review_result, commentary, comparison, client_name)
            if not approved:
                console.print("[red]Delivery cancelled by reviewer.[/red]")
                sys.exit(1)
            console.print("[green]✓[/green] Approved by reviewer")
        elif not dry_run and require_approval:
            console.print("[yellow]Report saved to pending/ — review before delivering.[/yellow]")

    renderer = ReportRenderer()
    safe_name = client_name.replace(" ", "_").lower()

    if fmt in {"html", "all"}:
        html_path = out / f"{safe_name}_{cur_period}_report.html"
        renderer.render_html(commentary, comparison, client_name, html_path)
        console.print(f"[green]✓[/green] HTML → {html_path}")

    if fmt in {"pdf", "all"}:
        pdf_path = out / f"{safe_name}_{cur_period}_report.pdf"
        renderer.render_pdf(commentary, comparison, client_name, pdf_path)
        console.print(f"[green]✓[/green] PDF  → {pdf_path}")

    if fmt in {"md", "all"}:
        md_path = out / f"{safe_name}_{cur_period}_report.md"
        renderer.render_markdown(commentary, comparison, client_name, md_path)
        console.print(f"[green]✓[/green] MD   → {md_path}")

    if email_to and not dry_run:
        from .reporting import ReportEmailer

        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")
        from_addr = os.getenv("SMTP_FROM", smtp_user)

        if not smtp_host:
            console.print("[yellow]⚠[/yellow] SMTP_HOST not set — skipping email")
        else:
            emailer = ReportEmailer(smtp_host, smtp_port, smtp_user, smtp_pass, from_addr)
            html_content = renderer.render_html(commentary, comparison, client_name)
            pdf_p = out / f"{safe_name}_{cur_period}_report.pdf" if fmt in {"pdf", "all"} else None
            emailer.send(
                to=list(email_to),
                subject=f"{client_name} — Management Report {cur_period}",
                html_body=html_content,
                pdf_path=pdf_p,
            )
            console.print(f"[green]✓[/green] Report emailed to {', '.join(email_to)}")
    elif dry_run and email_to:
        console.print(f"[yellow]DRY RUN — would email {', '.join(email_to)} but delivery skipped[/yellow]")

    # Update schema fingerprint after successful run
    drift_detector.update(fact.df, client_name)
    console.print(f"[dim]Schema fingerprint updated. Cost this run: {cost_tracker.monthly_summary(client_name)}[/dim]")


# ──────────────────────────────────────────────
# run — end-to-end pipeline
# ──────────────────────────────────────────────

@main.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.pass_context
def run(ctx: click.Context, config_file: str) -> None:
    """Run the full pipeline from a YAML config file."""
    import yaml

    cfg = yaml.safe_load(Path(config_file).read_text())
    console.print(Panel(f"Running pipeline for [bold]{cfg.get('client_name', 'client')}[/bold]"))

    # Invoke sub-commands programmatically
    ctx.invoke(
        report,
        current_file=cfg["current_file"],
        previous_file=cfg["previous_file"],
        client_name=cfg["client_name"],
        client_profile=cfg.get("client_profile", ""),
        output_dir=cfg.get("output_dir", "output"),
        fmt=cfg.get("format", "all"),
        email_to=tuple(cfg.get("email_to", [])),
        api_key=cfg.get("anthropic_api_key"),
        dry_run=cfg.get("dry_run", False),
        require_approval=cfg.get("require_approval", True),
        expected_period=cfg.get("expected_period"),
        confirm_dpa=cfg.get("confirm_dpa", False),
        delta_block_pct=cfg.get("delta_block_pct", 40.0),
    )


# ──────────────────────────────────────────────
# mutate-gate
# ──────────────────────────────────────────────

@main.command("mutate-gate")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")
def mutate_gate(as_json: bool) -> None:
    """Verify the review gate catches every documented failure mode.

    Runs the canonical mutation suite (MUTATIONS + COMPARISON_MUTATIONS) against
    the gate and reports which failure modes are caught and which slip through.
    Any uncaught mutation is a gate hole — fix before the next release.

    Exit code 0 if all mutations caught; 1 if any gate hole detected.
    """
    import logging as _logging
    from .ai.mutations import run_mutations

    # Suppress all log output during mutation runs — gate holes surface in the report.
    _logging.disable(_logging.CRITICAL)
    try:
        report = run_mutations()
    finally:
        _logging.disable(_logging.NOTSET)

    if as_json:
        import json as _json
        console.print(_json.dumps({
            "total": len(report.results),
            "caught": len(report.results) - len(report.holes),
            "holes": [
                {"name": h.mutation.name, "expected": h.mutation.expected_block_code,
                 "actual": h.actual_block_codes, "description": h.mutation.description}
                for h in report.holes
            ],
        }, indent=2))
    else:
        console.print(report.text())

    if not report.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
