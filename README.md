# TQM — AI-powered Power BI + DAX Automation for SMEs

> **The product:** Latvian SMEs have data sitting in Excel and SAP exports that no one is analyzing. TQM turns those files into a live Power BI dashboard and delivers a monthly management report — "here's what changed, here's why, here's what to do about it" — written by AI, reviewed by you.

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

## Why this beats a vanilla AI agency

| Capability | Average AI agency | TQM |
|-----------|-------------------|-----|
| Reads SAP pipe-delimited exports | ✗ | ✓ |
| Generates correct DAX (not hallucinated) | ✗ | ✓ |
| Knows Latvian business context | ✗ | ✓ |
| Explains *why* not just *what* | ✗ | ✓ |
| Push dataset → no PBIX needed | ✗ | ✓ |
| Prompt caching (fast + cheap at scale) | ✗ | ✓ |
| Fully automated monthly delivery | ✗ | ✓ |

---

## Pricing model (retainer)

| Tier | Deliverables | Price |
|------|-------------|-------|
| **Starter** | 1 dashboard + monthly PDF report | €490/mo |
| **Growth** | 3 dashboards + report + email delivery | €890/mo |
| **Scale** | Unlimited dashboards + weekly updates + Slack alerts | €1,890/mo |

Setup fee: €1,500–3,000 (one-time, covers ingestion build + initial dashboard).
