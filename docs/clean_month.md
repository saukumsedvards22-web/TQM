# Clean-Month Definition

The Spot-Check pricing tier (€390/mo) is available **only after 6 consecutive clean months** per client. Without a precise definition of "clean", the tier downgrade is a sales decision dressed up as an engineering one.

A month is **clean** for a client iff *all* of the following hold for that calendar month, in the audit log:

| # | Criterion | Source | Severity if violated |
|---|-----------|--------|---------------------|
| 1 | Zero gate blockers in any delivered report | `AuditEntry.gate_passed == True` for every `delivery="email:..."` entry | Hard fail |
| 2 | Zero `ClientCorrection` records logged for any report from this client | `corrections/<client>_corrections.jsonl` | Hard fail |
| 3 | Zero schema drift blocking events | `AuditEntry.schema_drift_clean == True` | Hard fail |
| 4 | Zero reruns producing different output on identical data hashes | Two entries with the same `source_data_hash` but different `response_hash` | Hard fail (pipeline non-determinism) |
| 5 | At least one delivery happened | At least one `AuditEntry` with `delivery` starting `email:` | Hard fail (vacancy is not "clean", it's "absent") |
| 6 | Golden test suite signoff remains complete | `GoldenSuite.signoff.is_complete()` at month end | Hard fail |
| 7 | No `FALLBACK_COMMENTARY` shipped (gate would have blocked, but defence in depth) | `"FALLBACK_COMMENTARY" not in [f.code for f in gate_flags]` for delivered entries | Hard fail |

A `ClientCorrection` is logged when a client disputes any number in a delivered report and the dispute is verified by an analyst. Records are append-only:

```jsonl
{"report_id": "abc123", "logged_at": "2024-05-12T10:00:00Z", "logged_by": "alice@tqm.lv",
 "field": "kpi_deltas.total_revenue.current", "claimed_value": 97650.0,
 "actual_value": 94200.0, "source_of_truth": "client_internal_sheet_q1.xlsx",
 "severity": "material"}
```

Severity is `material` (>2% of the field's magnitude) or `cosmetic` (≤2%). Both kinds break the month — the distinction exists for trend analysis, not for forgiveness. Cosmetic errors compound.

## Why each criterion exists

**Criterion 1 (zero blockers delivered).** A delivered report that triggered a gate blocker means someone overrode the gate. Even if the override was correct, the month is not clean — it required human judgement to ship. Spot-Check assumes the pipeline ships without judgement calls.

**Criterion 2 (zero corrections).** This is the only criterion the client can produce evidence for. The other six are internal. If you don't track corrections, you don't know if the pipeline works — you only know it ran.

**Criterion 3 (zero schema drift).** A drift blocker means the SAP export format changed. Even if you accommodated it, the underlying source system is no longer stable enough for unattended automation.

**Criterion 4 (determinism).** Two runs on the same data should produce the same output. The LLM's `temperature` defaults to >0, so this is achievable only when you've actively constrained the prompt. The criterion forces that constraint to be real, not aspirational.

**Criterion 5 (at least one delivery).** A "clean" month with zero deliveries is just a vacancy. Spot-Check is not the same as Skipped.

**Criterion 6 (signoff still complete).** Analyst departure invalidates suites (see `analyst_hiring.md`). The criterion forces re-verification within the 60-day window.

**Criterion 7 (no fallback shipped).** The gate should catch this, but if the fallback marker ever appeared in a delivered report, the entire pipeline is broken until investigated.

## When 6 clean months runs out

Spot-Check eligibility is **rolling**. Each month, recompute the most recent 6-month window. If any month in the window is now unclean (e.g. a correction was logged retroactively for a report from 4 months ago), the client is immediately downgraded from Spot-Check back to the Reviewed tier on the next billing cycle. The client receives notice with the specific failing criterion and report_id.

This is harsh on purpose. Spot-Check pricing assumes the pipeline is trustworthy. The moment that's no longer demonstrably true, the price returns to reflect the analyst hours that the trust required.

## What "clean" does NOT mean

- Does not mean the client is satisfied. Satisfaction is a CSM metric.
- Does not mean the report was correct, only that no one has yet disputed it. A correction logged in month 7 retroactively breaks month 4.
- Does not mean the pipeline didn't surface warnings — warnings are not blockers, and clean status tolerates them.
- Does not mean the analyst has zero work. Clean months still require: schema drift fingerprint verification, audit log review, monthly cost reconciliation.

## CLI integration

```bash
$ tqm tier-eligibility --client "Acme SIA"
Client: Acme SIA
Audit window: 2024-05-01 → 2024-10-31

Month     Clean?  Failed criterion (if any)
2024-05   ✓
2024-06   ✓
2024-07   ✗      Criterion 2: ClientCorrection logged for report abc123 on 2024-07-22
2024-08   ✓
2024-09   ✓
2024-10   ✓

6-month rolling window: NOT CLEAN (1 month failed)
Current tier eligibility: Reviewed (€690/mo)
Earliest possible Spot-Check eligibility: 2025-01-31 (if all months 2024-08 → 2025-01 are clean)
```

The CLI does not change the client's tier — that remains a billing decision. It produces evidence.
