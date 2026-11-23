# article-finder

**Release 1.1.0** — evidence-backed gates, fail-closed HTTPS retrieval and conflict-aware duplicate handling.

**A verification-first research-paper skill for AI agents.** It finds and vets sources for a paper, then checks a draft section by section — and it refuses to tick a box it cannot prove.

Most "find me references" prompting produces confident fiction. This skill inverts that: a source needs a search record, a resolved DOI, source-type-specific identifiers and documented review evidence. Missing or contradictory evidence stays **pending**, never approved. The scripts decide the verdict; the model cannot approve itself.

```
$ python3 scripts/render_table.py results.json --lang en
**Summary:** 0 approved · 8 pending · 2 rejected (Tier cut-off: B)
```

Zero approved is a normal, honest result. Read the next section for why.

---

## Workflows

| Workflow | Input | Output |
|---|---|---|
| Discover sources | Course keyword + research topic | Crossref/OpenAlex CLI results with DOI and query provenance; web UI offers Crossref discovery |
| Verify sources | DOI + evidence plan | 11-gate checklist and APA/IEEE references |
| Verify citations | Bibliography + manuscript text + APA/IEEE style | Crossref identity/update audit and in-text/reference crosswalk |
| Check a draft | Article draft | Section-by-section report against 76 writing rules |
| Systematic/scoping review | Protocol + database search log + screening counts | Validated PRISMA-style counts, flow diagram, evidence matrix and thematic synthesis |

Discovery returns candidates, never approvals. Reviewer evidence remains pending until documented. PRISMA counts are derived from the supplied search log and screening ledger; the tool refuses inconsistent arithmetic and never invents screening decisions.

## Four modes

| | Mode 1 — find and vet | Mode 2 — check a draft | Mode 3 — systematic/scoping review | Mode 4 — citation identity audit |
|---|---|---|---|---|
| Input | Research topic and DOI candidates | Draft with one heading per section | Protocol, exact searches, and screening ledger | Bibliography with DOI/title/year/author |
| Output | 11-gate source checklist + APA/IEEE bibliography | 76-rule section report + fix list + citation crosswalk | Database/register/other-method search audit, reconciled counts, Mermaid flow, evidence matrix | Identity match, mismatch, correction/retraction flags + APA/IEEE crosswalk |
| Command | `search_databases.py` → `verify_source.py` → `render_table.py` | `check_draft.py` + `citation_crosswalk.py` | `prisma_review.py` + `synthesize_literature.py` | `verify_citations.py` + `citation_crosswalk.py` |

## The 11 gates (Mode 1)

| # | Gate | Decided by |
|---|---|---|
| S1 | Area | reviewer judgement with a source URL and note |
| S2 | Subject | reviewer judgement with a source URL and note |
| S3 | Keyword | executed query, result URL, matching DOI and timestamp |
| S4 | Source type | Crossref type; thesis degree is explicit and undergraduate is rejected |
| S5 | Publisher / venue | Crossref publisher for journals/conferences; evidenced judgement for books/theses |
| S6 | Source credibility | Journals: blacklist + index; conferences: proceedings index; theses: Irandoc/university repository; books: Google Books/Amazon + citations + publisher evidence |
| S7 | Identifiers | journal ISSN + volume/issue; conference edition/venue; book ISBN; thesis repository record |
| S8 | Specialization & year | explicit specialization boolean + evidence URL/note + category-specific year rule |
| S9 | Computed tier ≥ cut-off | A/B/C/D is computed from source-specific evidence; SJR/JCR quartile, publisher, specialization, derived papers or book citations are validated; a declared/computed mismatch fails |
| S10 | Category | reviewer judgement with a source URL and note |
| S11 | Extraction | evidence of required reading: abstract/intro/conclusion, chapters 1–2, or full text |

**S6 remains evidence-driven.** A verified blacklist hit from MSRT, MOHME or IAU rejects the source. Otherwise, S6 stays pending until the plan contains all three reviewer-attributed ISSN checks (with current list version, exact locator and timestamp) and at least one verified index record. ImpactFactor is a secondary aggregator, not an authority. OpenAlex's DOAJ flag or a publisher name alone is not proof of Scopus/WoS/ISC/DBLP membership. The generated checklist gives the reviewer the pages to inspect.

## Quickstart

Requires **Python 3.10+** and one pinned runtime dependency: `defusedxml` for safe parsing of untrusted arXiv Atom feeds. Browser and static-analysis dependencies are isolated to CI.

