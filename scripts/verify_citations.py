#!/usr/bin/env python3
"""Verify citation identity against Crossref metadata and flag recorded updates.

A successful metadata match verifies bibliographic identity only. It does not
prove that a cited claim is supported by the paper or that no unregistered
correction/retraction exists.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from http_util import fetch_json  # noqa: E402

TITLE_MATCH_THRESHOLD = 0.92


DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[^\s]+$", re.I)


def normalize_doi(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith(("https://doi.org/", "https://dx.doi.org/")):
        try:
            parsed = urllib.parse.urlsplit(raw)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("malformed DOI URL") from exc
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() not in {"doi.org", "dx.doi.org"}
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("DOI URL must use the official HTTPS resolver without extra components")
        raw = urllib.parse.unquote(parsed.path.lstrip("/"))
    elif raw.lower().startswith(("http://", "https://")):
        raise ValueError("only doi.org HTTPS URLs are accepted")
    raw = re.sub(r"^doi:\s*", "", raw, flags=re.I)
    raw = urllib.parse.unquote(raw).strip().rstrip(" .").casefold()
    if not DOI_PATTERN.fullmatch(raw):
        raise ValueError("invalid DOI format")
    return raw

def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": ""}))
    text = text.replace("\u200c", "").replace("\u200f", "").replace("\u200e", "")
    return " ".join(re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE))



def title_similarity(expected: str, actual: str) -> float:
    left, right = normalize_text(expected), normalize_text(actual)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def first_author_family(authors: Any) -> str:
    if not isinstance(authors, list) or not authors or not isinstance(authors[0], dict):
        return ""
    return normalize_text(authors[0].get("family") or authors[0].get("name") or "")


def publication_year(message: dict[str, Any]) -> int | None:
    for field in ("published-print", "published-online", "issued", "created"):
        parts = (message.get(field) or {}).get("date-parts") or []
        if parts and parts[0] and isinstance(parts[0][0], int):
            return parts[0][0]
    return None


def update_status(message: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    updates: list[dict[str, str]] = []
    raw = message.get("update-to") or []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "update").strip().lower().replace("-", "_")
            updates.append({
                "type": kind,
                "doi": normalize_doi(item.get("DOI")),
                "label": str(item.get("label") or ""),
                "url": ("https://doi.org/" + normalize_doi(item.get("DOI"))) if item.get("DOI") else "",
            })
    relation = message.get("relation") or {}
    if isinstance(relation, dict):
        for kind, values in relation.items():
            relation_kind = str(kind).lower().replace("-", "_")
            for item in values if isinstance(values, list) else []:
                if not isinstance(item, dict):
                    continue
                target_type = str(item.get("type") or "").lower().replace("-", "_")
                update_type = relation_kind + " " + target_type
                if any(term in update_type for term in ("retract", "correct", "errat", "withdraw", "expression_of_concern")):
                    updates.append({
                        "type": update_type.strip(),
                        "doi": normalize_doi(item.get("id")),
                        "label": str(item.get("asserted-by") or ""),
                        "url": ("https://doi.org/" + normalize_doi(item.get("id"))) if item.get("id") else "",
                    })
    retraction_terms = ("retract", "withdraw", "expression_of_concern")
    correction_terms = ("correct", "errat", "corrigendum")
    if any(any(term in item["type"] for term in retraction_terms) for item in updates):
        return "retracted", updates
    if any(any(term in item["type"] for term in correction_terms) for item in updates):
        return "corrected", updates
    return "no_update_recorded", updates

def verify_metadata(citation: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    expected_doi = normalize_doi(citation.get("doi"))
    actual_doi = normalize_doi(message.get("DOI"))
    titles = message.get("title") or []
    actual_title = str(titles[0]) if titles else ""
    expected_title = str(citation.get("title") or "")
    similarity = title_similarity(expected_title, actual_title)
    actual_year = publication_year(message)
    expected_year_raw = citation.get("year")
    expected_year_text = str(expected_year_raw or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    expected_year_match = re.fullmatch(r"\d{4}", expected_year_text)
    expected_year = int(expected_year_match.group(0)) if expected_year_match else None
    actual_author = first_author_family(message.get("author"))
    containers = message.get("container-title") or []
    actual_venue = str(containers[0]) if containers else ""
    actual_publisher = str(message.get("publisher") or "")
    expected_venue = str(citation.get("venue") or citation.get("journal") or citation.get("container_title") or "").strip()
    expected_publisher = str(citation.get("publisher") or "").strip()
    expected_author_raw = str(citation.get("first_author") or "").strip()
    expected_author_raw = re.split(r"[,،]", expected_author_raw, maxsplit=1)[0]
    expected_author = normalize_text(expected_author_raw)
    status_update, updates = update_status(message)

    mismatches: list[str] = []
    if expected_doi and actual_doi and expected_doi != actual_doi:
        mismatches.append("DOI returned by Crossref does not match the supplied DOI")
    if expected_title and similarity < TITLE_MATCH_THRESHOLD:
        mismatches.append(f"title similarity {similarity:.3f} is below {TITLE_MATCH_THRESHOLD:.2f}")
    if expected_year is not None and actual_year is not None and int(expected_year) != actual_year:
        mismatches.append(f"publication year mismatch: expected {expected_year}, Crossref reports {actual_year}")
    if expected_author and actual_author and not (expected_author == actual_author or expected_author.endswith(" " + actual_author) or expected_author.startswith(actual_author + " ")):
        mismatches.append("first-author family name mismatch")
    venue_similarity = title_similarity(expected_venue, actual_venue) if expected_venue and actual_venue else 0.0
    publisher_similarity = title_similarity(expected_publisher, actual_publisher) if expected_publisher and actual_publisher else 0.0
    if expected_venue and actual_venue and venue_similarity < 0.85:
        mismatches.append(f"venue mismatch: expected {expected_venue!r}, Crossref reports {actual_venue!r}")
    if expected_publisher and actual_publisher and publisher_similarity < 0.90:
        mismatches.append(f"publisher mismatch: expected {expected_publisher!r}, Crossref reports {actual_publisher!r}")

    if status_update == "retracted":
        status = "retracted"
    elif status_update == "corrected":
        status = "corrected"
    elif mismatches:
        status = "mismatch"
    elif (
        not expected_doi or not actual_doi or not expected_title or not actual_title
        or expected_year is None or actual_year is None or not expected_author or not actual_author
        or (expected_venue and not actual_venue)
        or (expected_publisher and not actual_publisher)
    ):
        status = "pending"
    else:
        status = "verified"

    return {
        "status": status,
        "doi": actual_doi or expected_doi,
        "title": actual_title,
        "year": actual_year,
        "first_author": actual_author,
        "venue": actual_venue,
        "publisher": actual_publisher,
        "venue_similarity": round(venue_similarity, 4),
        "publisher_similarity": round(publisher_similarity, 4),
        "title_similarity": round(similarity, 4),
        "updates": updates,
        "mismatches": mismatches,
        "limitations": [
            "Metadata agreement verifies citation identity, not whether the cited paper supports the manuscript claim.",
            "No update recorded is not proof that no correction or retraction exists outside Crossref metadata.",
        ],
    }


def verify_citation(citation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(citation, dict):
        raise ValueError("each citation must be an object")
    if len(str(citation.get("title") or "")) > 1000 or len(str(citation.get("first_author") or "")) > 200:
        raise ValueError("citation title or first_author exceeds its input limit")
    doi = normalize_doi(citation.get("doi"))
    if doi:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
        payload = fetch_json(url)
        message = payload.get("message")
        if not isinstance(message, dict):
            return {"status": "pending", "doi": doi, "reason": "Crossref returned no metadata record"}
        return verify_metadata(citation, message)

    title = str(citation.get("title") or "").strip()
    author = str(citation.get("first_author") or "").strip()
    if not title:
        return {"status": "pending", "reason": "citation has neither a DOI nor a title"}
    query = " ".join(part for part in (title, author) if part)
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": 5})
    payload = fetch_json("https://api.crossref.org/works?" + params)
    items = (payload.get("message") or {}).get("items") or []
    candidates = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        titles = item.get("title") or []
        candidate_title = str(titles[0]) if titles else ""
        candidates.append({
            "doi": normalize_doi(item.get("DOI")),
            "title": candidate_title,
            "title_similarity": round(title_similarity(title, candidate_title), 4),
        })
    candidates.sort(key=lambda item: item["title_similarity"], reverse=True)
    return {
        "status": "pending",
        "reason": "no DOI supplied; Crossref matches are candidates and require human confirmation",
        "candidates": candidates,
    }


def verify_all(document: Any) -> list[dict[str, Any]]:
    citations = document.get("citations") if isinstance(document, dict) else document
    if not isinstance(citations, list):
        raise ValueError("input must be a list or an object with a citations list")
    if not 1 <= len(citations) <= 100:
        raise ValueError("citations must contain between 1 and 100 records")
    doi_counts: dict[str, int] = {}
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        try:
            normalized = normalize_doi(citation.get("doi"))
        except ValueError:
            normalized = ""
        if normalized:
            doi_counts[normalized] = doi_counts.get(normalized, 0) + 1

    results = []
    for index, citation in enumerate(citations, 1):
        try:
            result = verify_citation(citation)
        except Exception as exc:  # preserve per-citation failures without approving them
            try:
                failed_doi = normalize_doi(citation.get("doi")) if isinstance(citation, dict) else ""
            except ValueError:
                failed_doi = ""
            result = {
                "status": "pending",
                "doi": failed_doi,
                "reason": f"metadata lookup failed: {type(exc).__name__}",
            }
        result["index"] = index
        result["input"] = citation
        try:
            normalized_doi = normalize_doi(citation.get("doi")) if isinstance(citation, dict) else ""
        except ValueError:
            normalized_doi = ""
        if normalized_doi and doi_counts.get(normalized_doi, 0) > 1:
            result["duplicate_doi"] = True
            result.setdefault("mismatches", []).append("duplicate DOI appears more than once in the submitted bibliography")
            if result.get("status") not in {"retracted", "corrected"}:
                result["status"] = "mismatch"
        else:
            result["duplicate_doi"] = False
        results.append(result)
    return results


def render_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Citation verification report",
        "",
        "| # | Status | DOI | Title | Year | Notes |",
        "|---:|---|---|---|---:|---|",
    ]
    for item in results:
        def safe(value):
            return str(value or "").replace("|", "\\|").replace("\n", " ")
        citation = item.get("input") or {}
        notes = "; ".join(item.get("mismatches") or []) or item.get("reason", "")
        lines.append("| " + " | ".join((
            str(item.get("index", "")), safe(item.get("status")),
            safe(item.get("doi")), safe(item.get("title") or citation.get("title")),
            safe(item.get("year") or citation.get("year")), safe(notes),
        )) + " |")
    lines.extend([
        "",
        "A verified result means Crossref metadata matched the supplied citation fields.",
        "It does not establish claim support or prove the absence of updates outside Crossref.",
        "Pending and corrected items require human review; retracted items must not support claims.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check citation identity and Crossref update metadata.")
    parser.add_argument("input", help="JSON list or {citations: [...]} file")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    try:
        document = json.loads(Path(args.input).read_text(encoding="utf-8"))
        results = verify_all(document)
        output = (json.dumps(results, ensure_ascii=False, indent=2)
                  if args.format == "json" else render_markdown(results))
        if args.output:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
