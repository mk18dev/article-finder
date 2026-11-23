# Phase 3–5 — Acceptance and regression matrix

Scope: Article Finder 1.1.0, the existing `main` branch. These matrices describe automated coverage only; they do not replace human review or a successful final CI run.

## Phase 3 — Citation Identity, Update & Crosswalk

Implementation:
- `scripts/verify_citations.py`
- `scripts/citation_crosswalk.py`

Current focused regression inventory:
- `tests/test_verify_citations.py`: 28 test methods.
- `tests/test_citation_crosswalk.py`: 21 test methods.

Acceptance coverage:
- DOI normalization and resolver hardening; malformed/non-official DOI resolver URLs remain rejected.
- Crossref metadata identity: DOI, title, first author, year, venue and publisher.
- Missing/incomplete metadata and network failures remain Pending.
- Duplicate DOI records are surfaced; candidate DOI matches without a supplied DOI are not auto-approved.
- Correction, erratum, retraction, withdrawal and expression-of-concern signals are surfaced with notice references.
- APA author-year and IEEE numeric/range crosswalks detect missing in-text references, uncited bibliography entries, duplicate keys and malformed syntax.
- Persian/Arabic-Indic digits, Persian/Arabic author variants and Unicode normalization are covered.
- IEEE bibliography identifiers are positive integers only; zero, negative, boolean, fractional and malformed values are rejected.

Recent edge-case additions:
- `test_rejects_unsafe_doi_resolver_components`
- `test_first_author_mismatch_is_not_verified`
- `test_missing_expected_title_stays_pending`
- `test_ieee_reference_numbers_must_be_positive_integers`
- `test_persian_ieee_bibliography_number_is_normalized`

## Phase 4 — Draft Quality Engine (76 Rules)

Implementation:
- `scripts/check_draft.py`
- Source mapping: `references/writing-article.md`

Current focused regression inventory:
- `tests/test_check_draft.py`: 36 test methods.
- `tests/test_rule_acceptance_matrix.py`: 11 acceptance tests.

Acceptance coverage:
- All 76 rule IDs are unique, emitted exactly once, assigned to a valid section and mapped to a source Step/Page.
- Every automatic rule has a positive case, a negative case and a boundary case with an asserted expected verdict.
- Every manual rule defaults to Pending, accepts explicit human True/False decisions, and never turns a non-boolean value into approval.
- Every hint rule remains non-approved without human confirmation; its evidence detail is data-sensitive and both explicit human verdicts are covered.
- Missing sections fail closed for every rule.
- Persian/English rendering, localized details, citation detection, table/figure counting, and chart-review behavior remain covered by the existing regression suite.

The matrix intentionally does not claim to automate subjective rules. A human decision is required for all Manual and Hint rules.

## Phase 5 — PRISMA, Screening Ledger & Literature Synthesis

Implementation:
- `scripts/prisma_review.py`
- `scripts/synthesize_literature.py`
- Operating references: `references/prisma-review.md`, `references/evidence-records.md`

Current focused regression inventory:
- `tests/test_prisma_review.py`: 25 test methods.
- `tests/test_synthesize_literature.py`: 10 test methods.

Acceptance coverage:
- Frozen protocol, documented search strategy, exact calendar dates and valid HTTPS search origins.
- Raw retrieved record totals must reconcile to completed database, register and other-method hits.
- Valid DOI/PMID/URL/title deduplication order, canonical links, metadata conflicts and malformed DOI rejection.
- Dual reviewers must be independent; disagreement requires a separate adjudicator and note; single-reviewer mode requires justification.
- Title/abstract and full-text exclusion reasons are mandatory; included reports require stable study IDs.
- PRISMA counts are derived from the raw ledger; tampered supplied counts fail.
- Database, register and other-method streams remain distinct; included studies and included reports remain separate.
- Generated reports include a duplicate-resolution ledger with canonical record and metadata-conflict trace.
- Full-text extraction, quality appraisal and claim-to-source evidence require reviewed source evidence, a valid HTTPS origin, excerpt/note and non-empty locator.
- Claim evidence must uniquely map to studies linked by that claim; unknown and duplicate evidence IDs fail.
- Thematic synthesis preserves conflicting directions, quality/coverage flags, unsupported claims as Pending, and methodological limitations.

Recent edge-case additions:
- `test_search_url_requires_real_https_origin`
- `test_search_date_requires_exact_iso_calendar_date`
- `test_other_methods_url_and_date_are_validated`
- `test_report_preserves_duplicate_links_and_metadata_conflicts`
- `test_malformed_dois_do_not_become_deduplication_keys`
- `test_claim_evidence_requires_valid_https_origin_and_locator`
- `test_claim_evidence_must_be_unique_and_linked`
- `test_claim_study_ids_must_be_unique`

## Final acceptance rule

A phase is DONE only after:
1. The implementation and its documentation are read back from the current `main` HEAD.
2. Its targeted positive, negative, incomplete and boundary tests pass.
3. The full supported CI matrix for the exact current HEAD is complete and green.
4. No required browser or release gate is silently treated as passed when it was skipped or cancelled.

A previous green run on an ancestor commit is baseline evidence only. It does not certify later changes.
