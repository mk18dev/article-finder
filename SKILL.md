---
name: article-finder
description: Step-by-step research-paper workflow from the "Research method and presentation" course slides. Mode 1 finds, validates, ranks and categorizes references (journal papers, conference papers, theses, books) and returns a checklist table where every approved source has all 11 steps ticked ✅. Mode 2 checks an article draft section by section (title, abstract, keywords, affiliation, introduction, research background, methodology, findings, conclusion, references) against the course's writing rules and returns a ticked table. Use this skill whenever the user wants to find, collect, vet, rank or filter sources for a paper, thesis or literature review, asks whether a journal or conference is credible or ISI/Scopus/ISC indexed, wants help writing or reviewing an article's sections or word counts, or writes in Persian about «پیدا کردن مقاله»، «منبع»، «پیشینه پژوهش»، «اعتبارسنجی ژورنال/کنفرانس»، «نوشتن مقاله»، «چکیده»، «مقدمه» — even if they never say "skill" or "checklist".
---

# Article Finder

Release 1.1.0.

Two jobs, one method, both from the user's research-methods slides (Niloofar Mirzaei Chahardeh, I.A.U.):

1. **Find references** (slides Chapter 1, "Method of Search"): scope the topic, search with a fixed keyword formula, push every candidate through validation gates, rank it, file it under one of four categories.
2. **Write the article** (slides Chapter 2, "Writing an Article"): check each section of a draft against the course's rules.

Either way the output is a table where an approved item has every step ticked. The deck numbers its own method steps **1-53** (page 6 = step 1, page 60 = step 53); `references/slide-coverage.md` maps every page and every step number to the file and the phase that implements it, so a user who says "step 22" lands on the full-text download (Phase E) and "step 8" on the keyword formula (Phase B). Where the slides give no number or definition (tier cut-offs, recency, and similar), this skill sets a default and says so; the user can override it. `references/slide-coverage.md` maps all 60 slides to the files below.

## Ground rules

1. **Only report sources you actually found.** Every article in the output must come from a search or fetch you ran in this session, with a URL. Never write a title, DOI, ISSN or quartile from memory: a fabricated reference is worse than a missing one.
2. **A tick means "verified".** ✅ only when you saw the evidence (publisher page, SJR/Clarivate/DOAJ entry, Irandoc record, or in the draft itself). ❌ means checked and failed. ❓ means you could not verify it. Anything with a ❓ is *pending*, not approved.
3. **Reply in the user's language** (Persian if they write Persian). Keep titles, ISSNs, URLs and tier letters in Latin script.
4. **Full text from legitimate routes only:** publisher page, Google Scholar PDF links, arXiv/author pages, institutional access, emailing the author. The slides also list Sci-hub, Libgen and Z-Lib; those host copyrighted work without permission, so do not fetch from them or recommend them (details in `references/validation.md` §8). If the user asks about them, say so briefly and offer the legitimate routes.
5. **Do not write the user's article for them unless they ask.** In Mode 2, check and explain; offer a rewrite of a section as a next step.

---

## Mode 1: Find and vet references

### Inputs to settle first

Take them from the conversation; ask one compact question only for what is missing and cannot be defaulted.

| Input | Default if not given |
|---|---|
| Research area (slides: Software, Formal Method, Network, Data Science, Data Mining, Security …) | ask |
| Subject: Goals + Ability + Time + Personality attribute | ask for the topic; infer the rest lightly |
| Tier cut-off | **B**: sources ranked C or D are eliminated |
| Target size | up to 5 approved sources per category |
| Recency | last 5 years for Application and Methodology (the slides tell the Introduction to cover the last 3-5 years); older foundational works allowed for Concept |

### Phase A: Scope

