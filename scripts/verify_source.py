#!/usr/bin/env python3
"""Verify source records and build the article-finder results file.

Usage:
    python3 verify_source.py plan.json [-o results.json] [--s6 s6-checklist.md]
    python3 verify_source.py --doi 10.1145/2645710.2645757

plan.json: a list of entries, one per candidate source:
    [{"doi": "10.1145/...", "category": "concept|challenge|application|methodology",
      "tier": "A|B|C|D", "keyword": "keyword pair that found it",
      "specialized": true, "type_hint": "journal|conference"}]

What the script decides by itself, from the Crossref record and the OpenAlex
record: title, authors, year, venue, volume/issue/pages, publisher, ISSN list,
abstract, citation count, and every step that follows from them (S4, S5, S7,
S8, S11). ISSN checksums come from check_ids.py.

What it cannot decide, and why: S1 area, S2 subject, S3 keyword and S10
category are judgments about the research, so they are taken from the plan and
reported as caller-declared. S6 indexing has no public API: Scopus and Web of
Science expose membership only through Clarivate and SciMago, which block
scripted clients. S6 therefore stays null (pending, never approved) and the
checklist file lists the exact URL a human has to open for each source.

A null step is "not verified", never "passed". `render_table.py` turns that
into a pending row and refuses to approve it.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_ids import issn_valid
from http_util import fetch_json

RECENCY_YEARS = 5

TRUSTED_PUBLISHERS: tuple[str, ...] = (
    "IEEE", "Springer", "ACM", "Association for Computing Machinery", "Elsevier",
    "Taylor & Francis", "Wiley", "SAGE", "IOP", "MDPI", "Frontiers", "IOS Press",
)
COURSE_KEYWORDS: tuple[str, ...] = (
    "tutorial", "survey", "overview", "an introduction", "bibliography", "references",
    "archive", "method", "technique", "algorithm", "model", "concept", "thesis",
    "taxonomy", "approach", "books",
)
STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "these", "those", "into",
    "towards", "toward", "based", "using", "their", "there", "which", "system",
    "systems", "approach", "model", "models", "study", "paper", "review",
})
FOUNDATIONAL_CATEGORIES: frozenset[str] = frozenset({"concept", "challenge"})
RECENT_CATEGORIES: frozenset[str] = frozenset({"application", "methodology"})

CROSSREF_TYPE: dict[str, str | None] = {
    "journal-article": "journal",
    "proceedings-article": "conference",
    "book-chapter": "book",
    "book": "book",
    "monograph": "book",
    "dissertation": "thesis",
}

SCI_MAGO = "https://www.scimagojr.com/journalsearch.php?q="
CLARIVATE = "https://mjl.clarivate.com/search-results?issn="
DOAJ = "https://doaj.org/search/journals?source=%7B%22query%22%3A%7B%22query_string%22%3A%7B%22query%22%3A%22"
DBLP = "https://dblp.org/search?q="
IMPACTFACTOR = "http://impactfactor.ir/"


@dataclass
class Work:
    doi: str
    title: str
    container: str
    publisher: str
    issns: list[str]
    volume: str
    issue: str
    pages: str
    year: int | None
    authors: list[str]
    kind: str | None
    abstract: str = ""
    cited_by: int | None = None
    source_name: str = ""
    source_issn: str = ""
    in_doaj: bool = False
    notes: list[str] = field(default_factory=list)


def keyword_gate(keyword: str) -> bool:
    lead, separator, research = keyword.partition("+")
    return bool(separator and research.strip()) and lead.strip().lower() in COURSE_KEYWORDS


def subject_signal(keyword: str, work: Work) -> bool | None:
    tokens = [
        token for token in re.split(r"[^0-9a-z-]+", keyword.lower())
        if len(token) >= 4 and token not in STOPWORDS
    ]
    if not tokens:
        return None
    haystack = f"{work.title} {work.abstract}".lower()
    return True if any(token in haystack for token in tokens) else None


def initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p]
    return " ".join(f"{p[0]}." for p in parts)


def crossref(doi: str) -> Work:
    message = fetch_json(f"https://api.crossref.org/works/{doi}")["message"]
    authors = [
        f"{a.get('family', '').strip()}, {initials(a.get('given', ''))}".strip(", ")
        for a in message.get("author", [])
        if a.get("family")
    ]
    issued = message.get("issued", {}).get("date-parts", [[None]])
    raw_type = str(message.get("type", ""))
    return Work(
        doi=str(message.get("DOI", doi)),
        title=(message.get("title") or ["(untitled)"])[0].strip(),
        container=(message.get("container-title") or [""])[0].strip(),
        publisher=str(message.get("publisher", "")).strip(),
        issns=[i for i in message.get("ISSN", []) if i],
        volume=str(message.get("volume", "")).strip(),
        issue=str(message.get("issue", "")).strip(),
        pages=str(message.get("page", "")).strip(),
        year=issued[0][0] if issued and issued[0] else None,
        authors=authors,
        kind=CROSSREF_TYPE.get(raw_type),
    )


def enrich(work: Work) -> Work:
    try:
        record = fetch_json(f"https://api.openalex.org/works/doi:{work.doi}")
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError):
        work.notes.append("OpenAlex record unavailable")
        return work
    inverted = record.get("abstract_inverted_index") or {}
    if inverted:
        positions = {p: w for w, ps in inverted.items() for p in ps}
        work.abstract = " ".join(positions[i] for i in sorted(positions))
    cited = record.get("cited_by_count")
    work.cited_by = int(cited) if isinstance(cited, int) else None
    source = (record.get("primary_location") or {}).get("source") or {}
    work.source_name = str(source.get("display_name", "") or "")
    work.source_issn = str(source.get("issn_l", "") or "")
    work.in_doaj = bool(source.get("is_in_doaj"))
    return work


def publisher_trusted(publisher: str) -> bool:
    lowered = publisher.lower()
    return any(name.lower() in lowered for name in TRUSTED_PUBLISHERS)


def venue_text(work: Work) -> str:
    volume = "" if work.volume in {"", "0"} else work.volume
    issue = "" if work.issue in {"", "0"} else work.issue
    pages = "" if work.pages in {"", "0", "0-0"} else work.pages
    tail = f"{volume}({issue})" if issue else volume
    parts = [work.container, tail, pages]
    return ", ".join(p for p in parts if p)


def recency_ok(work: Work, category: str) -> bool | None:
    if work.year is None:
        return None
    if category in FOUNDATIONAL_CATEGORIES:
        return True
    return work.year >= date.today().year - RECENCY_YEARS


def identifiers_ok(work: Work) -> bool | None:
    if work.kind == "conference":
        return bool(work.container and work.doi)
    if not work.issns:
        return None
    return all(issn_valid(i.replace("-", "")) for i in work.issns)


def s6_links(work: Work) -> list[str]:
    key = work.source_issn or (work.issns[0] if work.issns else "")
    links: list[str] = [f"[blacklist + IF]({IMPACTFACTOR})"]
    if not key:
        return links + [f"[DBLP]({DBLP}{urllib.parse.quote(work.title)})"] if work.kind == "conference" else links
    if key:
        links.append(f"[SCImago]({SCI_MAGO}{key})")
        links.append(f"[Clarivate MJL]({CLARIVATE}{key})")
    if work.in_doaj or key:
        links.append(f"[DOAJ]({DOAJ}{key}%22%7D%7D%7D)")
    if work.kind == "conference":
        links.append(f"[DBLP]({DBLP}{urllib.parse.quote(work.title)})")
    return links


def decide(work: Work, entry: dict[str, Any]) -> dict[str, Any]:
    category = str(entry["category"]).lower()
    tier = str(entry.get("tier", "")).upper()
    specialized = bool(entry.get("specialized", True))
    trusted = publisher_trusted(work.publisher) if work.publisher else None
    recency = recency_ok(work, category)

    keyword = str(entry.get("keyword", ""))
    declared_area = str(entry.get("area", "")).strip()
    subject = False if entry.get("subject") is False else subject_signal(keyword, work)

    steps: dict[str, bool | None] = {
        "S1": True if declared_area else None,
        "S2": subject,
        "S3": keyword_gate(keyword),
        "S4": work.kind is not None,
        "S5": True if trusted else None,
        "S6": None,
        "S7": identifiers_ok(work),
        "S8": None if recency is None else bool(recency and specialized),
        "S10": category in {"concept", "challenge", "application", "methodology"},
        "S11": None if category == "methodology" or not work.abstract else True,
    }

    evidence = {
        "S1": f"declared area: {declared_area or 'none given'}",
        "S2": "keyword matches title/abstract" if subject else "no keyword token found in title/abstract",
        "S3": f"course keyword + research keyword: {keyword or 'none given'}",
        "S4": f"Crossref type -> {work.kind or 'unmapped'}",
        "S5": f"Crossref publisher: {work.publisher or 'unknown'}",
        "S7": ", ".join(work.issns) + " (check_ids.py)" if work.issns else "conference: edition/venue + DOI",
        "S8": f"{work.year} vs {date.today().year - RECENCY_YEARS} cut-off ({category})",
        "S11": "OpenAlex abstract" if work.abstract else "no abstract retrieved",
    }
    if work.in_doaj:
        evidence["S6-DOAJ"] = "OpenAlex reports is_in_doaj=true (not a substitute for Scopus/WoS)"

    notes_en = ["S6 pending: no public API reports Scopus/WoS membership; open the checklist links."]
    notes_fa = ["S6 در انتظار: هیچ API عمومی عضویت Scopus/WoS را گزارش نمی‌کند؛ لینک‌های فهرست را باز کن."]
    if trusted is False:
        notes_en.append(f"Publisher is not on the slide's list ({work.publisher}); confirm it is recognised.")
        notes_fa.append(f"ناشر در فهرست اسلاید نیست ({work.publisher})؛ معتبر بودنش را تأیید کن.")
    if steps["S3"] is False:
        notes_en.append("S3 failed: the keyword pair must be a course keyword plus the research keyword.")
        notes_fa.append("S3 رد شد: جفت کلیدواژه باید «کلیدواژهٔ اسلاید + کلیدواژهٔ پژوهش» باشد.")
    if category == "methodology":
        notes_en.append("S11 stays pending for a methodology source: the full text is required, not the abstract.")
        notes_fa.append("S11 برای منبع روش‌شناسی در انتظار می‌ماند: متن کامل لازم است، نه چکیده.")
    for note in work.notes:
        notes_en.append(note)
        notes_fa.append("رکورد OpenAlex در دسترس نبود." if note.startswith("OpenAlex") else note)

    return {
        "title": work.title,
        "authors": work.authors,
        "year": work.year,
        "type": work.kind or "unknown",
        "venue": venue_text(work),
        "publisher": work.publisher,
        "url": f"https://doi.org/{work.doi}",
        "doi": work.doi,
        "category": category,
        "tier": tier,
        "keyword": keyword,
        "cited_by": work.cited_by,
        "steps": steps,
        "evidence": evidence,
        "notes": {"en": " ".join(notes_en), "fa": " ".join(notes_fa)},
    }


def build(entry: dict[str, Any]) -> tuple[dict[str, Any], Work]:
    work = enrich(crossref(str(entry["doi"])))
    return decide(work, entry), work


def checklist(articles: list[dict[str, Any]], works: list[Work]) -> str:
    rows = ["# S6 indexing checklist", "",
            "Every row needs a human: no public API exposes Scopus or Web of Science membership.", "",
            "Start each row on the **blacklist** link. A journal listed on the blacklist of the two "
            "ministries or Islamic Azad University is a rejection at S6 (`validation.md` §2), not a "
            "tier downgrade, so the other links do not matter once that one hits.", "",
            "| # | Source | Publisher | ISSN | Open |", "|---|---|---|---|---|"]
    for index, (article, work) in enumerate(zip(articles, works), 1):
        issns = ", ".join(work.issns) or "-"
        rows.append(f"| {index} | {article['title']} | {work.publisher} | {issns} | "
                    + " · ".join(s6_links(work)) + " |")
    rows.append("")
    rows.append("Mark a row verified only after you see the journal's record on an index page, "
                "then set `\"S6\": true` in the results file and re-run `render_table.py`.")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify sources and build the results file.")
    parser.add_argument("plan", nargs="?", help="JSON list of {doi, category, tier, keyword}")
    parser.add_argument("--doi", help="single DOI; prints the record instead of writing a plan")
    parser.add_argument("-o", "--out", default="results.json", help="results file to write")
    parser.add_argument("--s6", help="write the S6 checklist markdown here")
    parser.add_argument("--cutoff", default="B", choices=["A", "B", "C", "D"])
    args = parser.parse_args()

    if args.doi:
        work = enrich(crossref(args.doi))
        print(json.dumps({
            "title": work.title, "authors": work.authors, "year": work.year,
            "venue": venue_text(work), "publisher": work.publisher, "issns": work.issns,
            "kind": work.kind, "abstract": work.abstract[:280], "cited_by": work.cited_by,
            "doaj": work.in_doaj, "s6_links": s6_links(work),
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.plan:
        parser.error("give a plan file or --doi")

    entries = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    articles: list[dict[str, Any]] = []
    works: list[Work] = []
    for entry in entries:
        article, work = build(entry)
        articles.append(article)
        works.append(work)
        state = sum(1 for v in article["steps"].values() if v is True)
        unknown = sum(1 for v in article["steps"].values() if v is None)
        print(f"{article['title'][:58]:<58} ok={state:<2} pending={unknown:<2} {article['type']}")

    payload = {"cutoff": args.cutoff.upper(), "articles": articles}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}: {len(articles)} sources")

    if args.s6:
        Path(args.s6).write_text(checklist(articles, works), encoding="utf-8")
        print(f"wrote {args.s6}: {len(articles)} rows, S6 unverified by design")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



