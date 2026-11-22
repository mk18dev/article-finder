---
name: article-finder-citation-verification
description: Audit DOI/title/year/author identity, flag Crossref correction and retraction records, and keep uncertain citations pending.
---

# Citation Verification Skill — Article Finder 1.1.0

Use `scripts/verify_citations.py` on a bibliography JSON file.

- Compare DOI, title, year, and first-author metadata with Crossref.
- If DOI is absent, return candidate DOI matches as Pending; never auto-replace a citation.
- Flag title/year/author mismatches and recorded corrections or retractions.
- A metadata identity match does not establish that the source supports the cited claim.
- No Crossref update record is not proof that no correction or retraction exists.
- Confirm high-risk notices on the publisher page and preserve the notice DOI.
- Do not silently delete or rewrite questionable citations; report the mismatch and request reviewer action.

Output: per-citation status, metadata comparison, update links, and limitations.
