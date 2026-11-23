---
name: article-finder-citation-verification
description: Audit DOI/title/year/author identity, flag Crossref correction and retraction records, and keep uncertain citations pending.
---

# Citation Verification Skill — Article Finder 1.1.0

Use `scripts/verify_citations.py` on a bibliography JSON file and `scripts/citation_crosswalk.py` on manuscript text plus a structured reference list.

- Compare DOI, title, year, first-author metadata, and supplied venue/publisher fields with Crossref; preserve the Crossref record URL and update-notice DOI URLs.
- Cross-check APA author-year or IEEE numeric citations against the bibliography; report missing in-text entries, uncited references, duplicate DOI/author-year keys, and malformed citations. IEEE bibliography identifiers must be positive integers; zero, negative, fractional, boolean, or malformed values require review. Normalize Persian/Arabic-Indic digits and Unicode author-name variants, including Arabic/Persian yeh/kaf and zero-width non-joiner.
- If DOI is absent, return candidate DOI matches as Pending; never auto-replace a citation.
- Flag title/year/author mismatches and recorded corrections or retractions.
- A metadata identity match does not establish that the source supports the cited claim.
- No Crossref update record is not proof that no correction or retraction exists.
- Confirm high-risk notices on the publisher page and preserve the notice DOI.
- Cross-check APA author-year or IEEE numeric citations against the reference list; report missing bibliography entries, uncited references, duplicate DOI and duplicate author-year keys.
- Do not silently delete or rewrite questionable citations; report the mismatch and request reviewer action.

Output: per-citation status, metadata comparison, update links, APA/IEEE crosswalk, and limitations.
