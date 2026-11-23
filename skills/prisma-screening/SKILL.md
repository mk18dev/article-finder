---
name: article-finder-prisma-screening
description: Freeze systematic-review protocols, manage duplicate and screening ledgers, reconcile PRISMA 2020 counts, and generate auditable flow reports.
---

# PRISMA Screening Skill — Article Finder 1.1.0

Use `scripts/prisma_review.py`, `references/prisma-review.md`, and `examples/prisma-review.json`.

1. Freeze review type, question, eligibility criteria, databases, date range, language, reviewer IDs, dual/single screening policy, and registration before screening. A single-reviewer protocol requires a written justification.
2. Save database/register searches in `search_log`; save websites, organisations, and backward/forward citation searching in `other_methods_log`. Preserve valid HTTPS result URLs with a real host, exact `YYYY-MM-DD` dates, actual retrieved counts, and limits.
3. Preserve raw provider records (not only the deduplicated result set). The ledger deduplicates using a valid DOI, PMID, normalized URL, then normalized title; malformed DOI values are not deduplication keys. The report must retain duplicate-to-canonical links and metadata conflicts.
4. Record each title/abstract and full-text decision with reviewer ID and timezone-aware timestamp. Dual screening requires two independent reviewers and an adjudication record when they disagree.
5. Every full-text exclusion needs one controlled reason and a record ID.
6. AI suggestions are not reviewer decisions. Reviewer decisions, identity, and timestamps must be explicit.
7. Derive counts directly from raw records and screening decisions; manually supplied totals are only accepted as assertions and must match the derived values.
8. Generate the PRISMA-style flow and report; reconcile database, register, and other-method identification inputs before calling it complete.
9. Record protocol deviations and missing reports. A diagram alone does not prove PRISMA compliance.

If records or decisions are incomplete, report the missing ledger fields and keep the flow Pending.
