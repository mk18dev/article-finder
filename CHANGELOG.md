# Changelog

All notable changes to this skill and web app. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning [SemVer](https://semver.org/).

## [1.1.0] — 2026-11-23

### Source discovery

- Added live Crossref bibliographic search to the web workspace.
- Returns real DOI candidates with title, authors, year, publisher and venue metadata.
- Captures exact query, Crossref result URL, matched DOI and UTC search timestamp in each candidate plan.
- Allows up to four selected candidates to flow directly into the existing 11-gate verifier; discovery never grants approval or fabricates reviewer evidence.
- Added unit and HTTP integration tests for discovery validation, malformed/duplicate records, upstream failures and evidence provenance.
- Removed unused Railway deployment configuration and platform-specific instructions; retained the hosting-neutral HTTP server and Vercel adapter.
- Added a separate manual production smoke workflow for static assets, health, Crossref discovery, source verification and draft checking. It is intentionally gated until the matching v1.1.0 production deployment is authorized.
- v1.1.0 has not been deployed to production in this release cycle; the existing Vercel deployment is not evidence that this source revision is live.

### Tier verification and evidence integrity

- Journal tier computation now requires a verified identifier; invalid identifiers resolve to tier D and missing identifiers remain pending.
- Malformed source-kind and indexing-status inputs fail closed instead of raising runtime errors.
- Book citation counts now require a separate reviewer-attributed OpenAlex record; the count and DOI/ISBN must match the exact book record.
- Added MIT Press to the trusted academic-publisher allowlist.
- Added real-source tier snapshots for a SCIE/SJR-Q1 journal, KDD 2024 proceedings, a Sheffield PhD thesis with an EBioMedicine derived paper, and the MIT Press Deep Learning book.
- PhD tier-A computation now requires independent SJR/JCR quartile or ESCI evidence for each derived paper; the evidence-derived tier must match the declared A/B tier.
- Added regression coverage for missing, mismatched and unrelated citation evidence, plus real-record A-tier paths across all four source categories.

### Systematic review and literature analysis

- Added Crossref + OpenAlex multi-provider search with exact query URLs, timestamps, provider-level failures, raw records, stable record IDs and duplicate links.
- Added a reviewer-attributed PRISMA-style ledger: dual screening, independent adjudication, full-text exclusion reasons, database/register/other-method identification streams, and counts derived from raw records.
- Included-study counts are based on unique study IDs; reports of included studies remain a separate count.
- Added thematic literature synthesis with reviewer-extracted study fields, evidence locators, conflict flags, quality-appraisal evidence and claim-to-source maps. It does not invent effect sizes or perform meta-analysis.
- Hardened PRISMA provenance: exact calendar dates, valid HTTPS origins, valid DOI deduplication keys, and a report-level duplicate-resolution ledger with metadata conflicts.
- Hardened synthesis evidence: every provided claim excerpt must be reviewed, linked to exactly one declared study, use a valid HTTPS origin, and include a non-empty locator; unknown and duplicate evidence links are rejected.

### Citation integrity

- Added Crossref DOI/title/year/author identity checks and correction/retraction/withdrawal flags; uncertain records remain Pending.
- Added APA/IEEE in-text-to-bibliography crosswalk checks for missing, uncited, duplicate and malformed citations.
- Identity agreement is explicitly not treated as proof that a source supports a manuscript claim.
- IEEE crosswalk now rejects non-positive, fractional, boolean, or malformed bibliography identifiers instead of coercing them into citation numbers.

### Specialized skills

- Added nine focused playbooks for systematic search, OpenAlex retrieval, source verification, PRISMA screening, literature synthesis, citation verification, scientific writing, security review and CI/CD release.
- The skill package now includes canonical `VERSION`, all specialized playbooks, and package-manifest regression tests.

### Quality gates

- The baseline CI run on commit `3315c76816249316d6698b795954b2c10ef6e66c` passed the Python 3.10–3.13 test jobs, static quality/security, Chromium, and WebKit; Firefox and production smoke were cancelled in that run and are not counted as passes.
- Added 21 regression/acceptance tests across citation identity, IEEE numbering, PRISMA provenance and duplicate traceability, synthesis evidence, and the 76-rule matrix. The latest main revision requires a fresh complete CI read-back before phase acceptance.
- Added Ruff lint, Bandit security scanning and pip-audit for pinned runtime/browser/quality dependencies.
- Added a Playwright browser smoke job for RTL rendering, mode switching and 320px/390px mobile plus desktop overflow checks.
- Added package-content validation for all nine specialist skills and explicit exclusion of PDFs, caches and build output.
- Production smoke remains manual and requires explicit authorization; this release cycle does not promote a Vercel deployment.

### Web application and API

- Added a Persian-first responsive web workspace for source verification and draft checking, backed by the existing Python modules.
- Added a bounded, same-origin JSON API with per-request size limits, DOI normalization, constant-time bearer authentication, fail-closed Vercel defaults, and no public PDF-fetch route.
- Added Vercel Python-function configuration, response security headers, and a 90-second function limit.
- Added API regression tests plus JavaScript syntax and deployment-config validation to the Python 3.10–3.13 CI matrix.
- Documented Vercel setup, production API-key configuration, and the limits of submitted reviewer evidence.


### Security and retrieval

- Removed the TLS-verification fallback. All remote requests use the platform's normal certificate validation; HTTP URLs are rejected.
- Added destination-IP preflight and redirect revalidation, disabled implicit environment proxies, and applied the response-size cap to JSON metadata as well as PDF bytes.
- Documented the DNS-rebinding race that remains between DNS preflight and socket connection; hostile inputs still require an isolated network/egress policy.
- Switched the arXiv API query to HTTPS and required an explicit `ARTICLE_FINDER_MAILTO` for Unpaywall requests.
- Made author-request email drafts topic-neutral instead of hardcoding a particular research topic.

### Evidence and source validation

- S1/S2/S10 now require documented reviewer judgements; S3 requires a matching executed-search record; S8 specialization and non-undergraduate thesis degree require reviewer evidence; tier A-D requires reviewer evidence.
- S6 now applies source-specific evidence: journals require blacklist + index checks; conferences require proceedings indexing; theses require an Irandoc/university repository record; books require Google Books/Amazon, citation count and publisher confirmation.
- S7 now uses source-type-specific evidence for journals, conference proceedings, books and theses; bachelor's theses are rejected, and book chapters are not treated as main books.
- S11 now requires the reading depth defined by the source category and type; an abstract alone cannot pass.
- Duplicate merge now surfaces contradictory steps and conflicting metadata instead of silently preferring one record.

### Draft validation

- Made the draft-chart rule reviewer-confirmed: a textual “Chart 1” label or an image alone no longer auto-approves the existence of a chart.
- Added an acceptance matrix covering all 76 rules, source-step mapping, fail-closed missing sections, manual verdicts, and hint-rule human confirmation.

### Tests, docs and CI

- Added network-free transport, evidence-gate and duplicate-conflict regression tests.
- Documented the evidence-plan schema and the boundaries of what the CLI actually verifies.
- Pinned GitHub Actions dependencies to full commit SHAs and disabled checkout credential persistence.
- Preserved the Python 3.10–3.13 matrix and standard-library-only runtime.

## [1.0.0] — first public release

### Mode 1 — find and vet references

- `verify_source.py` builds `results.json` from DOIs: Crossref for publisher, venue, volume/issue/pages, year and authors; OpenAlex for the abstract and citation count; `check_ids.py` for every ISSN checksum.
- Settles S3 (course keyword + research keyword), S4, S5, S7, S8 and S9 mechanically; records S1, S2 and S10 as declared; leaves S6 pending and writes `s6-checklist.md` with the exact SCImago, Clarivate, DOAJ, DBLP and Iranian-blacklist link per source.
- `render_table.py` decides the verdict — approved only when all 11 gates are ✅ — merges duplicate records (DOI, then URL, then normalised title), and emits an APA or IEEE reference list with the pending count.
- Persian and English output with localised details, numerals and notes.

### Mode 2 — write and check a draft

- `check_draft.py` applies 76 rules across 10 sections: 22 countable, 5 hinted with a number, 49 read by the reviewer and recorded in `manual.json`.
- Fail-closed: a manual rule without a recorded verdict shows ❓ and its section is never approved.
- Every rule names the course step and page it comes from; `references/writing-article.md` §12 maps slide lines to rule IDs.

### Full text

- `fetch_pdf.py` resolves open copies through OpenAlex, Unpaywall and Semantic Scholar, follows arXiv ids, and walks HTML→PDF links inside repository pages.
- A response counts as a PDF only if it starts with `%PDF-` and passes a size floor; a list of candidates is never mistaken for a download.
- `--draft-emails` writes author request emails for everything still paywalled. `--dry-run` lists candidates without downloading.
- Sci-Hub, LibGen and Z-Lib are not supported and cannot be enabled by a flag.

### Fixed before release

Four defect classes, each of which had produced a false ✅ or a false download, now covered by tests:

- a table *mention* was counted as a table, so Findings reported tables that did not exist;
- `(۱۴۰۲)` and `(Smith، ۱۴۰۲)` were invisible to the citation check, so abstracts and conclusions passed with citations in them;
- the detail column stayed English in `--lang fa` tables, and numerals stayed Latin;
- an HTML error page served under HTTP 200 was accepted as a PDF.

Also fixed: `Scientia Iranica, 0(0), 0-0` printed for in-press records, and `classify()` in `check_ids.py` was annotated `-> str` while returning a tuple.

### Verified against the source deck

All 60 pages and all 53 numbered steps were read from the deck's own text: 0 pages misattributed between the references, 53/53 steps accounted for. `references/slide-coverage.md` maps each page and step to the file and phase that implements it.

### Tests

121 tests, no network, no third-party dependencies: verdict logic, ISSN/ISBN checksums, Persian parsing, table and figure counters, duplicate merge, bibliography format, PDF detection, and the rule→step map.
