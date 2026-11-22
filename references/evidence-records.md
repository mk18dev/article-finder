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
  "url": "https://example.org/replace-with-real-source",
  "note": "Describe exactly what was checked"
}
```

The note must be at least eight non-whitespace characters. The URL must be
HTTPS. Specialization and degree evidence also require a source URL and reviewer
note. The one documented exception is the legacy official blacklist host
`http://impactfactor.ir/`, which the CLI permits only on the S6 blacklist
evidence field because the course source identifies that HTTP-only endpoint.
A non-empty string or an unchecked claim is not evidence.

## Plan fields

Every entry starts with:

- `doi`: DOI of the candidate source.
- `category`: `concept`, `challenge`, `application`, or `methodology`.
- `keyword`: the exact course-keyword + research-keyword pair used.
- `search_evidence`: `query` (must equal `keyword`), `doi` (must match the
  Crossref DOI), `url` (the real search-result page), and `searched_at`
  (timestamp or date).
- `specialized`: an explicit boolean plus `specialization_evidence` (reviewed
  URL and note); missing either is pending, false fails S8.
- `tier`: provisional A-D; it is not trusted without `tier_evidence`.
- `tier_evidence`: `verified: true`, `url`, and `basis` explaining the
  evidence/rubric used to assign the tier.
- `area` and `subject`: labels only; S1/S2 need matching records under
  `judgements`.
- `degree_evidence`: thesis degree confirmation with a reviewer URL and note;
  an accepted degree label alone cannot pass S4.
- `judgements`: S1, S2 and S10 use `ok`, `reviewed: true`,
  `evidence_url`, and `note`. Books and theses also need a reviewed S5
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

### S6 — blacklist and indexing

A blacklist hit is a hard rejection. A clear result only permits further
checking; S6 passes only when a documented blacklist check and at least one
verified index record are supplied.

```json
"blacklist_status": "clear",
"blacklist_evidence": {
  "reviewed": true,
  "url": "http://impactfactor.ir/",
  "note": "Checked the relevant national and university blacklist"
},
"indexing_evidence": [
  {
    "index": "Scopus",
    "verified": true,
    "url": "https://example.org/replace-with-index-record",
    "note": "Confirmed the journal title and coverage period"
  }
]
```

Accepted index labels in this release: `Scopus`, `Web of Science`/`WoS`,
`ISC`, and `DBLP`. DOAJ membership alone is not a substitute for one of
these. The script validates the evidence shape, not the remote page's truth;
the reviewer must actually inspect it.

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

Every required field is an evidence item with `reviewed`, a real HTTPS URL,
and a short note.

- Journal/conference, Concept/Challenge/Application:
  `abstract`, `introduction`, `conclusion`.
- Book/thesis, Concept/Challenge/Application: `chapter_1`, `chapter_2`.
- Methodology, any supported source type: `full_text`.

The script records the reviewer's attestation; it does not parse a PDF and
prove that the material was read. Do not record a section as reviewed unless
you actually inspected it.

## What this does not automate

The CLI does not execute database searches, inspect Clarivate/Scopus pages,
read a paper, or independently determine a journal's blacklist status. It
stores the evidence path and enforces that a required review record exists.
A reviewer remains responsible for the correctness of each attestation.
