# PRISMA screening ledger — Article Finder 1.1.0

The PRISMA module validates a reviewer-attributed screening ledger and derives counts from raw records. It does not make eligibility decisions.

## Inputs

- `protocol.review_type`: `systematic` or `scoping`; narrative reviews must not be presented as PRISMA systematic reviews.
- `protocol.question`, `inclusion_criteria`, and `exclusion_criteria`: frozen before screening.
- `protocol.reviewers`: unique reviewer IDs. Dual screening is explicit; single screening requires a written justification.
- `search_log`: database/register name, platform, exact query, ISO date, HTTPS result URL, actual retrieved hits, limits, status, and `source_type` (`database` or `register`).
- `other_methods_log`: websites, organisations, backward/forward citation searching, or other methods, with method, date, HTTPS URL, hits, limits, and status.
- `records`: every raw record from all search streams. `source_type` is `database`, `register`, or `other_method`. Each record needs a stable `record_id` and title.

The total raw-record count must equal the sum of completed database/register search hits plus other-method hits. Partial provider failures cannot be counted as completed searches.

## Screening record

A record uses `title_abstract_review` and, when included at that stage, `full_text_status` and `full_text_review`.

Each screening review stores:

- `reviewer_id`
- `decision`: `include` or `exclude`
- `reviewed_at`: timezone-aware ISO-8601 timestamp
- `second_review`: an independent reviewer when dual screening is enabled
- `adjudication`: a third declared reviewer, timestamp, decision, and note when the first two reviewers disagree

Title/abstract exclusions require `title_abstract_exclusion_reason`. Full-text exclusions require `full_text_review.exclusion_reason`. Included reports require a stable `study_id`; multiple reports can map to one study.

## Derived counts

The validator derives:

- records identified from databases, registers, and other methods
- duplicates removed and automation exclusions
- records screened and title/abstract exclusions
- reports sought, not retrieved, and assessed
- full-text exclusions
- unique studies included and reports of included studies

If a `counts` object is supplied, each supplied value is compared with the ledger-derived value. It is never treated as the source of truth.

## Deduplication

The canonical key order is DOI, PMID, normalized URL, then normalized title. Duplicate links preserve the canonical `record_id`, key type, and any conflicting title/year/author/venue/publisher metadata. A conflict is not silently overwritten.

## Run

```bash
python3 scripts/prisma_review.py examples/prisma-review.json --format report
```

The bundled example is an empty placeholder. Replace it with actual raw search exports and reviewer decisions before interpreting any count.

## Scope limitation

The generated flow includes database, register, and other-method identification inputs, then aggregates records after global deduplication for screening. It is a PRISMA-style auditable flow, not a claim that every optional PRISMA 2020 diagram variant or multi-report study relationship is fully represented. Human reviewers remain responsible for protocol registration, screening decisions, exclusions, and final reporting.
