# Validation gates and tier rubric

Contents: 1 Conference papers · 2 Journal papers · 3 Theses · 4 Books · 5 Ranking and tiers · 6 Where to verify · 7 Worked example from the slides · 8 Getting the full text · 9 Red flags

Each section lists what to check, then which step (S5-S8) it feeds. Items marked *(skill)* are this skill's additions, not slide content.

## 1. Conference papers (slides, pages 15-16)

Check:
- Conference Edition Number
- Conference Proceedings Publisher: IEEE, Springer, ACM, Elsevier
- National or International Conference
- Conference Specialization
- Conference Venue

Feeds: publisher → S5 · indexing (Scopus / WoS / DBLP) → S6 · edition + venue (+ DOI) → S7 · specialization + year → S8.

## 2. Journal papers (slides, pages 17-25)

The eight checks on the slide:
1. Journal Volume, Number, Issue
2. Journal Proceedings Publisher: IEEE, Springer, ACM, Elsevier, Taylor & Francis, John Wiley
3. Who has Indexed that Journal: ISI, Scopus, ISC, "DBLE" (the slide's spelling; read here as DBLP, the computer-science bibliography. If the user means something else, ask)
4. The level of Specialization of the Journal
5. Year of Publication, Journal
6. Article Volume Journal (the slide gives no explanation; read as the journal volume the article appeared in)
7. Number of Articles Published in Each Issue of the Journal (no threshold on the slide; an unusually large number is a warning sign *(skill)*)
8. The Time of the Journal: Monthly, Bimonthly, Quarterly

**Volume / Number / Issue** exactly as on the slide:
- Volume: indicates the publication year number of a journal / date of birth. Example: Vol. 8.
- Number: the total number of the journal within a year. Example: No.48 = 8*6.
- Issue: specifies the number of issues of a journal within a specific year. Example: Issue = 5.

*(skill)* The example 48 = 8×6 only works if Number counts issues cumulatively (8 volumes × 6 issues of a bimonthly), even though the slide's sentence says "within a year". The consistency check below is built on that example. If the journal's own pages number things differently, trust the journal and write what you saw in the notes. For a journal with P issues per year, Number should fall in `((Volume−1)·P, Volume·P]`, so Vol. 8 of a bimonthly (P = 6) gives 43-48, and Issue 5 gives No. 47. Skip the check when "volume" is just the calendar year.

**Identifiers** (page 21): ISSN (International Standard Serial Number) → journal · EISSN (Electronic ISSN) → journal · PISSN (Print ISSN) → journal · ISBN (International Standard Book Number) → book. Validate the checksums with `scripts/check_ids.py`.

**Blacklist** *(skill)*: the impact-factor site on the slides also reports whether the journal is on the blacklist of the two ministries and Islamic Azad University. Treat a listing there as a rejection at S6.

Feeds: publisher → S5 · indexing + blacklist → S6 · ISSN + volume/number/issue consistency → S7 · specialization + year → S8.

## 3. Theses (slides, pages 28-29)

Six points on the slide:
- The necessity of eliminating undergraduate theses (reject at S4)
- The necessity of focusing on doctoral dissertations
- The necessity of paying attention to Persian theses (do not discard a thesis just for language)
- Tracking these based on reputable journal articles
- Affiliated university
- Year of thesis publication

Site: Irandoc, https://irandoc.ac.ir/

Feeds: degree + university → S5 · Irandoc / university repository record → S6 · record identifier + derived articles → S7 · year → S8.

## 4. Books (slides, pages 30-31)

Seven points on the slide:
- The necessity of distinguishing the main book from a collection of articles
- The necessity of carefully reviewing the book's table of contents
- The necessity of focusing on the main text of the book
- Author of the book
- Number of citations to the book
- Publisher of the book
- Year of publication

Sites on the slide: Google Books https://books.google.com · Amazon https://www.amazon.com · Z-Lib https://z-lib.io/ (see section 8 about Z-Lib).

Feeds: publisher → S5 · Google Books/Amazon record + citation count → S6 · ISBN (validate with `scripts/check_ids.py`) → S7 · year → S8.

## 5. Ranking and tiers (slides, pages 32-33)

The course's three ranking steps:
1. Classification of references based on different validation tiers (A, B, C, D)
2. Identification of credible references based on the established classification
3. Elimination of all references that do not meet the minimum credibility standards

The slides give no tier definitions. The rubric below is this skill's **default** *(skill)*; tell the user so, and adjust if their department sets other rules.

| Tier | Journal | Conference | Thesis | Book |
|---|---|---|---|---|
| **A** | WoS (SCIE/SSCI/AHCI) or Scopus, best quartile Q1-Q2, recognized publisher, specialized | Proceedings by IEEE/ACM/Springer/Elsevier, international, established series, indexed | PhD dissertation, reputable university, derived papers found in A/B journals | Main book, recognized publisher, strong citations, relevant chapters |
| **B** | WoS/Scopus Q3-Q4 or ESCI, recognized publisher | Same publishers, international, newer or less specialized series | PhD dissertation without traceable derived papers | Main book, recognized publisher, modest citations |
| **C** | Only ISC/DBLP or a regional index; or indexed but off-specialization | National conference with a proceedings record | Master's thesis with traceable derived papers | Main book from a lesser-known publisher |
| **D** | Not indexed, unverifiable, blacklisted, or red flags | No proceedings publisher or unverifiable | Master's thesis without derived papers | Collection of articles, no ISBN or no publisher |

State which quartile source you used (SJR vs JCR); they can differ (see section 7). Default cut-off is **B**: A and B are kept, C and D are eliminated.

## 6. Where to verify (slides, pages 22-24, 26)

| Question | Source (as printed on the slides) |
|---|---|
| Is the journal ISI-indexed? Master Journal List | https://mjl.clarivate.com/ |
| Impact factor and list presence (Persian-language site) | http://impactfactor.ir/ |
| SJR | https://www.scimagojr.com |
| DOAJ | https://doaj.org |
| Persian theses | https://irandoc.ac.ir/ |
| Books | https://books.google.com · https://www.amazon.com |
| Good sites (page 26) | IEEE https://ieeexplore.ieee.org · Springer https://link.springer.com · Elsevier https://www.sciencedirect.com/search · Google Scholar https://scholar.google.com/ |

*(skill)* Computer-science venues can also be checked on https://dblp.org. Clarivate and Scholar pages often load only in a browser; if WebFetch cannot read them, fall back to SJR or the publisher's journal page, and mark WoS status ❓ with a note telling the user to check the Master Journal List.

## 7. Worked example from the slides (pages 22-23)

Journal: *Data Mining and Knowledge Discovery*. Figures are as printed on the slides, not re-verified; use this as a model of a complete check.

**Master Journal List** (page 22):
- Publisher: Springer, Van Godewijckstraat 30, Dordrecht, Netherlands, 3311 GZ
- ISSN / eISSN: 1384-5810 / 1573-756X
- Web of Science Core Collection: Science Citation Index Expanded
- Additional Web of Science indexes: Current Contents Engineering, Computing & Technology | Essential Science Indicators
- The screenshot also shows four active filters (SCIE, SSCI, AHCI, ESCI) with "Found 0 results (Page 1)" below. The slide does not explain this; do not copy that part of the screen.

**impactfactor.ir** (page 23; the site's messages are in Persian):
- Found in the Scopus-indexed list. SJR trend 2019-2024. Table: CiteScore (2023) 10.4 · SJR (2024) 1.019 · H index (2024) 123 · Best Quartile (based on SCImago) Q1.
- Found in the JCR-indexed list. Impact-factor trend 2018-2023. Table: IF (2021) 5.406 · IF (2022) 4.8 · IF (2023) 2.8 · 5-year IF 5.3 · Best Quartile Q2.
- Found in the Master Journal List (coverage: Science Citation Index Expanded, Current Contents Engineering Computing & Technology, Essential Science Indicators).
- Not found in the blacklist of the two ministries and Islamic Azad University (shown green = good).
- Not found in DOAJ open-access list; not found in Medline or PMC (shown red; these are absences, not failures).

Lesson: the best quartile is Q1 by SJR and Q2 by JCR, so always say which source a quartile comes from.

## 8. Getting the full text (slides, pages 26-27, 31)

Page 27, "Download Article", lists three sites, reproduced as printed:
- Sci-hub: https://sci-hub.st
- Iran Paper: https://iranpaper.ir/
- Libgen: http://libgen.is/

Page 31 adds Z-Lib (https://z-lib.io/) next to Google Books and Amazon.

How the skill treats them: `scripts/fetch_pdf.py` does the fetching and only ever follows open-access links (OpenAlex best-OA location, arXiv, author copies), so none of the three is reachable from the toolchain. Iran Paper is an Iranian paper-access service (check its terms and prices). Sci-hub, Libgen and Z-Lib distribute copyrighted papers and books without the publishers' permission, so Claude does not fetch from them, verify sources through them, or recommend them. They stay on this page only so the record of the slides is complete, and the choice of whether to use them is the user's own. For the same papers, Claude offers the routes that give a legitimate copy:
- the publisher page (IEEE Xplore, SpringerLink, ScienceDirect)
- Google Scholar's PDF and "all versions" links to open copies
- author pages and preprint servers
- the user's university or library access
- emailing the corresponding author

## 9. Red flags *(skill)*

Missing or invalid ISSN, publisher not identifiable, Number inconsistent with Volume, very large issues with unrelated topics, no named editorial board. Any one of these is reason to drop the tier by one level or to reject.

## 10. Which gates a script can decide *(skill)*

`scripts/verify_source.py` reads the Crossref record and the OpenAlex record for a DOI and fills the results file. The split is deliberate:

| Gate | Decided by | Evidence source |
|---|---|---|
| S4 Source type | script | Crossref `type` mapped to journal / conference / book / thesis |
| S5 Publisher | script, one-sided | Crossref `publisher`, matched against the slide's publisher list; a publisher outside that list stays ❓, never ❌ |
| S7 Identifiers | script | ISSN checksums via `check_ids.py`; for a conference, edition + venue + DOI |
| S8 Specialization & year | script, partly | Crossref year against the recency rule; specialization is declared in the plan |
| S11 Extraction | script, partly | an OpenAlex abstract ticks Concept, Challenge and Application; a Methodology source always stays ❓ |
| S1, S2, S3, S10 | the model | judgments about the research, taken from the plan and reported as declared |
| S6 Indexing | the user | no API decides it — see the ladder below |

**Why S6 cannot be automated.** Scopus and Web of Science membership is exposed only through Clarivate and SciMago. In a live session these hosts refuse scripted clients (`scimagojr.com` HTTP 403 Cloudflare, `dblp.org` HTTP 202 Anubis, `mjl.clarivate.com` JavaScript-only). An agent that ticks S6 without opening one of those pages is guessing.

**Fallback ladder for S6**, stop at the first rung that answers:

0. **Iranian blacklist first** — `impactfactor.ir`: the list of the two ministries and Islamic Azad University. A listing there is a rejection at S6 (§2), so check it before spending time on quartiles. This is the one rung that can only drop a source, never promote it.
1. SCImago — `scimagojr.com/journalsearch.php?q=<ISSN>`: gives the SJR quartile, which also settles the tier.
2. Clarivate Master Journal List — `mjl.clarivate.com/search-results?issn=<ISSN>`: gives SCIE / SSCI / ESCI coverage.
3. DOAJ — `doaj.org`: open-access journals only, but a real record.
4. DBLP — `dblp.org/search?q=<title>`: accepted for computer-science conferences.
5. Nothing answers: S6 stays ❓ and the note names the page to open. The source is pending, not approved.

`verify_source.py --s6 checklist.md` writes every link above for every source, so the user works from a list instead of re-deriving the URLs.

