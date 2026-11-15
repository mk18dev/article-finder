#!/usr/bin/env python3
"""Download the open full text for the sources in a results or plan file.

Usage:
    python3 fetch_pdf.py results.json [--out pdfs] [--report pdf-report.md] [--dry-run]

For every source the script asks three open-access indexes in order — OpenAlex,
Unpaywall and Semantic Scholar — and takes the first candidate that really is a
PDF: the best OA location, any location with a pdf_url, the OA landing URL when
it ends in .pdf, and the arXiv id when a record carries one.

It never touches Sci-Hub, LibGen or Z-Lib (references/validation.md §8). A
source with no open copy is reported with the legitimate route to take instead,
so the agent hands the user a list instead of a wall.

The PDF check is deliberate: publishers return HTML error pages with HTTP 200,
and a 200 answer is not a download. A file is accepted only when it starts with
%PDF-, is at least MIN_PDF_BYTES long, and stays under http_util.MAX_BYTES.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from http_util import MAILTO, fetch_bytes, fetch_json

ATOM = {"a": "http://www.w3.org/2005/Atom"}
IRANDOC_SEARCH = "https://ganj.irandoc.ac.ir/#/search?query="

MIN_PDF_BYTES = 20_000
ROUTES = (
    "publisher page (IEEE Xplore / SpringerLink / ScienceDirect)",
    "Google Scholar PDF and all-versions links",
    "author page or preprint server",
    "institutional or library access",
    "email the corresponding author",
)


@dataclass
class Source:
    title: str
    doi: str
    year: int | None = None
    category: str = ""
    tier: str = ""


@dataclass
class Result:
    source: Source
    status: str
    detail: str = ""
    path: str = ""
    routes: list[str] = field(default_factory=list)


def load_sources(path: Path) -> list[Source]:
    return load_sources_text(path.read_text(encoding="utf-8"))


def load_sources_text(text: str) -> list[Source]:
    payload = json.loads(text)
    entries = payload["articles"] if isinstance(payload, dict) else payload
    sources: list[Source] = []
    for entry in entries:
        doi = str(entry.get("doi") or "").strip()
        if not doi and entry.get("url", "").startswith("https://doi.org/"):
            doi = str(entry["url"]).split("doi.org/", 1)[1]
        sources.append(Source(
            title=str(entry.get("title", "(untitled)")),
            doi=doi.lower(),
            year=entry.get("year"),
            category=str(entry.get("category", "")),
            tier=str(entry.get("tier", "")),
        ))
    return sources


def arxiv_url(record: dict[str, Any]) -> str | None:
    identifier = str((record.get("ids") or {}).get("arxiv") or "")
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", identifier)
    return f"https://arxiv.org/pdf/{match.group(1)}" if match else None


def candidates(record: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def add(url: object) -> None:
        text = str(url or "").strip()
        if text and text not in urls:
            urls.append(text)

    best = record.get("best_oa_location") or {}
    add(best.get("pdf_url"))
    for location in record.get("locations") or []:
        add((location or {}).get("pdf_url"))
        landing = str((location or {}).get("landing_page_url") or "")
        if landing.lower().endswith(".pdf"):
            add(landing)
    add((record.get("open_access") or {}).get("oa_url"))
    add(arxiv_url(record))
    return [url for url in urls if url.lower().startswith("http")]


def unique(urls: list[str]) -> list[str]:
    ordered: list[str] = []
    for url in urls:
        if url.startswith("http") and url not in ordered:
            ordered.append(url)
    return ordered


def unpaywall_candidates(doi: str) -> list[str]:
    record = fetch_json(f"https://api.unpaywall.org/v2/{doi}?email={MAILTO}")
    urls: list[str] = []
    best = record.get("best_oa_location") or {}
    for key in ("url_for_pdf", "url"):
        value = str(best.get(key) or "")
        if value.startswith("http") and value not in urls:
            urls.append(value)
    for location in record.get("oa_locations") or []:
        value = str((location or {}).get("url_for_pdf") or "")
        if value.startswith("http") and value not in urls:
            urls.append(value)
    return unique(urls)


def semantic_scholar_candidates(doi: str) -> list[str]:
    record = fetch_json("https://api.semanticscholar.org/graph/v1/paper/DOI:"
                        f"{doi}?fields=openAccessPdf,externalIds")
    urls: list[str] = []
    pdf = str((record.get("openAccessPdf") or {}).get("url") or "")
    if pdf.startswith("http"):
        urls.append(pdf)
    arxiv = str((record.get("externalIds") or {}).get("ArXiv") or "")
    if arxiv:
        urls.append(f"https://arxiv.org/pdf/{arxiv}")
    return unique(urls)


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def title_matches(query: str, candidate: str) -> bool:
    wanted = set(normalize_title(query).split())
    found = set(normalize_title(candidate).split())
    if not wanted or not found:
        return False
    return len(wanted & found) / len(wanted) >= 0.8


def arxiv_title_candidates(title: str) -> list[str]:
    query = urllib.parse.quote(f'ti:"{title}"')
    payload = fetch_bytes(f"http://export.arxiv.org/api/query?search_query={query}&max_results=5")
    root = ET.fromstring(payload)
    urls: list[str] = []
    for entry in root.findall("a:entry", ATOM):
        found = (entry.findtext("a:title", default="", namespaces=ATOM) or "").strip()
        identifier = entry.findtext("a:id", default="", namespaces=ATOM) or ""
        match = re.search(r"abs/([^v]+)", identifier)
        if match and title_matches(title, found):
            urls.append(f"https://arxiv.org/pdf/{match.group(1)}")
    return unique(urls)


def core_candidates(doi: str) -> list[str]:
    key = os.environ.get("CORE_API_KEY", "").strip()
    if not key:
        return []
    query = urllib.parse.quote(f'doi:"{doi}"')
    record = fetch_json(f"https://api.core.ac.uk/v3/search/works?q={query}&limit=1",
                        headers={"Authorization": f"Bearer {key}"})
    urls: list[str] = []
    for item in record.get("results") or []:
        for key_name in ("downloadUrl", "fullTextIdentifier"):
            value = str((item or {}).get(key_name) or "")
            if value.startswith("http"):
                urls.append(value)
    return unique(urls)


def irandoc_route(title: str) -> str:
    return IRANDOC_SEARCH + urllib.parse.quote(title)


def external_candidates(doi: str, title: str) -> list[str]:
    urls: list[str] = []
    providers = (
        lambda: unpaywall_candidates(doi),
        lambda: semantic_scholar_candidates(doi),
        lambda: core_candidates(doi),
        lambda: arxiv_title_candidates(title),
    )
    for provider in providers:
        try:
            for url in provider():
                if url not in urls:
                    urls.append(url)
        except Exception:
            continue
    return urls


PDF_LINK = re.compile(rb'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
MAX_HTML_BYTES = 400_000


def pdf_links(payload: bytes, base: str) -> list[str]:
    if len(payload) > MAX_HTML_BYTES or b"<html" not in payload[:4096].lower():
        return []
    links: list[str] = []
    for raw in PDF_LINK.findall(payload):
        url = urllib.parse.urljoin(base, raw.decode("utf-8", "ignore"))
        if url.startswith("http") and url not in links:
            links.append(url)
    return links[:3]


def looks_like_pdf(payload: bytes) -> bool:
    return payload.startswith(b"%PDF-") and len(payload) >= MIN_PDF_BYTES


def slug(index: int, title: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{index:02d}-{(lowered[:60] or 'source').strip('-')}"


def download_one(index: int, source: Source, out: Path, dry_run: bool) -> Result:
    if not source.doi:
        return Result(source, "no-doi", "no DOI in the record; add it before downloading", routes=list(ROUTES))
    try:
        record = fetch_json(f"https://api.openalex.org/works/doi:{source.doi}")
    except Exception as exc:
        return Result(source, "lookup-failed", f"{type(exc).__name__}: {exc}"[:120], routes=list(ROUTES))

    urls = candidates(record)
    for url in external_candidates(source.doi, source.title):
        if url not in urls:
            urls.append(url)
    if not urls:
        routes = list(ROUTES) + [f"Persian thesis bank (Irandoc): {irandoc_route(source.title)}"]
        return Result(source, "paywalled", "no open-access copy registered", routes=routes)
    if dry_run:
        return Result(source, "candidate", " · ".join(urls[:3]))

    failures: list[str] = []
    for url in urls:
        try:
            payload = fetch_bytes(url)
        except Exception as exc:
            failures.append(f"{type(exc).__name__} @ {url[:60]}")
            continue
        if looks_like_pdf(payload):
            return save(index, source, out, payload, url)
        nested = pdf_links(payload, url)
        for link in nested:
            try:
                inner = fetch_bytes(link)
            except Exception:
                continue
            if looks_like_pdf(inner):
                return save(index, source, out, inner, f"{link} (via {url[:40]})")
        failures.append(f"no PDF @ {url[:60]}" + (f" ({len(nested)} link(s) inside)" if nested else ""))
    detail = f"{len(urls)} candidate(s) tried; " + (failures[-1] if failures else "no response")
    return Result(source, "no-pdf", detail, routes=list(ROUTES))


def save(index: int, source: Source, out: Path, payload: bytes, origin: str) -> Result:
    target = out / f"{slug(index, source.title)}.pdf"
    target.write_bytes(payload)
    return Result(source, "downloaded", f"{len(payload) // 1024} KB from {origin}", path=str(target))


def crossref_contact(doi: str) -> tuple[str, str]:
    if not doi:
        return "", ""
    try:
        message = fetch_json(f"https://api.crossref.org/works/{doi}")["message"]
    except Exception:
        return "", ""
    authors = message.get("author") or []
    family = next((str(a.get("family") or "") for a in authors if a.get("family")), "")
    venue = str((message.get("container-title") or [""])[0])
    return family, venue


EMAIL = """Subject: Request for the full text of "{title}" (DOI {doi})

