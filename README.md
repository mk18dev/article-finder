# article-finder

**Release 1.3.0** — evidence-backed gates, fail-closed HTTPS retrieval and conflict-aware duplicate handling.

**A verification-first research-paper skill for AI agents.** It finds and vets sources for a paper, then checks a draft section by section — and it refuses to tick a box it cannot prove.

Most "find me references" prompting produces confident fiction. This skill inverts that: a source needs a search record, a resolved DOI, source-type-specific identifiers and documented review evidence. Missing or contradictory evidence stays **pending**, never approved. The scripts decide the verdict; the model cannot approve itself.

```
$ python3 scripts/render_table.py results.json --lang en
**Summary:** 0 approved · 8 pending · 2 rejected (Tier cut-off: B)
```

Zero approved is a normal, honest result. Read the next section for why.

---

## Three workflows\n\n| Workflow | Input | Output |\n|---|---|---|\n| Discover sources | Course keyword + research topic | Real Crossref candidates with query, DOI and timestamp provenance |\n| Verify sources | DOI + evidence plan | 11-gate evidence checklist and APA/IEEE references |\n| Check a draft | Article draft | Section-by-section report against 76 writing rules |\n\nThe web workspace can search Crossref directly, select up to four candidates, and pass their exact search records into source verification. Discovery is not approval: missing reviewer evidence remains pending.\n\n## Two modes

| | Mode 1 — find and vet | Mode 2 — check a draft |
|---|---|---|
| Input | a research topic | a draft, one heading per section |
| Output | checklist table per source + APA/IEEE reference list | checklist table per section + fix list |
| Decides | 11 gates (S1–S11) | 76 rules, 21 countable, 6 requiring a hint/reviewer |
| Command | `verify_source.py` → `render_table.py` | `check_draft.py` |

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
| S9 | Tier ≥ cut-off | only a tier with reviewer evidence and a source URL can pass |
| S10 | Category | reviewer judgement with a source URL and note |
| S11 | Extraction | evidence of required reading: abstract/intro/conclusion, chapters 1–2, or full text |

**S6 remains evidence-driven.** A blacklist hit rejects the source. Otherwise, S6 stays pending until the plan contains a documented blacklist check and at least one verified index record. OpenAlex's DOAJ flag or a publisher name alone is not proof of Scopus/WoS/ISC/DBLP membership. The generated checklist gives the reviewer the pages to inspect.

## Quickstart

Requires **Python 3.10+** and nothing else. No third-party packages.

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

## What the tables look like

```
### Pending: needs your verification

| # | Article | Type | Tier | Category | 1 | 2 | 3 | ... | 11 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Placeholder Survey](https://doi.org/10.1000/x) (2024) | Journal | A | Concept | ❓ | ❓ | ❓ | ... | ❓ |

**Summary:** 0 approved · 1 pending · 0 rejected (Tier cut-off: B)
```

Full output examples for both modes live in [`references/output-example.md`](references/output-example.md). Mode 1's fixtures are explicitly placeholders and never demonstrate an approved source.

## Downloading full text

`fetch_pdf.py` asks OpenAlex, Unpaywall and Semantic Scholar, resolves arXiv ids, follows HTML→PDF links inside repository pages, and accepts a response as a PDF only if it starts with `%PDF-` and passes a size floor — because publishers answer with HTML error pages under HTTP 200.

When a paper is not open, the report names the licensed route and `--draft-emails` writes a ready-to-send request to the corresponding author.

**Transport safeguards:** remote fetches require HTTPS, normal TLS certificate verification, public-IP preflight, redirect revalidation and an 80 MiB response cap. Ambient proxy settings are disabled so they cannot bypass destination checks. DNS rebinding between preflight and connection remains a limitation; run untrusted inputs in a network sandbox or enforce an outbound firewall/egress policy. The legacy blacklist evidence page is a manual-review exception documented in `references/evidence-records.md`; it is not fetched by the downloader.

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

The suite is network-free and additionally covers source evidence gates, duplicate conflicts, URL/redirect policy, response-size limits and the original draft/PDF regressions. GitHub Actions runs it on Python 3.10–3.13.

| Bug | What it did |
|---|---|
| a table *mention* counted as a table | reported "1 table" for a draft with none |
| Persian-year citations missed | `(۱۴۰۲)` invisible to the citation check |
| English text in the Persian table | RTL leak in every `--lang fa` run |
| HTML error page accepted as PDF | a 200 response is not a download |

## Repository layout

```
SKILL.md              the workflow an agent follows
references/           the rule set, gates, rubric, reading rules, verification map
scripts/              verify_source · render_table · fetch_pdf · check_draft · check_ids · web_api · http_util
tests/                regression tests for every script
examples/             fixtures whose real output the docs show
tools/pack_skill.py   builds dist/article-finder.skill
```

## Packaging

```bash
python3 tools/pack_skill.py      # -> dist/article-finder.skill
```

The archive holds `SKILL.md`, `references/`, `scripts/`, `tests/` and `examples/` — drop it into a skills directory as-is.

## License and attribution

Code is MIT (see [`LICENSE`](LICENSE)). The rule set paraphrases a course deck by **Niloofar Mirzaei Chahardeh** (I.A.U.); the deck is not redistributed, and the paraphrased documentation is published **with the author's permission** — see [`NOTICE`](NOTICE) for the licence split.

Not affiliated with, or endorsed by, the deck's author or Islamic Azad University.

## Web app and API

**Live application:** [article-finder-peach.vercel.app](https://article-finder-peach.vercel.app/) — Release 1.3.0.

The Persian-first web interface uses the same Python verification and draft-checking
functions as the CLI; it does not introduce a second rules engine.

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
and a draft of at most 180,000 characters. Cross-origin browser POSTs are
rejected and no CORS access is granted. POSTs are JSON-only and limited to
512 KiB. Missing or unverified research evidence remains pending; the service
does not claim that a reviewer attestation or an indexing record is true merely
because it was submitted. Remote metadata requests use bounded timeouts and
retries. Set `ARTICLE_FINDER_API_KEY` in the hosting environment to require
Bearer authentication; the browser sends the key only for the current request
and does not persist it. Without this variable, API access is public.

### Local development

Run the offline suite and start the standard-library HTTP server:

```bash
python -m unittest discover -s tests -t tests -v
python -m scripts.serve
```

The local web/API is available at `http://127.0.0.1:8000/` (or the configured
`PORT`). Vercel deployment configuration is maintained in `vercel.json`.
GitHub Actions tests Python 3.10–3.13 and, on pushes to `main`, waits for the
production deployment before checking the live health endpoint, static assets,
Crossref discovery, 11-gate source verification and 76-rule draft-check API.
