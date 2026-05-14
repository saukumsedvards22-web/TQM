# TQM — AI-leveraged Managed Reporting for SMEs

> **The product:** Latvian SMEs have data sitting in Excel and SAP exports that no one is analyzing. TQM is a **managed monthly reporting service**: we build the Power BI dashboard, our pipeline drafts the management commentary using Claude, a TQM analyst reviews and signs off every report, and your CEO/CFO receives a 2-page PDF on the 1st of each month.
>
> This is **not** a "fully automated AI report". The engineering controls (audit log, FMEA register, gated review) exist precisely *because* AI-drafted commentary cannot be trusted to ship unreviewed to a paying client. The price reflects the analyst hours, not the compute.

---

## What it does

| Step | Input | Output |
|------|-------|--------|
| **Ingest** | `.xlsx`, `.xls`, SAP `.txt`/`.csv` | Cleaned, typed DataFrames |
| **Schema detect** | DataFrames | Star-schema dimensional model |
| **DAX generate** | Dimensional model | Full measure set (Tabular Editor script + DAX file) |
| **Deploy** | Measures + data | Power BI Push Dataset with all rows |
| **Report** | Two months of data | HTML + PDF management report with AI commentary |
| **Email** | Report files | Delivered to CEO/CFO inbox on the 1st of each month |

---

## Architecture

```
src/tqm/
├── ingestion/      # Excel (multi-sheet, auto-header) + SAP flat-file parsers
├── schema/         # Column classifier + star-schema builder
├── dax/            # Claude-powered DAX measure generator
├── powerbi/        # Power BI REST API client + measure deployer
├── ai/             # Monthly snapshot comparisons + AI analyst (Claude)
├── reporting/      # HTML/PDF report renderer + SMTP emailer
└── cli.py          # Click CLI: ingest | dax | deploy | report | run
```

### AI prompt caching

Both the DAX generator and the AI analyst use **Claude's prompt caching** on their system prompts. The DAX best-practices guide (~800 tokens) and the analyst persona (~600 tokens) are cached as `ephemeral` blocks, so repeated monthly calls are fast and use ~90% fewer tokens on the system prompt.

---

## Quick start

```bash
# 1. Install
pip install -e .
cp .env.example .env
# Fill in ANTHROPIC_API_KEY at minimum

# 2. Inspect your data
tqm ingest sample_data/sales_2024_03.csv

# 3. Generate DAX measures
tqm dax sample_data/sales_2024_03.csv \
  --client-context "Latvian wholesale, focus on revenue and margin"

# 4. Generate monthly report
tqm report sample_data/sales_2024_03.csv sample_data/sales_2024_02.csv \
  --client-name "Acme SIA" \
  --client-profile "Wholesale distribution, Baltics" \
  --output-dir output/

# 5. Full pipeline from config
cp config/client_template.yaml config/acme.yaml
# Edit config/acme.yaml
tqm run config/acme.yaml
```

---

## Power BI deployment

### Service Principal setup

1. Register an app in Azure AD → note `tenant_id`, `client_id`, `client_secret`
2. In Power BI Admin Portal → enable "Service principals can use Power BI APIs"
3. Add the service principal to your workspace as **Member**
4. Set env vars in `.env`

```bash
tqm deploy sample_data/sales_2024_03.csv \
  --dataset-name "Acme Sales" \
  --workspace-id $PBI_WORKSPACE_ID
```

### Measure deployment (Tabular Editor)

After `tqm dax` generates `output/measures.cs`:

```bash
TabularEditor.exe "powerbi://api.powerbi.com/v1.0/myorg/MyWorkspace" \
  "Acme Sales" -S output/measures.cs
```

---

## Monthly retainer workflow

```
Day 1 of month:
  1. Client drops new Excel/SAP export in shared folder
  2. tqm run config/client.yaml
  3. PDF report + HTML email delivered to CEO and CFO
  4. Power BI dataset refreshed with new data

That's it.
```

---

## Configuration

See `config/client_template.yaml` for all options.

Key fields:

```yaml
client_name: "Acme SIA"
client_profile: |
  Latvian wholesale, B2B, Baltic market.
  KPIs: revenue, margin%, top customers.
current_file: "data/acme/2024_03.xlsx"
previous_file: "data/acme/2024_02.xlsx"
email_to: [ceo@acme.lv, cfo@acme.lv]
```

---

## Tests

```bash
pip install -e ".[dev]"
pytest -v
```

---

## Docker

```bash
docker compose build
docker compose run --rm tqm report data/cur.csv data/prev.csv \
  --client-name "Acme SIA" -o /app/output
```

---

## Acceptance criteria before automated delivery to a paying client

These are the conditions under which you can sleep at night. Not before.

### Negative gates (block bad output)
- [ ] Schema drift check passes — no missing columns, no type regressions
- [ ] Date column validated — correct period coverage, no ambiguity (`date_column` set in config)
- [ ] DAX static validation passes — zero syntax errors
- [ ] Review gate passes — no `ANOMALOUS_DELTA`, `NO_CITATIONS`, `DIRECTION_CONFLICT`, `NUMERIC_MISMATCH`
- [ ] `FALLBACK_COMMENTARY` not triggered — API was reachable during generation
- [ ] DPA in place — client has signed sub-processor disclosure covering Anthropic (see FM-07)

### Positive verifications (confirm good output)
- [ ] **Golden tests bootstrapped and signed off** — client has verified the reference-period numbers
- [ ] **First 3 reports reviewed by a human analyst** before automated send is enabled per client
- [ ] **Root cause claims manually checked** for first 6 months — every `evidence_kpi` maps to a real
      column the client can open in their Excel file