Dear {salutation},

I am compiling a literature review on hybrid recommender systems and the
cold-start problem, and your paper "{title}" ({venue}, {year}) is directly
relevant to it. The copy I can reach is behind a paywall.

Would you be willing to share the published PDF, or the accepted manuscript?
I will cite the published version either way.

Kind regards,
"""


def email_drafts(results: list[Result],
                 contact: Callable[[str], tuple[str, str]] = crossref_contact) -> str:
    blocks = ["# Author email drafts", "",
              "One draft per source with no open copy. The agent fills the sender block and sends; "
              "nothing is sent automatically.", ""]
    for result in results:
        if result.status == "downloaded":
            continue
        family, venue = contact(result.source.doi)
        salutation = f"Dr. {family}" if family else "Dr."
        blocks.append(f"## {result.source.title}")
        blocks.append("")
        blocks.append("```")
        blocks.append(EMAIL.format(title=result.source.title, doi=result.source.doi or "(none)",
                                   salutation=salutation, venue=venue or "(venue)",
                                   year=result.source.year or "(year)").rstrip())
        blocks.append("")
        blocks.append("[sender name, affiliation, email]")
        blocks.append("```")
        blocks.append("")
    return "\n".join(blocks)


def report(results: list[Result], out: Path) -> str:
    lines = ["# Full-text fetch report", "",
             f"PDFs written to `{out}`. Paywalled rows list the legitimate routes; "
             "Sci-Hub, LibGen and Z-Lib are never used (`references/validation.md` §8).", "",
             "| # | Source | Year | Status | Detail |", "|---|---|---|---|---|"]
    for index, result in enumerate(results, 1):
        detail = result.detail or " · ".join(result.routes)
        detail = detail.replace("|", "\\|")
        lines.append(f"| {index} | {result.source.title} | {result.source.year or '-'} | "
                     f"{result.status} | {detail} |")
    downloaded = sum(1 for r in results if r.status == "downloaded")
    lines.append("")
    lines.append(f"**{downloaded}/{len(results)} downloaded · "
                 f"{sum(1 for r in results if r.status in {'paywalled', 'no-pdf'})} need a licensed route**")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the open full text for verified sources.")
    parser.add_argument("input", help="results.json or an earlier plan.json")
    parser.add_argument("--out", default="pdfs", help="directory for the PDFs")
    parser.add_argument("--report", help="write the markdown report here")
    parser.add_argument("--dry-run", action="store_true", help="print candidate URLs, download nothing")
    parser.add_argument("--draft-emails", help="write ready-to-send author request emails for the misses")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between sources, so the open-access indexes do not rate-limit")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sources = load_sources(Path(args.input))
    results: list[Result] = []
    for index, source in enumerate(sources, 1):
        if index > 1 and not args.dry_run and args.delay > 0:
            time.sleep(args.delay)
        results.append(download_one(index, source, out, args.dry_run))
    for index, result in enumerate(results, 1):
        print(f"{index:02d} {result.status:<13} {result.source.title[:56]}")

    if args.draft_emails:
        Path(args.draft_emails).write_text(email_drafts(results), encoding="utf-8")
        print(f"\nwrote {args.draft_emails}")

    text = report(results, out)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
        print(f"\nwrote {args.report}")
    print(f"\n{sum(1 for r in results if r.status == 'downloaded')}/{len(results)} downloaded into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




