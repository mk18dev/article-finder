#!/usr/bin/env python3
"""Reproducible multi-database scholarly search (Crossref + OpenAlex)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from http_util import fetch_json  # noqa: E402
from prisma_review import deduplicate_records  # noqa: E402

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _doi(value: Any) -> str:
    raw = str(value or "").strip()
    raw = raw.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return raw.casefold().rstrip(" .")


def _year(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def search_crossref(query: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "query": query,
        "rows": str(limit),
        "select": "DOI,title,author,published-print,published-online,issued,type,publisher,container-title,URL",
    }
    mailto = os.environ.get("ARTICLE_FINDER_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    payload = fetch_json(url)
    message = payload.get("message") or {}
    items = message.get("items") or []
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        titles = item.get("title") or []
        authors = item.get("author") or []
        parts = (item.get("published-print") or item.get("published-online")
                 or item.get("issued") or {}).get("date-parts") or []
        records.append({
            "doi": _doi(item.get("DOI")),
            "title": str(titles[0]) if titles else "",
            "authors": [
                " ".join(part for part in (str(author.get("given") or "").strip(),
                                           str(author.get("family") or "").strip()) if part)
                for author in authors if isinstance(author, dict)
            ],
            "year": _year(parts[0][0]) if parts and parts[0] else None,
            "publisher": str(item.get("publisher") or ""),
            "venue": str((item.get("container-title") or [""])[0]),
            "type": str(item.get("type") or ""),
            "url": str(item.get("URL") or ""),
            "source_provider": "Crossref",
        })
    log = {
        "database": "Crossref",
        "platform": "Crossref REST API",
        "query": query,
        "date_run": date.today().isoformat(),
        "searched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hits": len(records),
        "total_available": int(message.get("total-results") or len(records)),
        "limits": f"rows={limit}",
        "search_url": url,
        "status": "ok",
    }
    return records, log


def search_openalex(query: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {"search": query, "per-page": str(limit)}
    mailto = os.environ.get("ARTICLE_FINDER_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    payload = fetch_json(url)
    items = payload.get("results") or []
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        authorships = item.get("authorships") or []
        authors = []
        for authorship in authorships:
            author = (authorship or {}).get("author") or {}
            name = str(author.get("display_name") or "").strip()
            if name:
                authors.append(name)
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        records.append({
            "doi": _doi(item.get("doi")),
            "title": str(item.get("title") or ""),
            "authors": authors,
            "year": _year(item.get("publication_year")),
            "publisher": str(source.get("host_organization_name") or ""),
            "venue": str(source.get("display_name") or ""),
            "type": str(item.get("type") or ""),
            "url": str(item.get("id") or ""),
            "source_provider": "OpenAlex",
            "is_retracted": item.get("is_retracted"),
        })
    log = {
        "database": "OpenAlex",
        "platform": "OpenAlex Works API",
        "query": query,
        "date_run": date.today().isoformat(),
        "searched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hits": len(records),
        "total_available": int((payload.get("meta") or {}).get("count") or len(records)),
        "limits": f"per-page={limit}",
        "search_url": url,
        "status": "ok",
    }
    return records, log


def discover(query: str, limit: int = DEFAULT_LIMIT,
             providers: tuple[str, ...] = ("crossref", "openalex")) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    allowed = {"crossref", "openalex"}
    if not providers or any(provider not in allowed for provider in providers):
        raise ValueError("providers must contain crossref and/or openalex")
    records: list[dict[str, Any]] = []
    search_log: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    functions = {"crossref": search_crossref, "openalex": search_openalex}
    for provider in providers:
        try:
            found, log = functions[provider](query.strip(), limit)
            records.extend(found)
            search_log.append(log)
        except Exception as exc:
            errors.append({"provider": provider, "error": type(exc).__name__})
            search_log.append({
                "database": provider.title(),
                "platform": provider.title() + " API",
                "query": query.strip(),
                "date_run": date.today().isoformat(),
                "hits": 0,
                "limits": f"limit={limit}",
                "status": "error",
                "error": type(exc).__name__,
            })
    for index, record in enumerate(records, 1):
        record.setdefault(
            "record_id",
            f"{str(record.get('source_provider') or 'source').lower()}-{index:06d}",
        )
    for index, record in enumerate(records, 1):
        provider = str(record.get("source_provider") or "source").strip().lower()
        record.setdefault("record_id", f"{provider}-{index:06d}")
    unique, duplicates = deduplicate_records(records)
    return {
        "query": query.strip(),
        "raw_records": records,
        "records": unique,
        "duplicates": duplicates,
        "search_log": search_log,
        "errors": errors,
        "providers_succeeded": [item["database"] for item in search_log if item["status"] == "ok"],
        "disclaimer": "Search results are candidates, not verified or approved sources. Preserve failed-provider records and rerun failed searches before claiming systematic coverage.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Crossref and OpenAlex with a reproducible query log.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--providers", default="crossref,openalex")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    try:
        providers = tuple(item.strip().lower() for item in args.providers.split(",") if item.strip())
        result = discover(args.query, args.limit, providers)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0 if result["providers_succeeded"] and not result["errors"] else 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
