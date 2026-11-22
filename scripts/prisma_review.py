#!/usr/bin/env python3
"""Reproducible systematic/scoping-review ledger and PRISMA count validator.

This module validates user-recorded protocol/search/screening data. It never
invent counts, eligibility decisions, or a second reviewer's judgement.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

REVIEW_TYPES = {"systematic", "scoping", "narrative"}
DECISIONS = {"include", "exclude", "pending"}
REQUIRED_COUNTS = (
    "duplicates_removed",
    "records_removed_automation",
    "records_excluded_title_abstract",
    "reports_not_retrieved",
)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_doi(value: Any) -> str:
    raw = str(value or "").strip()
    raw = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw, flags=re.I)
    raw = re.sub(r"^doi:\s*", "", raw, flags=re.I)
    return raw.strip().rstrip(" .").casefold()


def normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def record_key(record: dict[str, Any]) -> tuple[str, str]:
    doi = normalize_doi(record.get("doi"))
    if doi:
        return ("doi", doi)
    pmid = str(record.get("pmid") or "").strip()
    if pmid:
        return ("pmid", pmid.casefold())
    url = str(record.get("url") or "").strip().rstrip("/").casefold()
    if url:
        return ("url", url)
    title = normalize_title(record.get("title"))
    if title:
        return ("title", title)
    return ("record", str(record.get("record_id") or id(record)))


def deduplicate_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep the first occurrence; return explicit duplicate-to-canonical links."""
    seen: dict[tuple[str, str], str] = {}
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for index, raw in enumerate(records, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"record {index} must be an object")
        item = dict(raw)
        key = record_key(item)
        canonical_id = seen.get(key)
        if canonical_id is None:
            canonical_id = str(item.get("record_id") or f"record-{index}")
            seen[key] = canonical_id
            item.setdefault("record_id", canonical_id)
            unique.append(item)
        else:
            duplicates.append({
                "record_id": str(item.get("record_id") or f"record-{index}"),
                "duplicate_of": canonical_id,
                "key_type": key[0],
                "key": key[1],
            })
    return unique, duplicates


def validate_protocol(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    protocol = review.get("protocol")
    if not isinstance(protocol, dict):
        return ["protocol must be an object"]
    kind = str(protocol.get("review_type") or "").strip().lower()
    if kind not in REVIEW_TYPES:
        errors.append("protocol.review_type must be systematic, scoping, or narrative")
    if not _nonempty(protocol.get("question")):
        errors.append("protocol.question is required")
    if kind in {"systematic", "scoping"}:
        for field in ("inclusion_criteria", "exclusion_criteria"):
            values = protocol.get(field)
            if not isinstance(values, list) or not values or not all(_nonempty(v) for v in values):
                errors.append(f"protocol.{field} must contain documented criteria")
    registration = protocol.get("registration")
    if registration is not None and not isinstance(registration, dict):
        errors.append("protocol.registration must be an object when supplied")
    if isinstance(registration, dict):
        if not _nonempty(registration.get("registry")) or not _nonempty(registration.get("id")):
            errors.append("protocol.registration requires registry and id")
    searches = review.get("search_log")
    if not isinstance(searches, list) or not searches:
        errors.append("search_log must contain at least one database search")
        return errors
    for index, item in enumerate(searches, 1):
        prefix = f"search_log[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("database", "platform", "query", "date_run"):
            if not _nonempty(item.get(field)):
                errors.append(f"{prefix}.{field} is required")
        try:
            date.fromisoformat(str(item.get("date_run", "")))
        except ValueError:
            errors.append(f"{prefix}.date_run must be YYYY-MM-DD")
        hits = item.get("hits")
        if isinstance(hits, bool) or not isinstance(hits, int) or hits < 0:
            errors.append(f"{prefix}.hits must be a non-negative integer")
        if not isinstance(item.get("limits", ""), str):
            errors.append(f"{prefix}.limits must be text")
    return errors


def derive_counts(review: dict[str, Any]) -> dict[str, int]:
    searches = review.get("search_log") or []
    counts = review.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("counts must be an object")
    for field in REQUIRED_COUNTS:
        value = counts.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"counts.{field} must be a non-negative integer")
    identified = sum(item["hits"] for item in searches)
    screened = identified - counts["duplicates_removed"] - counts["records_removed_automation"]
    sought = screened - counts["records_excluded_title_abstract"]
    assessed = sought - counts["reports_not_retrieved"]
    full_text_excluded_by_reason = counts.get("full_text_exclusions")
    if not isinstance(full_text_excluded_by_reason, dict):
        raise ValueError("counts.full_text_exclusions must be an object mapping reasons to counts")
    if not full_text_excluded_by_reason:
        full_text_excluded = 0
    else:
        full_text_excluded = 0
        for reason, value in full_text_excluded_by_reason.items():
            if not _nonempty(reason) or isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("full_text_exclusions requires non-empty reasons and non-negative integer counts")
            full_text_excluded += value
    included = assessed - full_text_excluded
    derived = {
        "records_identified": identified,
        "duplicates_removed": counts["duplicates_removed"],
        "records_removed_automation": counts["records_removed_automation"],
        "records_screened": screened,
        "records_excluded_title_abstract": counts["records_excluded_title_abstract"],
        "reports_sought": sought,
        "reports_not_retrieved": counts["reports_not_retrieved"],
        "reports_assessed": assessed,
        "reports_excluded_full_text": full_text_excluded,
        "studies_included": included,
    }
    if any(value < 0 for value in derived.values()):
        raise ValueError("PRISMA counts are inconsistent: a downstream count became negative")
    return derived


