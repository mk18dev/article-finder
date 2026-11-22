---
name: article-finder-prisma-screening
description: Freeze systematic-review protocols, manage duplicate and screening ledgers, reconcile PRISMA 2020 counts, and generate auditable flow reports.
---

# PRISMA Screening Skill — Article Finder 1.1.0

Use `scripts/prisma_review.py` and `examples/prisma-review.json`.

1. Freeze review type, question, eligibility criteria, databases, date range, language, reviewers, and registration before screening.
2. Save each executed query and HTTPS result URL, ISO date, actual retrieved count, and limits.
3. Preserve raw records. Deduplicate using DOI, PMID, normalized URL, then normalized title; keep duplicate-to-canonical links and metadata conflicts.
4. Keep records screened, title/abstract exclusions, reports sought, reports not retrieved, reports assessed, full-text exclusions, and included studies distinct.
5. Every full-text exclusion needs one controlled reason and a record ID.
6. AI suggestions are not reviewer decisions. Reviewer decisions, identity, and timestamps must be explicit.
7. Derive counts from the ledger; do not manually type arithmetic totals when records can be counted.
8. Generate the PRISMA-style flow and report; reconcile every branch before calling it complete.
9. Record protocol deviations and missing reports. A diagram alone does not prove PRISMA compliance.

If records or decisions are incomplete, report the missing ledger fields and keep the flow Pending.
