---
name: article-finder-systematic-search
description: Run reproducible scholarly searches across Crossref and OpenAlex and preserve exact query provenance.
---

# Systematic Search Skill — Article Finder 1.1.0

1. Freeze the review question, concepts, inclusion/exclusion criteria, and search date before searching.
2. Preserve the exact query verbatim; do not silently rewrite it after seeing results.
3. Run `python3 scripts/search_databases.py "EXACT QUERY" --limit 20 --providers crossref,openalex -o search-results.json`.
4. Inspect provider status independently. A partial provider failure must remain visible and be rerun before claiming complete coverage.
5. Preserve `search_log`, `search_url`, date, actual retrieved count, total available count, and limits. Never substitute total available for retrieved records.
6. Deduplicate with the PRISMA ledger's documented DOI/PMID/URL/title rules; preserve duplicate-to-canonical links and conflicts.
7. Treat every result as a candidate. Search rank, DOI presence, and metadata do not establish relevance, quality, or eligibility.

Output: exact query log, provider status, raw/deduplicated counts, candidate records, and unresolved retrieval gaps.
