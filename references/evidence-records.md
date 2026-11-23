# Evidence records for Mode 1

Release 1.1.0 uses **fail-closed** gates. Candidate metadata is retrieved from
Crossref/OpenAlex, but research judgements and browser-only checks must be
recorded by the agent/reviewer. Missing or malformed evidence means pending
(`null`), not pass (`true`). An explicit failed check means reject (`false`).

The example URLs below use reserved example domains. They are placeholders,
not proof. Replace every one with the page actually inspected; never copy them
into a real plan unchanged.

## Shared evidence shape

A reviewer-controlled item has this shape:

```json
{
  "reviewed": true,
  "reviewer_id": "reviewer-1",
  "reviewed_at": "2026-11-23T10:00:00Z",
  "url": "https://example.org/replace-with-real-source",
  "locator": "Results section, page 4",
  "note": "Describe exactly what was checked"
}
```

The note must be at least eight non-whitespace characters. Every manual evidence item requires a non-empty reviewer ID, a timezone-aware ISO-8601 `reviewed_at`, and a page/section/record `locator`. The URL must be HTTPS. Specialization and degree evidence also require a source URL and reviewer note. No HTTP blacklist exception is allowed. A non-empty string or an unchecked claim is not evidence.

## Plan fields

Every entry starts with:

- `doi`: DOI of the candidate source.
- `category`: `concept`, `challenge`, `application`, or `methodology`.
- `keyword`: the exact course-keyword + research-keyword pair used.
- `search_evidence`: `query` (must equal `keyword`), `doi` (must match the
  Crossref DOI), `url` (the real search-result page), and `searched_at`
  (timezone-aware ISO-8601 timestamp).
- `specialized`: an explicit boolean plus `specialization_evidence` (reviewed
  URL and note); missing either is pending, false fails S8.
- `tier`: optional declared A-D value; the application computes the tier from source-specific evidence and rejects a declared/computed mismatch.
- `tier_evidence`: `verified: true`, `reviewer_id`, `reviewed_at`, `locator`, `url`, and `basis` supporting the computed tier. The URL must be an official quartile/index/blacklist source for journals, publisher/index record for conferences, institutional repository for theses, or Google Books/Amazon record for books.
- Journal tier inputs: `quartile` (`Q1`-`Q4`) and `quartile_source` (`SJR` or `JCR`). The evidence URL must match that source when using quartile rules.
- Conference tier inputs: `conference_scope` (`international` or `national`) and boolean `conference_series_established`.
- Thesis tier inputs: `derived_papers_status` (`found` or `none`), reviewed `derived_papers_review`, optional `derived_papers` with verified DOI records and tier, `university_reputable`, and `university_evidence`.
- Book tier inputs: `main_book`, `relevant_chapters` plus `relevant_chapters_evidence`, and `book_s6_evidence` with publisher verification and integer citation count. The configurable default thresholds (50 strong / 10 modest) live in `scripts/tier-policy.json`.
- `area` and `subject`: labels only; S1/S2 need matching records under
  `judgements`.
- `degree_evidence`: thesis degree confirmation with a reviewer URL and note;
  an accepted degree label alone cannot pass S4.
- `judgements`: S1, S2 and S10 use `ok`, `reviewed: true`,
  `evidence_url`, `reviewer_id`, `reviewed_at`, `locator`, and `note`. Books and theses also need a reviewed S5
  judgement because their publisher/venue is not auto-approved from a simple
  Crossref publisher-name match.

## Gate-specific records

### S3 — actual search

```json
"search_evidence": {
  "query": "Survey + hybrid recommender systems",
  "doi": "10.3233/IDA-163209",
  "url": "https://example.org/replace-with-real-search-result",
  "searched_at": "2026-11-23T10:00:00Z"
}
```

The query must exactly match the recorded keyword pair and DOI. The script
checks the structure and match; it does not independently prove that a human
actually ran the search.

### S6 — type-specific validation

S6 follows a distinct source rule for each type. Example URLs below are
placeholders; replace them with the exact record you actually inspected.

**Journal:** a blacklist hit is a hard rejection. A clear result requires three
independent reviewer checks in `blacklist_checks`: `authority: "msrt"`,
`authority: "mohme"`, and `authority: "iau"`. Each entry must include `status: "clear"` or `"listed"`,
`query_type: "ISSN"`, a `query_value` matching the record's ISSN, a
`list_version`, reviewer ID, timezone-aware timestamp, HTTPS URL, locator and
note. A verified `listed` result from any of the three official authorities rejects S6,
even if the journal has a high tier. The IAU evaluation portal provides current
1405 evaluation/revocation status; it is not treated as a separate complete
blacklist download. The MOHME database linked by the IAU portal may be an older
snapshot; verify its list version before marking clear. If a current official
list cannot be located or is stale, record the check as unavailable and leave
S6 pending. A missing, inaccessible, malformed or
unverified result stays pending. After all three checks are clear, at least one
verified Scopus, Web of Science/WoS, ISC, DBLP or DOAJ record is required in
    `indexing_evidence`.

Illustrative journal blacklist-check structure (replace every version, URL and
locator with the exact current record you inspected; this is not a real
clearance result):

