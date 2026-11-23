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
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_ids import isbn10_valid, isbn13_valid, issn_valid
from http_util import fetch_json
from tier_policy import compute_tier

RECENCY_YEARS = 5
BLACKLIST_MAX_AGE_DAYS = 730

TRUSTED_PUBLISHERS: tuple[str, ...] = (
    "ieee", "institute of electrical and electronics engineers", "ieee computer society",
    "springer", "springer nature", "springer nature switzerland", "springer nature america", "springer science and business media",
    "acm", "association for computing machinery", "elsevier",
    "mit press", "the mit press",
    "taylor francis", "taylor francis group", "taylor and francis", "john wiley", "john wiley sons", "wiley", "wiley blackwell",
)

INDEX_DOMAINS: dict[str, tuple[str, ...]] = {
    "scopus": ("scopus.com",),
    "web of science": ("mjl.clarivate.com", "webofscience.com"),
    "wos": ("mjl.clarivate.com", "webofscience.com"),
    "isi master journal list": ("mjl.clarivate.com",),
    "esci": ("mjl.clarivate.com", "webofscience.com"),
    "isc": ("isc.gov.ir",),
    "dblp": ("dblp.org",),
    "doaj": ("doaj.org",),
}
BLACKLIST_DOMAINS: dict[str, tuple[str, ...]] = {
    "msrt": ("journals.msrt.ir", "msrt.ir"),
    "mohme": ("research.behdasht.gov.ir", "behdasht.gov.ir"),
    "iau": ("eval.journals.iau.ir", "iau.ac.ir"),
}
MSRT_PORTAL = "https://journals.msrt.ir/"
MOHME_PORTAL = "https://research.behdasht.gov.ir/"
IAU_EVALUATION_PORTAL = "https://eval.journals.iau.ir/"
IMPACTFACTOR = "https://impactfactor.ir/"
SEARCH_DOMAINS: tuple[str, ...] = (
    "crossref.org", "openalex.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
    "semanticscholar.org", "arxiv.org", "ieeexplore.ieee.org", "dl.acm.org",
    "dblp.org", "scopus.com", "mjl.clarivate.com",
)
JOURNAL_METADATA_DOMAINS: tuple[str, ...] = (
    "sciencedirect.com", "link.springer.com", "ieeexplore.ieee.org", "dl.acm.org",
    "tandfonline.com", "onlinelibrary.wiley.com", "wiley.com", "journals.sagepub.com",
    "journals.plos.org", "frontiersin.org", "nature.com", "academic.oup.com",
    "cambridge.org", "journals.aps.org",
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
    is_retracted: bool | None = None
    is_paratext: bool | None = None
    updates: list[dict[str, str]] = field(default_factory=list)
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
    updates = []
    for update in message.get("update-to", []) or []:
        if isinstance(update, dict):
            updates.append({
                "type": str(update.get("type") or "update").strip().lower(),
                "doi": str(update.get("DOI") or "").strip().lower(),
                "label": str(update.get("label") or ""),
            })
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
        updates=updates,
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
    if isinstance(record.get("is_retracted"), bool):
        work.is_retracted = record["is_retracted"]
    if isinstance(record.get("is_paratext"), bool):
        work.is_paratext = record["is_paratext"]
    return work


def integrity_status(work: Work) -> str:
    update_types = [str(item.get("type") or "").lower() for item in work.updates]
    if work.is_retracted is True or any(any(term in kind for term in ("retract", "withdraw", "expression_of_concern")) for kind in update_types):
        return "retracted"
    if any(any(term in kind for term in ("correct", "errat", "corrigendum")) for kind in update_types):
        return "corrected"
    if work.is_paratext is True:
        return "paratext"
    if work.is_retracted is False:
        return "not_flagged"
    return "partial"


def publisher_trusted(publisher: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", publisher.casefold()).strip()
    tokens = normalized.split()
    legal_suffixes = {"b", "v", "inc", "ltd", "llc", "ag", "gmbh", "plc", "s", "a", "limited", "company"}
    while tokens and tokens[-1] in legal_suffixes:
        tokens.pop()
    normalized = " ".join(tokens)
    return normalized in TRUSTED_PUBLISHERS


def host_matches(url: str, domains: tuple[str, ...]) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        return (
            parsed.scheme.lower() == "https" and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and any(host == domain or host.endswith("." + domain) for domain in domains)
        )
    except ValueError:
        return False


def _valid_search_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, TypeError, OverflowError):
        return False


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
    reviewer_id = str(item.get("reviewer_id") or "").strip()
    locator = str(item.get("locator") or "").strip()
    if not reviewer_id or not locator or not _valid_search_timestamp(item.get("reviewed_at")):
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
    return valid_https and len(note.strip()) >= 8


def _normalized_index_title(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)


def _index_coverage_matches(item: dict[str, Any], work: Work) -> bool:
    matched_title = _normalized_index_title(item.get("matched_title"))
    expected_title = _normalized_index_title(work.title)
    start = item.get("coverage_start_year")
    end = item.get("coverage_end_year")
    if not expected_title or matched_title != expected_title:
        return False
    if (not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or start < 0 or end < start or work.year is None):
        return False
    return start <= work.year <= end


def verified_indexing_items(entry: dict[str, Any], work: Work) -> list[dict[str, Any]]:
    items = entry.get("indexing_evidence")
    if not isinstance(items, list):
        return []
    verified: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        index = str(item.get("index") or "").strip().lower()
        domains = INDEX_DOMAINS.get(index)
        # S6 records use the source-specific "verified" flag, while the
        # shared evidence validator expects the generic "reviewed" flag.
        # Adapt the schema here so the tier policy consumes the same evidence
        # that already passed the S6 gate; do not weaken evidence validation.
        evidence = {
            "reviewed": item.get("verified") is True,
            "reviewer_id": item.get("reviewer_id"),
            "reviewed_at": item.get("reviewed_at"),
            "locator": item.get("locator"),
            "url": item.get("url"),
            "note": item.get("note"),
        }
        if (domains and _index_coverage_matches(item, work)
                and evidence_item_ok(evidence)
                and host_matches(str(item.get("url") or ""), domains)):
            verified.append(item)
    return verified


def tier_evidence_valid(work: Work, entry: dict[str, Any]) -> bool:
    evidence = entry.get("tier_evidence")
    if not isinstance(evidence, dict):
        return False
    payload = {
        "reviewed": evidence.get("verified") is True,
        "reviewer_id": evidence.get("reviewer_id"),
        "reviewed_at": evidence.get("reviewed_at"),
        "locator": evidence.get("locator"),
        "url": evidence.get("url"),
        "note": evidence.get("basis"),
    }
    if not evidence_item_ok(payload):
        return False
    if work.kind == "journal":
        domains = (
            "scimagojr.com", "jcr.clarivate.com", "clarivate.com",
            *(domain for values in INDEX_DOMAINS.values() for domain in values),
            *(domain for values in BLACKLIST_DOMAINS.values() for domain in values),
        )
    elif work.kind == "conference":
        domains = ("ieeexplore.ieee.org", "dl.acm.org", "link.springer.com", "sciencedirect.com", "dblp.org")
    elif work.kind == "thesis":
        institution = str(entry.get("institution_domain") or "").strip().lower()
        domains = ("irandoc.ac.ir",) + ((institution,) if institution else ())
    elif work.kind == "book":
        domains = ("books.google.com", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.ca")
    else:
        return False
    return bool(domains) and host_matches(str(evidence.get("url") or ""), domains)


def judgement(entry: dict[str, Any], step: str) -> bool | None:
    judgements = entry.get("judgements")
    if not isinstance(judgements, dict):
        return None
    item = judgements.get(step)
    if not isinstance(item, dict) or not evidence_item_ok({
        "reviewed": item.get("reviewed"),
        "reviewer_id": item.get("reviewer_id"),
        "reviewed_at": item.get("reviewed_at"),
        "locator": item.get("locator"),
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


def _positive_int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    if not match:
        return None
    parsed = int(match.group(0))
    return parsed if parsed > 0 else None


def identifiers_ok(work: Work, entry: dict[str, Any]) -> bool | None:
    if work.kind == "journal":
        if not work.issns:
            return None
        if not all(issn_valid(i.replace("-", "")) for i in work.issns):
            return False
        volume = _positive_int(work.volume)
        issue = _positive_int(work.issue)
        if not volume or not issue:
            return None
        if entry.get("calendar_year_volume") is True:
            return True
        journal_number = _positive_int(entry.get("journal_number"))
        issues_per_year = _positive_int(entry.get("issues_per_year"))
        if not journal_number or not issues_per_year:
            return None
        if issue > issues_per_year:
            return False
        expected_number = (volume - 1) * issues_per_year + issue
        if journal_number != expected_number:
            return False
        number_evidence = entry.get("journal_number_evidence")
        if not evidence_item_ok(number_evidence):
            return None
        if not host_matches(str(number_evidence.get("url") or ""), JOURNAL_METADATA_DOMAINS):
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
        if not all(isbn10_valid(i.replace("-", "").replace(" ", "").upper()) or
                   isbn13_valid(i.replace("-", "").replace(" ", "").upper()) for i in work.isbns):
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


def _normalize_issn(value: Any) -> str:
    return re.sub(r"[^0-9x]", "", str(value or "").casefold())


def blacklist_gate(work: Work, entry: dict[str, Any]) -> bool | None:
    checks = entry.get("blacklist_checks")
    if not isinstance(checks, list):
        return None
    valid_issns = {_normalize_issn(value) for value in work.issns if _normalize_issn(value)}
    by_authority: dict[str, dict[str, Any]] = {}
    incomplete = False
    for item in checks:
        if not isinstance(item, dict):
            incomplete = True
            continue
        authority = str(item.get("authority") or "").strip().lower()
        if authority not in BLACKLIST_DOMAINS:
            incomplete = True
            continue
        duplicate = authority in by_authority
        if str(item.get("query_type") or "").strip().lower() != "issn":
            incomplete = True
            continue
        if _normalize_issn(item.get("query_value")) not in valid_issns:
            incomplete = True
            continue
        if not str(item.get("list_version") or "").strip():
            incomplete = True
            continue
        try:
            list_updated = date.fromisoformat(str(item.get("list_updated_at") or ""))
        except ValueError:
            incomplete = True
            continue
        list_age = (date.today() - list_updated).days
        if list_age < 0 or list_age > BLACKLIST_MAX_AGE_DAYS:
            incomplete = True
            continue
        if not evidence_item_ok(item) or not host_matches(
            str(item.get("url") or ""), BLACKLIST_DOMAINS[authority]
        ):
            incomplete = True
            continue
        status = str(item.get("status") or "").strip().lower()
        # A verified official hit is decisive even when another authority's
        # record is missing, malformed, duplicated, or stale.
        if status in {"listed", "blacklisted", "invalid", "revoked"}:
            return False
        if status != "clear" or duplicate:
            incomplete = True
            continue
        by_authority[authority] = item
    if incomplete:
        return None
    return True if set(by_authority) == set(BLACKLIST_DOMAINS) else None


def s6_gate(work: Work, entry: dict[str, Any]) -> bool | None:
    def verified_record(item: Any, domains: tuple[str, ...]) -> bool:
        return (
            isinstance(item, dict)
            and evidence_item_ok({
                "reviewed": item.get("verified"),
                "reviewer_id": item.get("reviewer_id"),
                "reviewed_at": item.get("reviewed_at"),
                "locator": item.get("locator"),
                "url": item.get("url"),
                "note": item.get("note"),
            })
            and host_matches(str(item.get("url") or ""), domains)
        )

    if work.kind in {"journal", "conference"}:
        if work.kind == "journal":
            blacklist_result = blacklist_gate(work, entry)
            if blacklist_result is not True:
                return blacklist_result
        allowed_indexes = (
            {"scopus", "web of science", "wos", "isc", "dblp"}
            if work.kind == "conference" else set(INDEX_DOMAINS)
        )
        valid_indexes = {
            str(item.get("index") or "").strip().lower()
            for item in verified_indexing_items(entry, work)
        }
        return True if valid_indexes & allowed_indexes else None

    if work.kind == "thesis":
        item = entry.get("thesis_repository_evidence")
        if not isinstance(item, dict):
            return None
        repository = str(item.get("repository", item.get("index", ""))).strip().lower()
        if repository == "irandoc":
            return True if verified_record(item, ("irandoc.ac.ir",)) else None
        if repository in {"university repository", "institutional repository"}:
            institution_domain = str(item.get("institution_domain") or "").strip().lower()
            if not institution_domain or "." not in institution_domain:
                return None
            return True if verified_record(item, (institution_domain,)) else None
        return None

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
        citation_evidence = item.get("citation_evidence")
        citation_source = (
            str(citation_evidence.get("source") or "").strip().lower()
            if isinstance(citation_evidence, dict) else ""
        )
        citation_doi = str(
            citation_evidence.get("doi") or ""
            if isinstance(citation_evidence, dict) else ""
        ).strip().lower().removeprefix("https://doi.org/").removeprefix("http://dx.doi.org/")
        work_doi = str(work.doi or "").strip().lower().removeprefix(
            "https://doi.org/"
        ).removeprefix("http://dx.doi.org/")
        citation_isbn = re.sub(
            r"[^0-9X]", "", str(citation_evidence.get("isbn") or "").upper()
        ) if isinstance(citation_evidence, dict) else ""
        work_isbns = {
            re.sub(r"[^0-9X]", "", str(value).upper()) for value in work.isbns
        }
        citation_identity_verified = (
            citation_doi == work_doi if work_doi
            else bool(citation_isbn and citation_isbn in work_isbns)
        )
        citation_count_verified = (
            citation_source == "openalex"
            and citation_identity_verified
            and citation_evidence.get("citation_count") == citation_count
            and isinstance(citation_evidence.get("citation_count"), int)
            and not isinstance(citation_evidence.get("citation_count"), bool)
            and citation_evidence.get("citation_count") >= 0
            and verified_record(citation_evidence, ("api.openalex.org",))
        )
        publisher_verified = item.get("publisher_verified") is True
        if source == "google books":
            domains = ("books.google.com",)
        elif source == "amazon":
            domains = ("amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr",
                       "amazon.ca", "amazon.in", "amazon.co.jp", "amazon.com.au")
        else:
            return None
        return True if (
            citation_count_valid and citation_count_verified and publisher_verified
            and verified_record(item, domains)
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


def tier_verified(
    work: Work, entry: dict[str, Any], steps: dict[str, bool | None]
) -> tuple[bool | None, str | None, str]:
    book_evidence = entry.get("book_s6_evidence")
    if not isinstance(book_evidence, dict):
        book_evidence = {}
    derived_review = entry.get("derived_papers_review")
    derived_status = (
        str(entry.get("derived_papers_status") or "").lower()
        if evidence_item_ok(derived_review) else None
    )
    derived_papers = entry.get("derived_papers")
    if not isinstance(derived_papers, list):
        derived_papers = []
    valid_derived = [
        item for item in derived_papers
        if isinstance(item, dict) and item.get("verified") is True
        and evidence_item_ok(item)
        and host_matches(
            str(item.get("url") or ""),
            ("doi.org", "crossref.org", "scopus.com", "webofscience.com",
             "mjl.clarivate.com", "scimagojr.com", "ieeexplore.ieee.org",
             "dl.acm.org", "link.springer.com", "sciencedirect.com"),
        )
    ]
    if derived_status == "found" and not valid_derived:
        derived_status = None
    university_evidence = entry.get("university_evidence")
    institution_domain = str(entry.get("institution_domain") or "").strip().lower()
    university_domains = (institution_domain,) if institution_domain else ("ac.ir", "edu")
    university_reputable = (
        True if entry.get("university_reputable") is True
        and evidence_item_ok(university_evidence)
        and host_matches(str(university_evidence.get("url") or ""), university_domains)
        else False if entry.get("university_reputable") is False else None
    )
    relevant_chapters_evidence = entry.get("relevant_chapters_evidence")
    book_domains = ("books.google.com", "amazon.com", "amazon.co.uk", "amazon.de", "amazon.ca")
    relevant_chapters = (
        True if entry.get("relevant_chapters") is True
        and evidence_item_ok(relevant_chapters_evidence)
        and host_matches(str(relevant_chapters_evidence.get("url") or ""), book_domains)
        else False if entry.get("relevant_chapters") is False else None
    )
    computed, reason = compute_tier(
        source_kind=work.kind,
        publisher_recognized=publisher_trusted(work.publisher) if work.publisher else None,
        specialized=entry.get("specialized"),
        indexing_evidence=verified_indexing_items(entry, work),
        quartile=entry.get("quartile"),
        quartile_source=entry.get("quartile_source"),
        blacklisted=steps.get("S6") is False,
        indexing_status=entry.get("indexing_status"),
        source_record_verified=steps.get("S6"),
        identifier_verified=steps.get("S7"),
        conference_scope=entry.get("conference_scope"),
        conference_series_established=entry.get("conference_series_established"),
        degree=entry.get("degree"),
        degree_evidence_verified=(
            True if steps.get("S7") is True and evidence_item_ok(entry.get("degree_evidence"))
            else None
        ),
        repository_verified=steps.get("S6") if work.kind == "thesis" else None,
        derived_papers_status=derived_status,
        derived_papers=valid_derived,
        university_reputable=university_reputable,
        main_book=entry.get("main_book"),
        publisher_verified=book_evidence.get("publisher_verified"),
        citation_count=book_evidence.get("citation_count"),
        relevant_chapters=relevant_chapters,
    )
    if computed is None:
        return None, None, reason
    if not tier_evidence_valid(work, entry):
        return None, computed, "Computed tier lacks reviewer-attributed evidence from the relevant official source."
    declared = str(entry.get("tier") or "").strip().upper()
    if not declared:
        return None, computed, "Declared tier is missing; record the reviewer-provided A/B/C/D tier to compare with the computed tier."
    if declared != computed:
        return False, computed, f"Declared tier {declared} does not match computed tier {computed}. {reason}"
    return True, computed, reason


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
    links: list[str] = [
        f"[MSRT journal portal]({MSRT_PORTAL})",
        f"[MOHME journal database]({MOHME_PORTAL})",
        f"[IAU evaluation / revoked-credit status]({IAU_EVALUATION_PORTAL})",
        f"[ImpactFactor secondary report — verify officially]({IMPACTFACTOR})",
    ]
    if key:
        links.extend([
            f"[SCImago]({SCI_MAGO}{key})",
            f"[Clarivate MJL]({CLARIVATE}{key})",
            f"[DOAJ]({DOAJ}{key}%22%7D%7D%7D)",
        ])
    return links


def decide(work: Work, entry: dict[str, Any]) -> dict[str, Any]:
    category = str(entry.get("category", "")).lower()
    tier_declared = str(entry.get("tier", "")).upper()
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
        and host_matches(str(search.get("url", "")), SEARCH_DOMAINS)
        and _valid_search_timestamp(str(search.get("searched_at", "")))
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

    tier_ok, tier_computed, tier_reason = tier_verified(work, entry, steps)

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
            f"blacklist checks={[(item.get('authority'), item.get('status')) for item in entry.get('blacklist_checks', []) if isinstance(item, dict)]}; "
            f"verified index evidence={len(verified_indexing_items(entry, work))}"
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
        notes_en.append("S6 rejected: a verified official MSRT, MOHME or IAU blacklist hit was recorded.")
        notes_fa.append("S6 رد شد: مورد ثبت‌شده در فهرست رسمی وزارت علوم، وزارت بهداشت یا دانشگاه آزاد تأیید شد.")
    elif s6 is None:
        if work.kind == "journal":
            notes_en.append("S6 pending: record current ISSN checks for MSRT, MOHME and IAU, then add a verified Scopus/WoS/ISC/DBLP/DOAJ record. Stale or unavailable lists remain pending.")
            notes_fa.append("S6 در انتظار است: بررسی ISSN در فهرست‌های به‌روز وزارت علوم، وزارت بهداشت و دانشگاه آزاد و سپس مدرک نمایه‌سازی معتبر را ثبت کن؛ فهرست قدیمی یا در دسترس‌نبودن یعنی وضعیت معلق.")
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
    if tier_ok is None:
        notes_en.append(f"S9 pending: {tier_reason}")
        notes_fa.append(f"S9 در انتظار است: {tier_reason}")
    elif tier_ok is False:
        notes_en.append(f"S9 rejected: declared tier {tier_declared or 'missing'} does not match computed tier {tier_computed}.")
        notes_fa.append(f"S9 رد شد: رتبه اعلام‌شده {tier_declared or 'ثبت‌نشده'} با رتبه محاسبه‌شده {tier_computed} منطبق نیست.")
    for key in ("S1", "S2", "S10"):
        if steps[key] is None:
            notes_en.append(f"{key} pending: add a documented research judgement.")
            notes_fa.append(f"{key} در انتظار است: قضاوت پژوهشی مستند ثبت کن.")
    integrity = {
        "status": integrity_status(work),
        "openalex_is_retracted": work.is_retracted,
        "openalex_is_paratext": work.is_paratext,
        "crossref_updates": work.updates,
    }
    if integrity["status"] == "retracted":
        notes_en.append("RETRACTION FLAG: this work is marked retracted by OpenAlex or Crossref update metadata.")
        notes_fa.append("هشدار پس‌گرفتن: این اثر در داده‌های OpenAlex یا Crossref پس‌گرفته‌شده علامت‌گذاری شده است.")
    elif integrity["status"] == "corrected":
        notes_en.append("CORRECTION FLAG: inspect the correction/erratum notice before citing this version.")
        notes_fa.append("هشدار اصلاحیه: پیش از استناد، اطلاعیه اصلاح/اراطا را بررسی کن.")
    elif integrity["status"] == "partial":
        notes_en.append("Retraction status is incomplete: OpenAlex did not provide an is_retracted value.")
        notes_fa.append("وضعیت پس‌گرفتن کامل نیست: OpenAlex مقدار is_retracted ارائه نکرد.")
    elif integrity["status"] == "paratext":
        notes_en.append("OpenAlex classifies this work as paratext; confirm that it is eligible for the review.")
        notes_fa.append("OpenAlex این اثر را paratext طبقه‌بندی کرده؛ واجد شرایط بودن آن برای مرور را بررسی کن.")
    else:
        notes_en.append("No retraction flag recorded by OpenAlex/Crossref; this is not proof that no notice exists.")
        notes_fa.append("در OpenAlex/Crossref نشانه پس‌گرفتن ثبت نشده؛ این اثبات نبود اطلاعیه نیست.")
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
        "tier": tier_computed if tier_ok is not None else "",
        "tier_declared": tier_declared,
        "tier_computed": tier_computed,
        "tier_reason": tier_reason,
        "tier_verified": tier_ok,
        "integrity_status": integrity["status"],
        "integrity": integrity,
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
    rows.append("For each journal, record three independent blacklist_checks: authority=msrt, "
                "authority=mohme and authority=iau. Each check must include status=clear/listed, ISSN query, "
                "list_version, reviewer_id, reviewed_at, URL, locator and note. Any verified listed "
                "result hard-rejects S6. Missing or inaccessible lists remain pending. For a positive "
                "index result, add indexing_evidence with index, verified=true, source URL, note, "
                "matched_title equal to the Crossref title, and integer coverage_start_year / "
                "coverage_end_year containing the publication year. Conference evidence must use "
                "Scopus, Web of Science/WoS, ISC or DBLP (not DOAJ). Then rerun verify_source.py.")
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



