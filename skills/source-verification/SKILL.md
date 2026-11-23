---
name: article-finder-source-verification
description: Apply the 11 evidence gates to DOI sources, preserve provenance, rank conservatively, and keep unsupported claims pending.
---

# Source Verification Skill — Article Finder 1.1.0

Use `scripts/verify_source.py` and the Mode 1 workflow.

- Validate DOI syntax and resolver host before metadata requests.
- Execute S1–S11 in order; do not mark a gate passed until evidence is observed.
- Store every manual judgment with HTTPS evidence URL, reviewer ID, timezone-aware timestamp, page/section locator, and reviewer note.
- Compute A/B/C/D using scripts/tier_policy.py; do not trust a manually typed tier. A declared/computed mismatch fails S9. Book citation thresholds are configurable in scripts/tier-policy.json.
- For journal S6, require three separate ISSN lookups: MSRT, MOHME, and IAU. Each must record status, list version, reviewer, timestamp, official URL, locator, and note. A verified hit from any official authority hard-rejects; missing or stale lists remain pending. ImpactFactor is only a secondary signal.
- Crossref/OpenAlex metadata can support identity and bibliographic fields; it cannot prove indexing, peer review, or content relevance by itself.
- Check indexing at the authoritative registry for the claimed year and exact title. Every positive indexing_evidence record must include matched_title equal to the Crossref title after case/spacing/punctuation normalization, plus integer coverage_start_year and coverage_end_year containing the publication year. S6 accepts evidence URLs only from the official registry host allowlist; host match is not proof that the page content was read.
- Conference proceedings accept Scopus, Web of Science/WoS, ISC or DBLP evidence only; DOAJ is a journal directory and cannot satisfy conference S6.
- The Phase 2 acceptance matrix is documented in references/phase2-test-matrix.md; keep positive, negative, incomplete and contradictory cases aligned with the test suite.
- Any unknown gate keeps the source Pending, never Approved.
- Record corrections, retractions, inaccessible pages, conflicting metadata, and missing full text.
- Render APA/IEEE output only from verified fields; never fill missing fields from memory.

Output: 11-gate checklist, source tier, evidence links, errors, and formatted reference.
