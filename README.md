# article-finder

**A verification-first research-paper skill for AI agents.** It finds and vets sources for a paper, then checks a draft section by section — and it refuses to tick a box it cannot prove.

Most "find me references" prompting produces confident fiction. This skill inverts that: every source needs a search you actually ran, a DOI that resolves, and an ISSN whose checksum passes. A source with one unverified gate stays **pending**, never approved. The scripts decide the verdict; the model cannot approve itself.

```
$ python3 scripts/render_table.py results.json --lang en
**Summary:** 0 approved · 8 pending · 2 rejected (Tier cut-off: B)
```

Zero approved is a normal, honest result. Read the next section for why.

---

## Two modes

| | Mode 1 — find and vet | Mode 2 — check a draft |
|---|---|---|
| Input | a research topic | a draft, one heading per section |
| Output | checklist table per source + APA/IEEE reference list | checklist table per section + fix list |
| Decides | 11 gates (S1–S11) | 76 rules, 22 of them countable |
| Command | `verify_source.py` → `render_table.py` | `check_draft.py` |

## The 11 gates (Mode 1)

| # | Gate | Decided by |
|---|---|---|
| S1 | Area | declared, and recorded as declared |
| S2 | Subject | keyword token found in title/abstract |
| S3 | Keyword | a course keyword + the research keyword (machine-checked) |
| S4 | Source type | Crossref record type |
| S5 | Publisher / venue | Crossref publisher, matched against the rubric |
| S6 | Indexing | **a human** — see below |
| S7 | Identifiers | ISSN checksum (`check_ids.py`) |
| S8 | Specialization & year | Crossref year vs the recency rule |
| S9 | Tier ≥ cut-off | computed from the tier and the cut-off |
| S10 | Category | declared |
| S11 | Extraction | an abstract ticks Concept/Challenge/Application; Methodology needs the full text |

**S6 is the honest hole, and it stays a hole.** Scopus and Web of Science membership is exposed only through Clarivate and SCImago, which block scripted clients (`scimagojr.com` → HTTP 403, `dblp.org` → Anubis challenge, `mjl.clarivate.com` → JavaScript only). `verify_source.py` therefore leaves S6 `❓` and writes `s6-checklist.md` with the exact URL a human must open for every source. Ticking S6 by inference from the publisher is the failure mode this design exists to prevent.

## Quickstart

Requires **Python 3.10+** and nothing else. No third-party packages.

```bash
# 1. Describe what you found, one entry per candidate
cat > plan.json <<'JSON'
[
  {"doi": "10.3233/IDA-163209", "category": "concept", "tier": "B",
   "keyword": "Survey + hybrid recommender systems", "area": "data science"}
]
JSON

# 2. Fill in every mechanical gate from Crossref + OpenAlex, and write the S6 checklist
python3 scripts/verify_source.py plan.json -o results.json --s6 s6-checklist.md

# 3. Render the verdicts and the reference list
python3 scripts/render_table.py results.json --lang en --evidence --bibliography apa
python3 scripts/render_table.py results.json --lang fa     # Persian table, Persian numerals

# 4. Fetch whatever open full text exists
python3 scripts/fetch_pdf.py results.json --out pdfs --report pdf-report.md --draft-emails emails.md

# 5. Check a draft against the writing rules
python3 scripts/check_draft.py draft.md --lang en
python3 scripts/check_draft.py draft.md --lang fa --manual manual.json
```

## What the tables look like

```
### Approved sources (all steps ticked)

| # | Article | Type | Tier | Category | 1 | 2 | 3 | ... | 11 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Placeholder Survey](https://doi.org/10.1000/x) (2024) | Journal | A | Concept | ✅ | ✅ | ✅ | ... | ✅ |

**Summary:** 1 approved · 1 pending · 1 rejected (Tier cut-off: B)
```

Full real output for both modes lives in [`references/output-example.md`](references/output-example.md) — it is generated from the fixtures in [`examples/`](examples), so it cannot go stale.

## Downloading full text

`fetch_pdf.py` asks OpenAlex, Unpaywall and Semantic Scholar, resolves arXiv ids, follows HTML→PDF links inside repository pages, and accepts a response as a PDF only if it starts with `%PDF-` and passes a size floor — because publishers answer with HTML error pages under HTTP 200.

When a paper is not open, the report names the licensed route and `--draft-emails` writes a ready-to-send request to the corresponding author.

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
python3 -m unittest discover tests      # 121 tests, ~0.03s, no network
```

The suite exists because four bug classes each silently produced a false ✅ or a false download:

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
scripts/              verify_source · render_table · fetch_pdf · check_draft · check_ids · http_util
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