1. Area, then subject (slides' formula above).
2. Reference plan, as four questions: **Conceptology** (What), **Challenges** and **Applications** (Why), **Methodology** (How). Background: `references/course-background.md`.

### Phase B: Search

Search with `This Word + Your Research Keyword`. The slide's keyword words: Tutorial, Survey, Overview, An Introduction, Bibliography, References, Archive, Method, Technique, Algorithm, Model, Concept, Thesis, Taxonomy, Approach, Books.

Practical pairing *(skill)*: Survey / Overview / Tutorial / Introduction / Taxonomy / Concept / Books surface Concept and Challenge sources; Method / Technique / Algorithm / Model / Approach surface Methodology; Thesis / Bibliography / References / Archive surface extra leads.

Good starting sites from the slides: IEEE Xplore, SpringerLink, ScienceDirect, Google Scholar. When a site cannot be fetched, search with `site:` filters instead. Run the searches for all four categories in parallel. For reproducible multi-database retrieval, run `python3 scripts/search_databases.py` with the exact keyword query and save its JSON output. It queries Crossref and OpenAlex, records each query/date/URL/retrieved count, and deduplicates candidates. Preserve provider failures and rerun them before describing the search as systematic. The web workspace's Crossref discovery is supplementary single-provider search, not a substitute for this workflow. Record which keyword found each article (that is step S3).

### Phase C: Gate every candidate

Run the steps in order. Stop at the first ❌ and note why. Details, the tier rubric and the worked example: `references/validation.md`.

| Step | Gate | Passes when |
|---|---|---|
| S1 | Area | Reviewer judgement has an evidence URL and note |
| S2 | Subject | Reviewer judgement has an evidence URL and note |
| S3 | Keyword | The executed query, result URL, matching DOI and search date are recorded |
| S4 | Source type | Crossref type is supported; thesis degree has a review URL/note; undergraduate theses are rejected |
| S5 | Publisher / venue | Journal/conference publisher matches the allowed list; books/theses have a reviewed judgement |
| S6 | Source credibility | Journal: blacklist + index; conference: proceedings index; thesis: Irandoc/university repository; book: Google Books/Amazon + citation count + publisher evidence |
| S7 | Identifiers | Journal ISSN + volume/issue; conference DOI + edition/venue; book ISBN + main-book evidence; thesis repository record |
| S8 | Specialization & year | Specialization boolean and its review URL/note are present; category-specific year rule passes |
| S9 | Tier | A-D tier has a reviewer evidence URL and basis; the render script compares it to the cut-off |
| S10 | Category | Category judgement has an evidence URL and note |
| S11 | Extraction | Reading evidence is recorded: abstract/intro/conclusion, chapters 1–2, or full text |

If a source cannot be verified, try one alternative source (SJR when the Master Journal List will not load). If it still fails, mark ❓ and say exactly what the user should check and where. Never convert an unverified page, inferred tier, or missing specialization into ✅.

### Phase D: Report

1. Collect the DOIs you actually found and create a plan using `references/evidence-records.md`. The script retrieves Crossref/OpenAlex metadata and checks the evidence records supplied in the plan; it does **not** execute database searches or read papers for you. Record the real query, search-result URL, matching DOI and date; add the reviewed judgements, tier basis, blacklist check, index result and reading-depth evidence. Then run `python3 scripts/verify_source.py plan.json -o results.json --s6 s6-checklist.md`. Any missing or malformed evidence remains ❓; a blacklist hit rejects S6.
2. Run `python3 scripts/render_table.py results.json --lang fa` (`--lang en` for English, `--cutoff` to change the cut-off, `--evidence` to show the proof behind each tick, `--bibliography apa|ieee` to also emit the reference list). The script decides the verdict itself: approved only when all 11 steps are ✅. Duplicate records (same DOI, URL or normalised title) are merged before the count. Missing evidence can be filled from another duplicate, but contradictory evidence or metadata is recorded and makes the affected gate pending.
3. Run the citation identity audit for the bibliography: save the cited records as a JSON list and run `python3 scripts/verify_citations.py citations.json --format markdown`. DOI metadata must match the title/year/first author; retractions are rejected, corrections require human review, and missing DOIs produce candidates that remain pending. A metadata match does not prove that the paper supports the manuscript claim.\n4. Paste the output. Then, for each approved article, add a one-to-two-sentence extract in your own words of the point that made it useful in its category.
5. Hand the S6 checklist to the user as its own file: every row needs a human to open the blacklist and index links, confirm the relevant source record, and record both the blacklist result and index evidence in the plan. Do not tick S6 by inference from the publisher.
6. Close with one natural next step (for instance "next, write the Research Background from the Challenge sources").

---

## Phase E: Fetch the full text

```bash
python3 scripts/fetch_pdf.py results.json --out pdfs --report pdf-report.md
```

It asks OpenAlex, Unpaywall and Semantic Scholar, resolves arXiv ids, and writes the first candidate that is a real PDF. HTTP retrieval is fail-closed: HTTPS only, normal TLS certificate validation, public-IP preflight, redirect validation and an 80 MiB response cap. The resolver documents the remaining DNS-rebinding limitation; for hostile inputs, run it inside a network sandbox. Set `ARTICLE_FINDER_MAILTO` to a real contact address to query Unpaywall. The PDF check requires a `%PDF-` header and the size floor.

- **Paywalled rows are the normal case, not a failure.** The report lists the legitimate route for each one — publisher page, Google Scholar PDF links, author page, institutional access, emailing the author. Hand that list to the user; do not fetch from Sci-Hub, LibGen or Z-Lib and do not offer them as a shortcut (`references/validation.md` §8). This is the author's line, not a tool limitation: those hosts serve copyrighted papers without permission, and a copy from them can be a stale or retracted version. The skill stays on the open-access indexes and the routes above.
- `--dry-run` prints the candidate URLs without downloading, for when the user only wants to know what is reachable.
- **A downloaded PDF unblocks S11 for a Methodology source.** Open it, read the method section, then record the extract and the verdict; the abstract alone still does not tick S11.
- Say how many downloaded and how many need a licensed route. Never claim full-text coverage you did not get.

For more than about 8 approved articles, or if the user asks for a file, also save the table as a spreadsheet (use the xlsx skill if available).

---

## Mode 2: Write and check an article

Rules per section (word counts, what each part must contain, the slide examples): `references/writing-article.md`. Word budget: Title 8-15 · Abstract 200-250 · Keywords 6-8 · Introduction 500-700 · Research Background 1000-1500 · Methodology 500-1000 · Findings 1000-1500 (3-5 tables, 1-2 figures) · Conclusion 1000-1500. Title and Abstract are written after the article is completed.

1. **Get the draft.** If the user has none yet, walk them through the section list and the rules instead; do not invent content. Save the draft to a file with one heading per section (Title, Abstract, Keywords, Affiliation, Introduction, Research Background, Methodology, Findings, Conclusion, References; Persian headings also work).
2. **Run the auto checks:** `python3 scripts/check_draft.py draft.md --lang fa`. It decides the rules that are countable (word ranges, single paragraph, no tables/citations in the abstract and conclusion, capitalized keywords, table and figure counts, no list in the population description, the "and" rule). The rest show ❓ with a hint where a number helps.
3. **Judge the manual rules yourself** by reading the draft. For each ❓ rule write `true` or `false` plus a short note naming where in the draft you saw it (or why it is missing). Save as `manual.json` (format in the script docstring) and re-run with `--manual manual.json`. Be strict: a rule is ✅ only if the draft clearly does it.
4. **Paste the table**, then list what to fix, section by section, starting with ❌ and then ❓. Give the concrete slide rule behind each fix.
5. A section is **approved** only when every rule in it is ✅. Offer to rewrite a section once the user has seen the table.

Two judgment notes: the "and" rule (B7) is the slide's own rule, so report it as written, but say that it is a style rule and not a grammar error; rule B8 quotes a slide line that is only a fragment, so mark it from what the user tells you.


---

## Mode 3: Systematic and scoping review (PRISMA ledger)

Use this mode when the user asks for a systematic or scoping review, reproducible search documentation, screening counts, or a PRISMA-style flow.

1. **Freeze the protocol before screening.** Record the review type, research question, inclusion criteria, exclusion criteria, and any registry and registration ID. Do not invent a registration.
2. **Log every database search when it runs.** For each database/platform, save the exact query, ISO date, hit count, and limits. A database count without a corresponding query and date is invalid.
3. **Deduplicate explicitly.** Run `deduplicate_records()` or use the review ledger's DOI/PMID/URL/title keys. Preserve a link from each duplicate to its canonical record; do not silently discard conflicts.
4. **Record screening decisions.** Keep title/abstract and full-text stages separate. Full-text exclusions require one explicit reason. AI suggestions are not reviewer decisions and must not silently change protocol criteria.
5. **Reconcile counts.** Put the search log and counts in a JSON file following `examples/prisma-review.json`. The tool derives downstream counts and rejects negative or inconsistent arithmetic.
6. **Generate the report.** Run `python3 scripts/prisma_review.py examples/prisma-review.json --format report`; use `--format flow` for Mermaid or `--format json` for machine-readable counts.
7. **Synthesize only extracted evidence.** Save reviewer-extracted study fields and claim-to-source excerpts in a JSON bundle, then run `python3 scripts/synthesize_literature.py evidence-bundle.json --format markdown`. Group findings by theme, preserve conflicting and null directions, and leave a claim pending unless every linked study has a reviewed excerpt and locator. Do not infer study findings from titles or abstracts.
8. **State the limits.** A valid flow diagram proves arithmetic consistency, not search completeness, eligibility correctness, or absence of bias. Human screening and quality appraisal remain explicit responsibilities.

Do not describe a review as PRISMA-compliant solely because a diagram was generated. Complete the relevant PRISMA checklist and report protocol deviations, missing full texts, single-reviewer limitations, and any unregistered post hoc changes.


---

## Bundled files

- `references/course-background.md`: research concept, types, prerequisites, area/subject/reference, keywords (slides 1-14).
- `references/validation.md`: gates for each source type, tier rubric, where to verify, the worked example, full-text policy, and §10 on which gates a script can decide.
- `references/reading.md`: reading and extraction rules for the four categories. Read before S11.
- `references/writing-article.md`: all Chapter 2 rules and the rule IDs for `check_draft.py`.
- `references/output-example.md`: JSON inputs and rendered outputs for both modes (placeholder data).
- `references/slide-coverage.md`: all 60 pages and all 53 numbered steps mapped to the file and the phase that implements each one.
- `scripts/check_ids.py`: offline ISSN / ISBN-10 / ISBN-13 checksum validator.
- `scripts/verify_source.py`: builds `results.json` from DOIs (Crossref + OpenAlex + `check_ids.py`) and writes the S6 checklist.\n- `scripts/verify_citations.py`: compares citation identity with Crossref metadata and flags recorded corrections/retractions.
- `scripts/search_databases.py`: searches Crossref and OpenAlex, saves exact query provenance and deduplicates candidate records.
- `scripts/fetch_pdf.py`: downloads the open full text and reports the licensed route for everything else.
- `scripts/render_table.py`: Mode 1 checklist tables, verdicts, duplicate merge, APA/IEEE reference list.
- `scripts/check_draft.py`: Mode 2 checklist tables for a draft.
- `scripts/prisma_review.py`: Mode 3 protocol/search-log validation, deduplication helpers, PRISMA count reconciliation and Mermaid flow output.
- `scripts/synthesize_literature.py`: reviewer-extracted evidence matrix, thematic grouping, conflict flags and claim-to-source evidence map.
- `scripts/http_util.py`: the shared request, retry and TLS handling the three network scripts use.
- `examples/`: the fixture files whose real output `references/output-example.md` shows.
- `tests/`: regression tests for every script.

## Tests

```bash
python3 -m unittest discover tests
```

The suite covers the verdict logic, ISSN/ISBN checksums, Persian-digit parsing, draft counters, duplicate merging, bibliography formatting, bilingual output, transport policy, API boundaries and PRISMA count reconciliation. Run it after any edit to `scripts/`. Bug classes it exists for, because each one silently produced a false ✅ or a false download: a mention counted as a table, a Persian-year citation missed, English text leaking into the Persian table, and an HTML error page accepted as a PDF.



