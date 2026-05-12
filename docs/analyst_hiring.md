# Analyst-2 Hiring Plan — Independent Verification Role

The two-analyst rule on `GoldenSuite` (`signoff.verified_by` must differ from `signoff.seeded_by`) requires an actual second person. This document defines who they are, what they do, and what they cannot do.

Without this role staffed, **no client can move past the bootstrap step**. `GoldenSuite.compare()` will raise `GoldenSuiteUnsignedError` and the pipeline will not deliver.

---

## 1. Role definition

**Title:** Reporting Analyst II (Verification)

**Reports to:** Operations lead (not the analyst who seeded the suite, ever).

**Primary responsibility:** Independently reproduce every value in a freshly-seeded `GoldenSuite` from the client's raw data, using Power BI or DAX Studio, without reference to the seeding analyst's working notes. Sign `verified_by` only when each value matches within tolerance.

**Secondary responsibilities:**
- Read every `root_cause_analysis` from generated reports for the first 6 months of each new client (FM-02 process control).
- Spot-check `key_findings` rendering against source data on a random sample of reports.
- Maintain the client's `synonyms.yaml` file when domain terminology shifts.
- Co-sign any change to the live golden suite (`verified_by` re-attestation required).

---

## 2. Independence requirements

The verification analyst must not be the same person who:
- Seeded the golden suite (`signoff.seeded_by`)
- Ingested or transformed the client's data
- Wrote the AI prompt or client_profile
- Has commission or revenue exposure to that specific client account

This is segregation-of-duties, not paranoia. The seeder/verifier collapse is exactly the failure mode that breaks two-eyes review.

If the team has only two analysts and both must work on every client, rotate roles per client: Alice seeds Client A and verifies Client B; Bob seeds Client B and verifies Client A. Document the rotation in the audit log via `signoff.seeded_by` / `signoff.verified_by` emails.

---

## 3. Required skills

Mandatory:
- Read SAP exports or equivalent ERP outputs without hand-holding.
- Write basic DAX (`SUMX`, `CALCULATE`, `DIVIDE`, `SAMEPERIODLASTYEAR`) — not generate, but read and verify.
- Understand the difference between gross margin, contribution margin, and operating margin in Latvian accounting practice.
- Spot a misclassified column in 30 seconds (currency reported in thousands vs. units, sign convention differences, period boundary off-by-one).

Strongly preferred:
- Latvian + English. The client conversations are in Latvian; the audit log and code are in English.
- Power BI desktop experience.
- Audit or controlling background (one prior role in finance ops, internal audit, or controlling at a Latvian SME).

Disqualifying:
- Cannot resist the urge to "tidy up" a DAX expression while verifying it. Verification means reproducing the result on the data; modifying the measure invalidates the signoff.
- Treats AI-drafted commentary as authoritative input rather than a draft to be checked.

---

## 4. Compensation structure

This is the most consequential design choice. Get it wrong and you have rubber-stamping built into the role.

**Do NOT use:**
- Per-report-shipped commission. Creates direct pressure to wave reports through.
- Bonus tied to client retention. Creates pressure to soften negative findings.
- Bonus tied to clients onboarded. Creates pressure to rush verification.

**Do use:**
- Flat hourly or salaried rate.
- Quarterly bonus tied to **zero post-delivery client corrections** for the analyst's verified clients. A correction is logged via `ClientCorrection` (see `clean_month.md`). The bonus rewards refusing to sign off on numbers that don't reconcile, not pushing them through.
- Bonus is forfeited for the quarter if any signed-off suite produces a delivered report that the client later corrects on a numerical fact. This is harsh on purpose.

---

## 5. Day-1 to Day-30 training

| Day | Task | Sign-off |
|-----|------|----------|
| 1 | Read FMEA register (`config/fmea.yaml`). Walk through every open mode with operations lead. | Verbal |
| 2-3 | Run the full pipeline end-to-end on `sample_data/`. Generate a report, read every gate flag. | `tqm report` log review |
| 4-5 | Pair with the seeding analyst on a reference dataset. Reproduce every golden value independently in Power BI. | Both analysts present |
| 6-10 | Shadow-verify a real client's golden suite. Output goes nowhere — comparison against the live seeded values shows whether the trainee catches what they should. | Operations lead reviews discrepancies |
| 11-30 | Co-verify on every new client. Trainee's signoff doesn't count yet — the senior analyst countersigns. | `signoff.verified_by` = senior; trainee shadowed |
| 31+ | Solo verification permitted on new clients only. The first three solo verifications get a senior re-check after delivery. | Solo on `signoff.verified_by` |

---

## 6. Turnover handling

If the verification analyst leaves the company:

1. **All client suites they verified become unsigned** from a trust perspective even though the YAML still has their name. This is policy, not code.
2. A successor must re-verify each client's golden suite within 60 days, or that client is downgraded from automated-after-signoff back to fully reviewed delivery until re-verification completes.
3. The departing analyst's last action should be a written knowledge transfer covering the synonym tables, the audit log oddities, and any informal client-specific calibrations.
4. The CLI exposes `tqm signoff status --analyst <email>` to list every suite signed by that analyst, scoped by client.

---

## 7. Conflict-of-interest declaration

Annually, every verification analyst signs:

- I do not hold shares or directorships in any TQM client company.
- I do not have a relative employed by any TQM client company in a finance role.
- I will declare any consulting work outside TQM that could create a perceived conflict.
- I have not been offered or solicited to soften findings for any client.

Filed with the operations lead. Renewed each January. A "yes" answer doesn't disqualify automatically — it disqualifies from verifying that specific client.

---

## 8. What this role is not

- Not a junior DAX developer. The seeding analyst can do that; this person verifies.
- Not a customer-facing role. CSMs handle client communication.
- Not first-line support for pipeline bugs. Engineering owns that.
- Not a fallback for the seeding analyst when they're on holiday — that defeats independence.

When this role is vacant, golden test signoffs cannot be issued. New clients cannot be onboarded past the bootstrap step. Existing automated-tier clients revert to fully reviewed delivery on their next monthly run.
