---
name: article-finder-literature-synthesis
description: Build reviewer-extracted evidence matrices, thematic summaries, conflict maps, and claim-to-source links without inventing findings or effect estimates.
---

# Literature Synthesis Skill — Article Finder 1.1.0

Use `scripts/synthesize_literature.py` with a reviewer-extracted JSON bundle.

- Extract design, population, method, outcomes, direction, findings, limitations, and quality appraisal from full text, or label the review as abstract-only/metadata-only.
- Every full-text extraction and quality rating needs reviewed HTTPS evidence, a locator, and a concise note.
- Group by declared themes; preserve positive, negative, null, mixed, and unclear findings separately.
- Flag conflicting directions, single-study themes, missing full-text review, and missing quality appraisal.
- Map each manuscript claim to study IDs and a reviewed excerpt plus locator from every linked study.
- Keep unsupported claims Pending. Do not create synthesis from titles or abstracts.
- Direction counts are descriptive, not effect sizes, significance tests, or meta-analysis.
- Research gaps are reviewer judgments, not automatic conclusions.

Output: evidence matrix, theme summaries, conflict flags, claim map, and methodological limitations.
