---
name: article-finder-source-verification
description: Apply the 11 evidence gates to DOI sources, preserve provenance, rank conservatively, and keep unsupported claims pending.
---

# Source Verification Skill — Article Finder 1.1.0

Use `scripts/verify_source.py` and the Mode 1 workflow.

- Validate DOI syntax and resolver host before metadata requests.
- Execute S1–S11 in order; do not mark a gate passed until evidence is observed.
- Store every manual judgment with HTTPS evidence URL, reviewer note, and timestamp.
- Crossref/OpenAlex metadata can support identity and bibliographic fields; it cannot prove indexing, peer review, or content relevance by itself.
- Check indexing at the authoritative registry for the claimed year and exact title.
- Any unknown gate keeps the source Pending, never Approved.
- Record corrections, retractions, inaccessible pages, conflicting metadata, and missing full text.
- Render APA/IEEE output only from verified fields; never fill missing fields from memory.

Output: 11-gate checklist, source tier, evidence links, errors, and formatted reference.
