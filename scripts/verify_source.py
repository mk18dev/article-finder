#!/usr/bin/env python3
"""Verify source records and build an evidence-backed results file.

The plan contains candidate DOIs plus explicit review records. Metadata is
retrieved from Crossref/OpenAlex; reviewer-controlled gates remain pending
until their evidence is recorded. An abstract alone never proves reading depth,
an unrecorded specialization never passes, and a blacklist hit rejects S6.
A null step is "not verified", never "passed".
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

from check_ids import isbn10_valid, isbn13_valid, issn_valid
from http_util import fetch_json

RECENCY_YEARS = 5

TRUSTED_PUBLISHERS: tuple[str, ...] = (
    "IEEE", "Springer", "ACM", "Association for Computing Machinery", "Elsevier",
    "Taylor & Francis", "John Wiley", "Wiley",
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
FOUNDATIONAL_CATEGORIES: frozenset[str] = frozenset({"concept"})
RECENT_CATEGORIES: frozenset[str] = frozenset({"application", "methodology"})

CROSSREF_TYPE: dict[str, str | None] = {
    "journal-article": "journal",
    "proceedings-article": "conference",
    "book-chapter": "book_chapter",
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
    isbns: list[str] = field(default_factory=list)
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
        isbns=[i for i in message.get("ISBN", []) if i],
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
    current_year = date.today().year
    if work.year > current_year:
        return False
    if category in FOUNDATIONAL_CATEGORIES:
        return True
    if category in RECENT_CATEGORIES:
        return work.year >= current_year - RECENCY_YEARS
    return True if work.year >= current_year - RECENCY_YEARS else None


def evidence_item_ok(item: Any) -> bool:
    if not isinstance(item, dict) or item.get("reviewed") is not True:
        return False
    url = item.get("url")
    note = item.get("note")
    if not isinstance(url, str) or not isinstance(note, str) or len(url) > 4096:
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    valid_https = (
        parsed.scheme.lower() == "https" and bool(host)
        and parsed.username is None and parsed.password is None
        and port in (None, 443)
    )
    legacy_blacklist_http = (
        item.get("allow_legacy_blacklist_http") is True
        and parsed.scheme.lower() == "http" and host == "impactfactor.ir"
        and parsed.username is None and parsed.password is None
        and port in (None, 80)
    )
    return (valid_https or legacy_blacklist_http) and len(note.strip()) >= 8


def judgement(entry: dict[str, Any], step: str) -> bool | None:
    judgements = entry.get("judgements")
    if not isinstance(judgements, dict):
        return None
    item = judgements.get(step)
    if not isinstance(item, dict) or not evidence_item_ok({
        "reviewed": item.get("reviewed"),
        "url": item.get("evidence_url"),
        "note": item.get("note"),
    }):
        return None
    value = item.get("ok")
    return value if isinstance(value, bool) else None


def source_type_ok(work: Work, entry: dict[str, Any]) -> bool | None:
    if work.kind not in {"journal", "conference", "book", "thesis"}:
        return False
    if work.kind == "thesis":
        degree = str(entry.get("degree", "")).strip().lower()
        if not degree:
            return None
        if degree in {"bachelor", "bachelors", "undergraduate", "bsc", "ba"}:
            return False
        if degree not in {"master", "masters", "msc", "ma", "phd", "doctoral", "doctorate"}:
            return None
        if not evidence_item_ok(entry.get("degree_evidence")):
            return None
    return True


def identifiers_ok(work: Work, entry: dict[str, Any]) -> bool | None:
    if work.kind == "journal":
        if not work.issns:
            return None
        if not all(issn_valid(i.replace("-", "")) for i in work.issns):
            return False
        if not work.volume or not work.issue:
            return None
        return True
    if work.kind == "conference":
        if not work.doi or not work.container:
            return False
        if not entry.get("conference_edition") or not entry.get("conference_venue"):
            return None
        return True if evidence_item_ok(entry.get("conference_evidence")) else None
    if work.kind == "book":
        if entry.get("main_book") is False:
            return False
        if entry.get("main_book") is not True:
            return None
        if not work.isbns:
            return None
        if not all(isbn10_valid(i.replace("-", "").replace(" ", "")) or
                   isbn13_valid(i.replace("-", "").replace(" ", "")) for i in work.isbns):
            return False
        return True if evidence_item_ok(entry.get("book_evidence")) else None
    if work.kind == "thesis":
        record_id = str(entry.get("record_id", "")).strip()
        repository_url = str(entry.get("repository_url", "")).strip()
        institution = str(entry.get("institution", "")).strip()
        if not record_id or not institution or not repository_url.startswith("https://"):
            return None
        return True if evidence_item_ok(entry.get("thesis_evidence")) else None
    return None


def s6_gate(work: Work, entry: dict[str, Any]) -> bool | None:
    def verified_record(item: Any) -> bool:
        return isinstance(item, dict) and evidence_item_ok({
            "reviewed": item.get("verified"),
            "url": item.get("url"),
            "note": item.get("note"),
        })

    if work.kind in {"journal", "conference"}:
        if work.kind == "journal":
            blacklist = str(entry.get("blacklist_status", "")).strip().lower()
            if blacklist in {"listed", "blacklisted"}:
                return False
            blacklist_evidence = entry.get("blacklist_evidence")
            if blacklist != "clear" or not isinstance(blacklist_evidence, dict) or not evidence_item_ok({
                **blacklist_evidence,
                "allow_legacy_blacklist_http": True,
            }):
                return None
        accepted = {"scopus", "web of science", "wos", "isc", "dblp"}
        for item in entry.get("indexing_evidence", []) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("index", "")).strip().lower()
            if name in accepted and verified_record(item):
                return True
        return None

    if work.kind == "thesis":
        item = entry.get("thesis_repository_evidence")
        if not isinstance(item, dict):
            return None
        repository = str(item.get("repository", item.get("index", ""))).strip().lower()
        accepted = {"irandoc", "university repository", "institutional repository"}
        return True if repository in accepted and verified_record(item) else None

    if work.kind == "book":
        item = entry.get("book_s6_evidence")
        if not isinstance(item, dict):
            return None
        source = str(item.get("source", item.get("index", ""))).strip().lower()
        citation_count = item.get("citation_count")
        citation_count_valid = (
            isinstance(citation_count, int) and not isinstance(citation_count, bool)
            and citation_count >= 0
        )
        publisher_verified = item.get("publisher_verified") is True
        accepted = {"google books", "amazon"}
        return True if (
            source in accepted and citation_count_valid and publisher_verified
            and verified_record(item)
        ) else None

    return False


def s11_gate(work: Work, entry: dict[str, Any], category: str) -> bool | None:
    reading = entry.get("reading_evidence")
    if not isinstance(reading, dict):
        return None
    if category == "methodology":
        required = ["full_text"]
    elif work.kind in {"journal", "conference"}:
        required = ["abstract", "introduction", "conclusion"]
    elif work.kind in {"book", "thesis"}:
        required = ["chapter_1", "chapter_2"]
    else:
        return None
    return True if all(evidence_item_ok(reading.get(key)) for key in required) else None


def tier_verified(entry: dict[str, Any]) -> bool:
    tier = str(entry.get("tier", "")).upper()
    evidence = entry.get("tier_evidence")
    if not isinstance(evidence, dict):
        return False
    return tier in {"A", "B", "C", "D"} and evidence_item_ok({
        "reviewed": evidence.get("verified"),
        "url": evidence.get("url"),
        "note": evidence.get("basis"),
    })


def s6_links(work: Work) -> list[str]:
    title = urllib.parse.quote(work.title)
    if work.kind == "thesis":
        return ["[Irandoc](https://irandoc.ac.ir/)"]
    if work.kind == "book":
        isbn = work.isbns[0] if work.isbns else ""
        query = urllib.parse.quote(isbn or work.title)
        return [
            f"[Google Books](https://books.google.com/books?q={query})",
            f"[Amazon](https://www.amazon.com/s?k={query})",
        ]
    if work.kind == "conference":
        return [f"[DBLP]({DBLP}{title})"]
    key = work.source_issn or (work.issns[0] if work.issns else "")
    links: list[str] = [f"[blacklist + IF]({IMPACTFACTOR})"]
    if key:
        links.extend([
            f"[SCImago]({SCI_MAGO}{key})",
            f"[Clarivate MJL]({CLARIVATE}{key})",
            f"[DOAJ]({DOAJ}{key}%22%7D%7D%7D)",
        ])
    return links


def decide(work: Work, entry: dict[str, Any]) -> dict[str, Any]:
    category = str(entry.get("category", "")).lower()
    tier = str(entry.get("tier", "")).upper()
    tier_ok = tier_verified(entry)
    keyword = str(entry.get("keyword", "")).strip()
    declared_area = str(entry.get("area", "")).strip()
    subject = str(entry.get("subject", "")).strip()

    keyword_format_ok = keyword_gate(keyword)
    search = entry.get("search_evidence") or {}
    search_ok = (
        keyword_format_ok
        and isinstance(search, dict)
        and str(search.get("query", "")).strip() == keyword
        and str(search.get("doi", "")).strip().lower() == work.doi.lower()
        and str(search.get("url", "")).startswith("https://")
        and bool(str(search.get("searched_at", "")).strip())
    )
    recency = recency_ok(work, category)
    specialized = entry.get("specialized")
    specialization_evidence = entry.get("specialization_evidence")
    if specialized is False or recency is False:
        s8: bool | None = False
    elif (specialized is not True or not evidence_item_ok(specialization_evidence)
          or recency is None):
        s8 = None
    else:
        s8 = True

    publisher_ok = publisher_trusted(work.publisher) if work.publisher else None
    s5: bool | None = (
        True if publisher_ok else None
    ) if work.kind in {"journal", "conference"} else judgement(entry, "S5")

    s6 = s6_gate(work, entry)
    s7 = identifiers_ok(work, entry)
    s11 = s11_gate(work, entry, category)
    s4 = source_type_ok(work, entry)
    s10 = judgement(entry, "S10") if category in {
        "concept", "challenge", "application", "methodology"
    } else False

    steps: dict[str, bool | None] = {
        "S1": judgement(entry, "S1") if declared_area else None,
        "S2": judgement(entry, "S2") if subject else None,
        "S3": True if search_ok else (False if not keyword_format_ok else None),
        "S4": s4,
        "S5": s5,
        "S6": s6,
        "S7": s7,
        "S8": s8,
        "S10": s10,
        "S11": s11,
    }

    judgements = entry.get("judgements") or {}
    j1 = judgements.get("S1") if isinstance(judgements, dict) else None
    j2 = judgements.get("S2") if isinstance(judgements, dict) else None
    j10 = judgements.get("S10") if isinstance(judgements, dict) else None
    reading = entry.get("reading_evidence")
    if not isinstance(reading, dict):
        reading = {}
    evidence = {
        "S1": j1.get("note", "area judgement needs evidence") if isinstance(j1, dict) else "area judgement needs evidence",
        "S2": j2.get("note", "subject relevance needs evidence") if isinstance(j2, dict) else "subject relevance needs evidence",
        "S3": (f"search query: {keyword}; DOI matched: {work.doi}" if search_ok
               else "search execution and result-to-DOI evidence not supplied"),
        "S4": f"Crossref type -> {work.kind or 'unmapped'}; degree -> {entry.get('degree', 'not recorded')}",
        "S5": f"Crossref publisher: {work.publisher or 'unknown'}",
        "S6": (
            f"blacklist status={entry.get('blacklist_status', 'not checked')}; "
            f"index evidence={len(entry.get('indexing_evidence', []) or [])}"
            if work.kind == "journal" else
            f"conference index evidence={len(entry.get('indexing_evidence', []) or [])}"
            if work.kind == "conference" else
            f"thesis repository evidence={bool(entry.get('thesis_repository_evidence'))}"
            if work.kind == "thesis" else
            f"book S6 evidence={bool(entry.get('book_s6_evidence'))}; "
            f"citation count={(entry.get('book_s6_evidence') or {}).get('citation_count', 'missing')}"
            if work.kind == "book" else "unsupported source type"
        ),
        "S7": (", ".join(work.issns) if work.kind == "journal" else
               ", ".join(work.isbns) if work.kind == "book" else
               f"conference edition: {entry.get('conference_edition', 'missing')}; "
               f"venue: {entry.get('conference_venue', 'missing')}" if work.kind == "conference" else
               f"thesis record: {entry.get('record_id', 'missing')}"),
        "S8": f"year={work.year}; specialized={specialized!r}; "
              f"specialization evidence supplied={evidence_item_ok(specialization_evidence)}; "
              f"recency={recency!r}",
        "S10": j10.get("note", "category judgement needs evidence") if isinstance(j10, dict) else "category judgement needs evidence",
        "S11": f"reading evidence fields: {', '.join(reading.keys()) or 'none'}",
    }
    if work.kind == "journal" and work.in_doaj:
        evidence["S6-DOAJ"] = "OpenAlex reports is_in_doaj=true; this alone does not complete S6"

    notes_en: list[str] = []
    notes_fa: list[str] = []
    if s6 is False:
        notes_en.append("S6 rejected: the source is marked as listed on an Iranian blacklist.")
        notes_fa.append("S6 رد شد: منبع به‌عنوان مورد فهرست سیاه ایران ثبت شده است.")
    elif s6 is None:
        if work.kind == "journal":
            notes_en.append("S6 pending: record a checked blacklist result and a verified Scopus/WoS/ISC/DBLP record.")
            notes_fa.append("S6 در انتظار است: نتیجه بررسی فهرست سیاه و مدرک نمایه‌سازی Scopus/WoS/ISC/DBLP را ثبت کن.")
        elif work.kind == "conference":
            notes_en.append("S6 pending: verify the conference proceedings in Scopus, Web of Science, ISC or DBLP.")
            notes_fa.append("S6 در انتظار است: نمایه‌شدن مجموعه‌مقالات کنفرانس را در Scopus، Web of Science، ISC یا DBLP تأیید کن.")
        elif work.kind == "thesis":
            notes_en.append("S6 pending: verify the thesis record in Irandoc or an official university repository.")
            notes_fa.append("S6 در انتظار است: رکورد پایان‌نامه را در ایرانداک یا مخزن رسمی دانشگاه تأیید کن.")
        elif work.kind == "book":
            notes_en.append("S6 pending: verify the Google Books/Amazon record, citation count and publisher.")
            notes_fa.append("S6 در انتظار است: رکورد Google Books/Amazon، تعداد استناد و ناشر کتاب را تأیید کن.")
        else:
            notes_en.append("S6 pending: unsupported source type.")
            notes_fa.append("S6 در انتظار است: نوع منبع پشتیبانی نمی‌شود.")
    if s4 is None:
        notes_en.append("S4 pending: the thesis degree must be recorded; undergraduate theses are rejected.")
        notes_fa.append("S4 در انتظار است: مقطع پایان‌نامه باید ثبت شود؛ پایان‌نامه کارشناسی رد می‌شود.")
    if steps["S3"] is None:
        notes_en.append("S3 pending: add the executed search query, result URL, DOI match and date.")
        notes_fa.append("S3 در انتظار است: عبارت جست‌وجوشده، نشانی نتیجه، DOI منطبق و تاریخ را ثبت کن.")
    if s7 is None:
        notes_en.append("S7 pending: complete the source-type identifier and edition/record evidence.")
        notes_fa.append("S7 در انتظار است: شناسه متناسب با نوع منبع و مدرک ویرایش/رکورد را کامل کن.")
    if s8 is None:
        notes_en.append("S8 pending: specialization must be explicitly reviewed; missing data is not a pass.")
        notes_fa.append("S8 در انتظار است: تخصصی‌بودن باید صریح بررسی شود؛ داده مفقود تأیید محسوب نمی‌شود.")
    if s11 is None:
        if category == "methodology":
            notes_en.append("S11 pending: full text is required for Methodology; attach the full-text reading record.")
            notes_fa.append("S11 در انتظار است: برای دسته روش‌شناسی مطالعه متن کامل لازم است؛ مدرک مطالعه متن کامل را ثبت کن.")
        else:
            notes_en.append("S11 pending: attach the reading record required for the source category and type.")
            notes_fa.append("S11 در انتظار است: سابقه مطالعه متناسب با دسته و نوع منبع را ثبت کن.")
    if s5 is None:
        notes_en.append(f"Publisher/venue requires confirmation: {work.publisher or 'not recorded'}.")
        notes_fa.append(f"ناشر/محل انتشار نیاز به تأیید دارد: {work.publisher or 'ثبت نشده'}.")
    if not tier_ok:
        notes_en.append("S9 pending: the A-D tier needs a reviewer note and a source URL.")
        notes_fa.append("S9 در انتظار است: رتبه A تا D به توضیح ارزیاب و نشانی مدرک نیاز دارد.")
    for key in ("S1", "S2", "S10"):
        if steps[key] is None:
            notes_en.append(f"{key} pending: add a documented research judgement.")
            notes_fa.append(f"{key} در انتظار است: قضاوت پژوهشی مستند ثبت کن.")
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
        "tier": tier if tier_ok else "",
        "tier_verified": tier_ok,
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
    rows.append("After checking the blacklist, record blacklist_status as clear or listed "
                "in the plan. For a positive index result, add indexing_evidence with index, "
                "verified=true, source URL and a short note, then rerun verify_source.py.")
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
            "doaj": work.in_doaj, "isbns": work.isbns, "s6_links": s6_links(work),
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