- [ ] **Audit log entry exists** for this run — source hash, prompt hash, gate result retained

### FMEA status
Run `python scripts/fmea_report.py` before each new client onboarding.
Currently open high-RPN failure modes (must be mitigated before automated delivery):

| ID | RPN | Failure Mode | Mitigation |
|----|-----|-------------|------------|
| FM-02 | 252 | Fabricated root cause | Human review every RCA for 6 months (process control) |
| FM-01 | 144 | Magnitude mismatch in prose | Golden tests on first 3 reports |
| FM-06 | 135 | DAX wrong filter context | Golden tests (two-analyst signoff required) before first deploy |
| FM-10 | 135 | Prompt injection via free-text field | `PromptSanitizer` + `<client_data>` framing + system guard |

Recently closed:

| ID | Old RPN | New RPN | Closed by |
|----|---------|---------|-----------|
| FM-07 | pending | 30 | `--confirm-dpa` flag required by `tqm report` for email delivery. Without it, CLI exits 1 before any API call is made. |
| FM-09 | 252 | 56 | Structured `KeyFinding(kpi_id, direction, magnitude_pct, context)` — LLM fills tuple, code renders prose. Five gate checks. |
| FM-12 | 96 | 48 | `ROW_COUNT_DROP` gate blocks at <70% of previous rows; `ROW_COUNT_LOW` warns at 70–85%; `ROW_COUNT_SPIKE` warns at >150%. |
| FM-13 | 72 | 48 | `period_days` computed from actual date coverage in `MonthlySnapshot`; `PERIOD_LENGTH_MISMATCH` gate warns on ≥2-day diff, blocks on ≥7. |

### On XMLA + Linux CI
The XMLA deployment path (`powerbi/xmla.py`) requires:
- Power BI Premium Per User (PPU) or Premium capacity on the target workspace
- .NET runtime accessible to Tabular Editor CLI
- Post-deploy verification: query `Information_Schema.MEASURE_NAME` via XMLA to assert measure count

On Linux CI this is reliably rough. If you can't confirm post-deploy measure count, treat every DAX
deploy as unverified and re-run golden tests manually from DAX Studio before the report runs.

### On data privacy (GDPR / DPA)
Customer names, transaction amounts, and segment labels are personal or commercially sensitive data.
Before sending any client data to the Anthropic API:
1. Confirm Anthropic is listed as a sub-processor in your DPA with the client
2. Anthropic's DPA: https://www.anthropic.com/legal/dpa
3. Consider hashing customer names in the prompt context (`customer_hash` instead of `"Rimi Latvia"`)
4. Data does not leave the EU under Anthropic's EU endpoint — confirm region is set correctly

### Operational documents

- [`docs/analyst_hiring.md`](docs/analyst_hiring.md) — Role spec for the second-analyst verification position. Required for `GoldenSuite` signoff. Defines independence, compensation that doesn't create rubber-stamp pressure, and turnover handling.
- [`docs/clean_month.md`](docs/clean_month.md) — Seven-criterion definition of a clean month. Required for Spot-Check tier eligibility. Includes the `ClientCorrection` schema, the rolling-window rule, and the retroactive-downgrade policy.

### Gate verification

```bash
# Mutation test: deliberately corrupt the baseline commentary in 10 ways
# and verify the gate catches each.
pytest tests/test_gate_mutations.py -v

# Or as a one-shot CLI report (planned):
# tqm mutate-gate
```

The mutation registry lives in `src/tqm/ai/mutations.py`. When you change the
gate or the prompt, run this. A gate hole here is a release blocker.

---

## Why this beats a vanilla AI agency

| Capability | Average AI agency | TQM |
|-----------|-------------------|-----|
| Reads SAP pipe-delimited exports | ✗ | ✓ |
| Generates correct DAX, then verifies it | ✗ | ✓ |
| Knows Latvian business context | ✗ | ✓ |
| Structured findings — LLM fills tuples, code writes prose (closes FM-09) | ✗ | ✓ |
| Structured root cause with cited evidence | ✗ | ✓ |
| Number reconciliation between prose and source | ✗ | ✓ |
| Per-client volatility thresholds | ✗ | ✓ |
| FMEA register with RPN scores | ✗ | ✓ |
| Two-analyst golden test signoff | ✗ | ✓ |
| Immutable audit log for dispute resolution | ✗ | ✓ |
| Honest about what's automated and what isn't | ✗ | ✓ |

---

## Pricing model (managed retainer)

Pricing reflects analyst review hours, not compute. AI is leverage on analyst time, not a replacement for it.

| Tier | Deliverables | Analyst review | Price |
|------|-------------|---------------|-------|
| **Reviewed** | 1 dashboard + monthly PDF, every report reviewed by analyst, 15-min walk-through call | ~2 h/mo | €690/mo |
| **Reviewed Plus** | 3 dashboards + reports + email delivery + 30-min CFO call | ~5 h/mo | €1,290/mo |
| **Audit Trail** | Unlimited dashboards + weekly mid-month updates + Slack alerts + full audit log access | ~10 h/mo | €2,490/mo |
| **Spot-Check** (after 6 clean months) | Reviewed tier with spot-check (every 3rd report only) | ~0.5 h/mo | €390/mo |

Setup fee: **€2,500–4,500** (one-time). Covers ingestion build, schema mapping, initial dashboard, golden test seeding by one analyst, independent verification by a second, and client signoff. Without this, the production gate refuses to run.

The €390 Spot-Check tier is what most clients eventually settle into. The path there is six months of reviewed delivery so we both trust the pipeline.
