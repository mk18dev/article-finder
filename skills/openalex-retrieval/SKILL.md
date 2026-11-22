---
name: article-finder-openalex-retrieval
description: Use OpenAlex Works metadata for scholarly discovery, DOI normalization, author and venue mapping, and retraction signals.
---

# OpenAlex Retrieval Skill — Article Finder 1.1.0

- Search through `scripts/search_databases.py`; never construct user-controlled hosts or arbitrary API URLs.
- Preserve the OpenAlex query URL, exact query, retrieval date, page limit, returned count, and provider status.
- Keep OpenAlex work IDs, DOI, authorships, publication year, primary location, and `is_retracted` signal distinct.
- Normalize DOI values before cross-provider deduplication; preserve which provider supplied each field.
- If OpenAlex fails while Crossref succeeds, report partial coverage and retain the failed-provider log.
- Treat missing or conflicting metadata as Pending. OpenAlex presence does not prove indexing, peer review, or journal quartile.
- Recheck retraction/correction signals against publisher and Crossref records before final decisions.

Output: candidate records, provenance, and explicit partial-failure warnings.