def validate_counts(review: dict[str, Any]) -> list[str]:
    try:
        counts = derive_counts(review)
    except (KeyError, TypeError, ValueError) as exc:
        return [str(exc)]
    supplied = review.get("counts") or {}
    errors: list[str] = []
    for key, value in counts.items():
        if key in supplied and supplied[key] != value:
            errors.append(f"counts.{key} is derived as {value}, not {supplied[key]}")
    return errors


def validate_review(review: dict[str, Any]) -> list[str]:
    if not isinstance(review, dict):
        return ["review document must be a JSON object"]
    errors = validate_protocol(review)
    errors.extend(validate_counts(review))
    records = review.get("records", [])
    if not isinstance(records, list):
        errors.append("records must be a list")
    else:
        for index, record in enumerate(records, 1):
            if not isinstance(record, dict):
                errors.append(f"records[{index}] must be an object")
                continue
            if not _nonempty(record.get("title")):
                errors.append(f"records[{index}].title is required")
            decision = str(record.get("decision") or "pending").lower()
            if decision not in DECISIONS:
                errors.append(f"records[{index}].decision must be include, exclude, or pending")
            stage = str(record.get("stage") or "title_abstract").lower()
            if stage not in {"title_abstract", "full_text"}:
                errors.append(f"records[{index}].stage must be title_abstract or full_text")
            if stage == "full_text" and decision == "exclude" and not _nonempty(record.get("exclusion_reason")):
                errors.append(f"records[{index}] full-text exclusion requires exclusion_reason")
    return errors


def render_prisma_flow(counts: dict[str, int]) -> str:
    """Render a Mermaid PRISMA-style flow from validated, derived counts."""
    return "\n".join([
        "flowchart TD",
        f'    A["Records identified from databases (n={counts["records_identified"]})"]',
        f'    B["Duplicates removed (n={counts["duplicates_removed"]})"]',
        f'    C["Records removed before screening (n={counts["records_removed_automation"]})"]',
        f'    D["Records screened (n={counts["records_screened"]})"]',
        f'    E["Records excluded (n={counts["records_excluded_title_abstract"]})"]',
        f'    F["Reports sought for retrieval (n={counts["reports_sought"]})"]',
        f'    G["Reports not retrieved (n={counts["reports_not_retrieved"]})"]',
        f'    H["Reports assessed for eligibility (n={counts["reports_assessed"]})"]',
        f'    I["Reports excluded (n={counts["reports_excluded_full_text"]})"]',
        f'    J["Studies included (n={counts["studies_included"]})"]',
        "    A --> B --> C --> D",
        "    D --> E",
        "    D --> F --> G",
        "    F --> H --> I",
        "    H --> J",
    ])


def build_report(review: dict[str, Any]) -> str:
    errors = validate_review(review)
    if errors:
        raise ValueError("review validation failed:\n- " + "\n- ".join(errors))
    counts = derive_counts(review)
    protocol = review["protocol"]
    lines = [
        "# Systematic review audit report",
        "",
        f'- Review type: {protocol["review_type"]}',
        f'- Research question: {protocol["question"]}',
        "",
        "## Search log",
        "",
        "| Database | Platform | Exact query | Date | Hits | Limits |",
        "|---|---|---|---|---:|---|",
    ]
    for item in review["search_log"]:
        safe = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append("| " + " | ".join(safe(item.get(key, "")) for key in
                     ("database", "platform", "query", "date_run", "hits", "limits")) + " |")
    lines.extend(["", "## PRISMA counts", "", "| Stage | n |", "|---|---:|"])
    for key, value in counts.items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")
    lines.extend(["", "## Flow diagram", "", "```mermaid", render_prisma_flow(counts), "```", ""])
    lines.append("## Eligibility criteria")
    lines.extend(["", "### Inclusion"])
    lines.extend(f"- {item}" for item in protocol.get("inclusion_criteria", []))
    lines.extend(["", "### Exclusion"])
    lines.extend(f"- {item}" for item in protocol.get("exclusion_criteria", []))
    lines.extend(["", "## Limitations", "",
                  "- Counts are calculated from the supplied search log and screening ledger; they are not independently verified.",
                  "- Eligibility decisions remain human-reviewed; this tool does not screen papers or infer exclusion reasons.",
                  "- A valid PRISMA flow does not by itself establish a complete or bias-free review.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a reproducible review ledger and render PRISMA counts.")
    parser.add_argument("input", help="review JSON file")
    parser.add_argument("--format", choices=("report", "flow", "json"), default="report")
    parser.add_argument("-o", "--output", help="write output to a file instead of stdout")
    args = parser.parse_args()
    try:
        review = json.loads(Path(args.input).read_text(encoding="utf-8"))
        errors = validate_review(review)
        if errors:
            print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
            return 2
        counts = derive_counts(review)
        if args.format == "flow":
            output = render_prisma_flow(counts)
        elif args.format == "json":
            output = json.dumps({"valid": True, "counts": counts}, ensure_ascii=False, indent=2)
        else:
            output = build_report(review)
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