```bash
# 1. Record each DOI you actually found and its review evidence.
#    The complete schema is documented in references/evidence-records.md.
cat > plan.json <<'JSON'
[
  {
    "doi": "10.3233/IDA-163209",
    "category": "concept",
    "tier": "B",
    "keyword": "Survey + hybrid recommender systems",
    "area": "data science",
    "subject": "hybrid recommender systems",
    "specialized": true
  }
]
JSON

# 2. Add real search, reading, tier, judgement, blacklist and index evidence
#    before expecting any of those gates to pass.
python3 scripts/verify_source.py plan.json -o results.json --s6 s6-checklist.md

# 3. Render the verdicts and the reference list
python3 scripts/render_table.py results.json --lang en --evidence --bibliography apa
python3 scripts/render_table.py results.json --lang fa     # Persian table, Persian numerals

# 4. Optional: configure a real contact address for Unpaywall.
export ARTICLE_FINDER_MAILTO="you@example.org"
python3 scripts/fetch_pdf.py results.json --out pdfs --report pdf-report.md --draft-emails emails.md

# 5. Check a draft against the writing rules
python3 scripts/check_draft.py draft.md --lang en
python3 scripts/check_draft.py draft.md --lang fa --manual manual.json
```

### Systematic review, evidence synthesis and citation audit

```bash
python3 scripts/prisma_review.py examples/prisma-review.json --format report
python3 scripts/synthesize_literature.py examples/literature-evidence.json --format markdown
python3 scripts/verify_citations.py examples/citations.json --format markdown
python3 scripts/citation_crosswalk.py manuscript.txt references.json --style APA
```

The PRISMA, literature and citation fixtures are explicitly placeholders. For a real review, copy `raw_records` (not only deduplicated `records`) from each completed search into the ledger. Each screening decision needs reviewer ID and timezone-aware timestamp; dual-review disagreements need adjudication, while single-reviewer work needs a stated justification. Counts are calculated from that record ledger. Placeholder output is not research evidence.

## What the tables look like

```
### Pending: needs your verification

| # | Article | Type | Tier | Category | 1 | 2 | 3 | ... | 11 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Placeholder Survey](https://doi.org/10.1000/x) (2024) | Journal | A | Concept | ❓ | ❓ | ❓ | ... | ❓ |

**Summary:** 0 approved · 1 pending · 0 rejected (Tier cut-off: B)
```

Mode 1 and Mode 2 output examples live in [`references/output-example.md`](references/output-example.md). Mode 1's fixtures are explicitly placeholders and never demonstrate an approved source.

## Downloading full text

`fetch_pdf.py` asks OpenAlex, Unpaywall and Semantic Scholar, resolves arXiv ids, follows HTML→PDF links inside repository pages, and accepts a response as a PDF only if it starts with `%PDF-` and passes a size floor — because publishers answer with HTML error pages under HTTP 200.

When a paper is not open, the report names the licensed route and `--draft-emails` writes a ready-to-send request to the corresponding author.

**Transport safeguards:** remote fetches require HTTPS, normal TLS certificate verification, all-address public-IP validation, connection-time IP pinning with original-host TLS SNI, redirect revalidation, ambient-proxy isolation, bounded timeout/retries and an 80 MiB response cap. Retrieval reports record provider, source URL, final URL, UTC time and outcome for each attempt. Content-Type is diagnostic only; the `%PDF-` signature and size floor determine whether a response is accepted. The ImpactFactor site is a secondary blacklist aggregator only; S6 requires reviewer-attributed checks against official MSRT, MOHME and IAU sources.

**It never touches Sci-Hub, LibGen or Z-Lib, and no flag enables them.** Those hosts redistribute copyrighted papers without permission, and a copy from them can be a stale or retracted version. If you need a paywalled paper: publisher page, Google Scholar's PDF links, your library, or the author's inbox.

## Tracing every rule to the course slide

`SKILL.md` and the `references/` files paraphrase a 60-page course deck (53 numbered steps). Every rule the checker applies names the step and page it comes from, and `references/slide-coverage.md` maps all 60 pages and all 53 steps to the file and phase that implements each one.

```
| ID | Rule                   | Result | Detail                    | Step      |
| T1 | 8-15 words             | ✅     | 8 words (slide: 8-15)     | 34 (p41)  |
| A11| No tables, refs...     | ❌     | found: in-text reference  | 37 (p44)  |
```

## Tests

```bash
python3 -m unittest discover -s tests -t tests -v
```

The suite is network-free and additionally covers source evidence gates, citation identity/update checks, APA/IEEE in-text crosswalk, PRISMA count reconciliation, thematic evidence synthesis, claim-to-source mapping, duplicate conflicts, URL/redirect policy, response-size limits and the original draft/PDF regressions. GitHub Actions runs it on Python 3.10–3.13.

| Bug | What it did |
|---|---|
| a table *mention* counted as a table | reported "1 table" for a draft with none |
| Persian-year citations missed | `(۱۴۰۲)` invisible to the citation check |
| English text in the Persian table | RTL leak in every `--lang fa` run |
| HTML error page accepted as PDF | a 200 response is not a download |