```json
"blacklist_checks": [
  {
    "authority": "msrt", "status": "clear", "query_type": "ISSN",
    "query_value": "0924-1868", "list_version": "replace-with-current-version",
    "list_updated_at": "2026-11-23",
    "reviewed": true, "reviewer_id": "reviewer-1",
    "reviewed_at": "2026-11-23T10:00:00Z",
    "url": "https://journals.msrt.ir/",
    "locator": "ISSN search result / exact record",
    "note": "No matching entry in the current official list"
  },
  {
    "authority": "mohme", "status": "clear", "query_type": "ISSN",
    "query_value": "0924-1868", "list_version": "replace-with-current-version",
    "list_updated_at": "2026-11-23",
    "reviewed": true, "reviewer_id": "reviewer-1",
    "reviewed_at": "2026-11-23T10:00:00Z",
    "url": "https://research.behdasht.gov.ir/",
    "locator": "ISSN search result / exact record",
    "note": "No matching entry in the current official list"
  },
  {
    "authority": "iau", "status": "clear", "query_type": "ISSN",
    "query_value": "0924-1868", "list_version": "replace-with-current-version",
    "reviewed": true, "reviewer_id": "reviewer-1",
    "reviewed_at": "2026-11-23T10:00:00Z",
    "url": "https://eval.journals.iau.ir/",
    "locator": "1405 evaluation / exact journal record",
    "note": "No revocation or invalidation marker in the current official record"
  }
]
```

**Conference:** verify the exact proceedings title and coverage years in
Scopus, Web of Science/WoS, ISC or DBLP using `indexing_evidence`. Each
positive record must include `matched_title`, `coverage_start_year` and
`coverage_end_year`. DOAJ cannot satisfy conference S6 because it is a
journal directory. The journal blacklist check does not apply to conference
proceedings.

**Thesis:** use `thesis_repository_evidence` with repository
`Irandoc`, `university repository`, or `institutional repository`, plus
`verified: true`, a source URL and note.

**Book:** use `book_s6_evidence` with source `Google Books` or `Amazon`,
a non-negative integer `citation_count`, `publisher_verified: true`,
`verified: true`, a source URL and note.

Example book record:

```json
"book_s6_evidence": {
  "source": "Google Books",
  "verified": true,
  "reviewer_id": "reviewer-1",
  "reviewed_at": "2026-11-23T10:00:00Z",
  "url": "https://books.google.com/books?id=replace-with-real-record",
  "locator": "Google Books bibliographic record",
  "note": "Book record, publisher and citation count were inspected",
  "citation_count": 27,
  "publisher_verified": true
}
```

The script validates evidence fields and official-host boundaries, not the truth
of the external page. MSRT blacklist evidence must use `journals.msrt.ir` or `msrt.ir`; MOHME evidence must use `research.behdasht.gov.ir` or `behdasht.gov.ir`; IAU evidence must use `eval.journals.iau.ir` or `iau.ac.ir`. The generated checklist links to the MSRT portal, MOHME journal database,
the IAU 1405 evaluation/revocation-status portal, and ImpactFactor as a
secondary aggregator. ImpactFactor is a lead only: its own notice says online
results require expert review and the receiving institution makes the final
decision. Journal
indexing URLs must use official provider domains: Scopus (`scopus.com`), Web of
Science (`mjl.clarivate.com` or `webofscience.com`), ISC (`isc.gov.ir`), DBLP
(`dblp.org`), or DOAJ (`doaj.org`). A URL such as
`scopus.com.attacker.example` is rejected.
For Irandoc, the evidence host must be `irandoc.ac.ir`. For a university or
institutional repository, provide `institution_domain` and use a URL on that
domain. Google Books evidence must use `books.google.com`; Amazon evidence
must use a supported Amazon country domain. A reviewer must still inspect the
actual record. DOAJ membership alone does not substitute for the required
journal/conference index evidence.

### S7 — identifiers by source type

- **Journal:** Crossref ISSN values must pass checksum validation; volume and
  issue must both be present. EISSN/PISSN classification and volume-number
  consistency still require source-page review.
- **Conference:** Crossref DOI and proceedings/container must exist, with
  `conference_edition`, `conference_venue`, and a `conference_evidence`
  record.
- **Book:** `main_book: true`, valid Crossref ISBN-10/ISBN-13, and
  `book_evidence`. A collection/chapter is not a main book.
- **Thesis:** degree + `degree_evidence`, `record_id`, `institution`, HTTPS
  `repository_url`, and `thesis_evidence`. Bachelor's theses are rejected at
  S4; master's and doctoral theses need explicit degree evidence.

### S11 — reading depth

Every required field is an evidence item with `reviewed`, `reviewer_id`, timezone-aware `reviewed_at`, a real HTTPS URL, a `locator`, and a short note.

- Journal/conference, Concept/Challenge/Application:
  `abstract`, `introduction`, `conclusion`.
- Book/thesis, Concept/Challenge/Application: `chapter_1`, `chapter_2`.
- Methodology, any supported source type: `full_text`.

The script records the reviewer's attestation; it does not parse a PDF and
prove that the material was read. Do not record a section as reviewed unless
you actually inspected it.

## What this does not automate

The source-verification CLI does not execute database searches, inspect Clarivate/Scopus page contents, read a paper, or independently determine a journal's blacklist status. The separate `search_databases.py` tool executes Crossref and OpenAlex retrieval. The verifier stores evidence paths and enforces the reviewer attestation shape; it does not authenticate page contents.
A reviewer remains responsible for the correctness of each attestation.
