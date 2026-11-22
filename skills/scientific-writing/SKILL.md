---
name: article-finder-scientific-writing
description: Review scientific article sections against course rules, validate measurable constraints, and separate automated checks from reviewer judgments.
---

# Scientific Writing Skill — Article Finder 1.1.0

Use `scripts/check_draft.py` and `references/writing-article.md`.

- Preserve the supplied draft; do not invent data, results, citations, or methods.
- Run deterministic checks first: word ranges, paragraph constraints, headings, table/figure counts, and reference formatting.
- Keep manual rules Pending until a reviewer records a boolean decision and a note pointing to the exact section.
- Distinguish course-specific style rules from universal scientific-writing standards.
- Return passed, failed, and pending rules separately, grouped by article section.
- Suggest revisions with the rule and reason; rewrite only when explicitly asked.
- Passing a checklist does not prove scientific validity, originality, or publication readiness.

Output: section-level report, rule IDs, concrete fixes, and unresolved reviewer decisions.