## Repository layout

```
SKILL.md              the main workflow an agent follows
VERSION               canonical release version
requirements.txt      pinned safe-XML runtime dependency
requirements-browser.txt pinned Playwright browser-test dependency
requirements-quality.txt pinned Ruff, Bandit and pip-audit tools
skills/               nine specialized research and engineering playbooks
references/           the rule set, gates, rubric, reading rules, verification map
scripts/              search_databases · verify_source · verify_citations · citation_crosswalk · prisma_review · synthesize_literature · render_table · fetch_pdf · check_draft · check_ids · web_api · http_util
tests/                regression tests for every script and package
examples/             fixtures whose real output the docs show
tools/pack_skill.py   builds dist/article-finder.skill
```

## Packaging

```bash
python3 tools/pack_skill.py      # -> dist/article-finder.skill
```

The archive holds `SKILL.md`, `VERSION`, nine specialized `skills/` playbooks, `references/`, `scripts/`, `tests/` and `examples/` — drop it into a skills directory as-is.

## License and attribution

Code is MIT (see [`LICENSE`](LICENSE)). The rule set paraphrases a course deck by **Niloofar Mirzaei Chahardeh** (I.A.U.); the deck is not redistributed, and the paraphrased documentation is published **with the author's permission** — see [`NOTICE`](NOTICE) for the licence split.

Not affiliated with, or endorsed by, the deck's author or Islamic Azad University.

## Web app and API

The Persian-first web interface exposes source discovery, 11-gate source verification and draft checking through the same Python modules as the CLI. The workspace visibly lists all four research modes: source verification and draft checking are available in Web/API; systematic/scoping review and citation identity audit are explicitly marked CLI-only. Full-text PDF retrieval also remains a local CLI-only workflow.

- `/` serves the responsive web workspace.
- `GET /api` reports API health and supported actions.
- `POST /api` accepts `discover_sources`, `verify_sources`, or `check_draft`
  and returns structured JSON plus Markdown.
- `discover_sources` performs a real Crossref bibliographic search and records
  the exact query URL, matched DOI and UTC timestamp. It returns candidates,
  never approvals.
- `scripts/web_api.py` contains the bounded API and delegates to the existing
  verification/checking modules.
- `scripts/serve.py` is a standard-library HTTP server for local use and
  self-managed hosting. It serves only known static assets and routes `/api`
  to the same API handler.
- `api/index.py` and `vercel.json` provide the Vercel function adapter.
- The hosted API never exposes `fetch_pdf.py`; arbitrary PDF fetching remains
  a local CLI workflow, not a public URL-fetch endpoint.

### API boundaries

The API accepts at most four source records or discovery candidates per request
and a draft of at most 180,000 characters. Cross-origin browser POSTs and CORS preflight are rejected; no
CORS access is granted. POSTs are JSON-only and limited to 512 KiB. Malformed
JSON/shape errors return 400, semantic payload validation returns 422,
authentication failures return 401, oversized bodies return 413, and unsupported
media types return 415. The API does not emit 429 because no shared/distributed
rate limiter is configured; a process-local counter would not be a reliable
Vercel-wide security control. Each Python process also caps simultaneous POST processing at four requests and rejects excess work with HTTP 503; this is a local resource guard, not a cross-instance quota or distributed rate limit. Missing or unverified research evidence remains pending; the service
does not claim that a reviewer attestation or an indexing record is true merely
because it was submitted. Remote metadata requests use bounded timeouts and
retries. On Vercel, `ARTICLE_FINDER_API_KEY` is required by default; the browser sends this Article Finder access key only for the current request and does not persist it. It is not an LLM/provider key. Set the same secret as a Sensitive Production environment variable in Vercel and as the GitHub Actions repository secret `ARTICLE_FINDER_API_KEY` before running production smoke. Do not set `ARTICLE_FINDER_PUBLIC_MODE=1` unless the API is intentionally meant to be public. Local development remains public by default. The health endpoint reports the active auth mode.

### Local development

Install the pinned runtime dependency, run the offline suite, and start the local HTTP server:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -t tests -v
python -m scripts.serve
```

The local web/API is available at `http://127.0.0.1:8000/` (or the configured
`PORT`). Vercel deployment configuration is maintained in `vercel.json`. The current Vercel project is not Git-linked, so pushes to `main` do not auto-deploy; do not deploy until the user explicitly authorizes a release; the Vercel project remains intentionally outside automatic Git deployments. GitHub Actions tests Python 3.10–3.13, browser behavior, lint, security and package contents on pushes to `main`; the live Vercel smoke suite is a separate manual workflow dispatch (`run_production_smoke=true`) and requires the matching API key secret.
