# Changelog

All notable changes to this skill and web app. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning [SemVer](https://semver.org/).

## [1.3.0] — 2026-11-23

### Source discovery

- Added live Crossref bibliographic search to the web workspace.
- Returns real DOI candidates with title, authors, year, publisher and venue metadata.
- Captures exact query, Crossref result URL, matched DOI and UTC search timestamp in each candidate plan.
- Allows up to four selected candidates to flow directly into the existing 11-gate verifier; discovery never grants approval or fabricates reviewer evidence.
- Added unit and HTTP integration tests for discovery validation, malformed/duplicate records, upstream failures and evidence provenance.
- Removed unused Railway deployment configuration and platform-specific instructions; retained the hosting-neutral HTTP server and Vercel adapter.
- Added a production smoke-test job after the Python matrix: waits for Vercel health, checks static assets, performs real Crossref discovery, and exercises all 76 draft rules against the live API.
- Released and verified the Vercel production build at `article-finder-peach.vercel.app`.

## [1.2.0] — 2026-11-23

### Web application and API

- Added a Persian-first responsive web workspace for source verification and draft checking, backed by the existing Python modules.
- Added a bounded, same-origin JSON API with per-request source/draft size limits, DOI normalization, optional bearer authentication, and no public PDF-fetch route.
- Added Vercel Python-function configuration, response security headers, and a 90-second function limit.
- Added API regression tests plus JavaScript syntax and deployment-config validation to the Python 3.10–3.13 CI matrix.
- Documented Vercel setup, production API-key configuration, and the limits of submitted reviewer evidence.


## [1.1.0] — 2026-11-23

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
