# Citation integrity — Article Finder 1.1.0

Citation integrity has two separate checks. Passing one does not imply passing the other.

## 1. Bibliographic identity and update notices

Run:

```bash
python3 scripts/verify_citations.py bibliography.json --format markdown
```

The verifier compares DOI, title, publication year, and first-author family name against Crossref metadata. It flags recorded correction, erratum, retraction, withdrawal, and expression-of-concern relations.

Interpretation:

- `verified`: supplied identity fields match the returned Crossref record; it does not prove claim support or scientific quality.
- `mismatch`: one or more supplied identity fields disagree.
- `corrected`: a correction relation is recorded; inspect the notice and affected claims.
- `retracted`: a retraction/withdrawal/expression-of-concern signal is recorded.
- `pending`: DOI or metadata is missing, unavailable, or not comparable.

A DOI-less candidate is never auto-inserted into the bibliography. No Crossref update record is not proof that no notice exists; inspect the publisher and other authoritative sources.

## 2. In-text citation and bibliography crosswalk

Run:

```bash
python3 scripts/citation_crosswalk.py manuscript.txt references.json --style APA
python3 scripts/citation_crosswalk.py manuscript.txt references.json --style IEEE
```

The crosswalk reports:

- APA author-year citations or IEEE numeric/range citations missing from the bibliography
- bibliography entries never cited in the manuscript body
- duplicate DOI and APA author-year keys
- malformed or unsupported citation patterns
- bibliography text excluded from the in-text citation scan

The crosswalk is deterministic and intentionally conservative. It does not parse every citation style, footnote convention, group-author exception, or complex narrative syntax. Resolve ambiguous names and unsupported patterns manually; do not treat a parser's `pass` as proof of scholarly correctness.

## Claim support remains a human evidence task

Neither metadata identity nor an in-text/reference match proves that a paper supports the sentence where it is cited. Use the literature evidence matrix and claim-to-source map for that separate question. Every claim needs a reviewed excerpt and locator from the actual source.
