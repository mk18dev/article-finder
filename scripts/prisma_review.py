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
from datetime import date, datetime
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
    reviewers = protocol.get("reviewers")
    if not isinstance(reviewers, list) or not reviewers or not all(_nonempty(v) for v in reviewers):
        errors.append("protocol.reviewers must list reviewer IDs")
    elif len(set(reviewers)) != len(reviewers):
        errors.append("protocol.reviewers must be unique")
    dual = protocol.get("dual_screening")
    if not isinstance(dual, bool):
        errors.append("protocol.dual_screening must be explicitly true or false")
    elif dual and isinstance(reviewers, list) and len(reviewers) < 2:
        errors.append("dual screening requires at least two reviewer IDs")
    elif dual is False and not _nonempty(protocol.get("single_reviewer_justification")):
        errors.append("single_reviewer_justification is required when dual_screening is false")
    searches = review.get("search_log")
    if not isinstance(searches, list) or not searches:
        errors.append("search_log must contain at least one database search")
        return errors
    for index, item in enumerate(searches, 1):
        prefix = f"search_log[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("database", "platform", "query", "date_run", "search_url"):
            if not _nonempty(item.get(field)):
                errors.append(f"{prefix}.{field} is required")
        if item.get("status") == "error":
            errors.append(f"{prefix} is marked failed and cannot count as a completed search")
        search_url = str(item.get("search_url") or "")
        if search_url and not search_url.startswith("https://"):
            errors.append(f"{prefix}.search_url must use HTTPS")
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


def _valid_timestamp(value: Any) -> bool:
    if not _nonempty(value):
        return False
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


def _validate_stage_review(review: Any, protocol: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(review, dict):
        return [f"{prefix} review record is required"]
    reviewers = protocol.get("reviewers") or []
    dual = protocol.get("dual_screening") is True

    def check_one(item: Any, label: str) -> tuple[str, str]:
        if not isinstance(item, dict):
            errors.append(f"{prefix}.{label} must be an object")
            return "", ""
        reviewer_id = str(item.get("reviewer_id") or "").strip()
        decision = str(item.get("decision") or "").lower()
        if reviewer_id not in reviewers:
            errors.append(f"{prefix}.{label}.reviewer_id must be declared in protocol.reviewers")
        if decision not in {"include", "exclude"}:
            errors.append(f"{prefix}.{label}.decision must be include or exclude")
        if not _valid_timestamp(item.get("reviewed_at")):
            errors.append(f"{prefix}.{label}.reviewed_at must be timezone-aware ISO-8601")
        return reviewer_id, decision

    primary_id, primary_decision = check_one(review, "primary")
    final_decision = str(review.get("decision") or "").lower()
    if not dual:
        if final_decision != primary_decision:
            errors.append(f"{prefix}.decision must match the primary reviewer decision")
        return errors

    second = review.get("second_review")
    second_id, second_decision = check_one(second, "second_review")
    if second_id and second_id == primary_id:
        errors.append(f"{prefix} reviewers must be independent")
    if second_id and second_id not in reviewers:
        errors.append(f"{prefix}.second_review reviewer must be declared in protocol.reviewers")
    if primary_decision and second_decision and primary_decision == second_decision:
        if final_decision != primary_decision:
            errors.append(f"{prefix}.decision must match the agreeing reviewers")
        if review.get("adjudication") is not None:
            errors.append(f"{prefix}.adjudication is unnecessary when reviewers agree")
    elif primary_decision and second_decision and primary_decision != second_decision:
        adjudication = review.get("adjudication")
        if not isinstance(adjudication, dict):
            errors.append(f"{prefix} disagreement requires an adjudication record")
        else:
            if str(adjudication.get("decision") or "").lower() not in {"include", "exclude"}:
                errors.append(f"{prefix}.adjudication.decision must be include or exclude")
            if not _nonempty(adjudication.get("reviewer_id")):
                errors.append(f"{prefix}.adjudication.reviewer_id is required")
            if not _valid_timestamp(adjudication.get("reviewed_at")):
                errors.append(f"{prefix}.adjudication.reviewed_at must be timezone-aware ISO-8601")
            if not _nonempty(adjudication.get("note")):
                errors.append(f"{prefix}.adjudication.note is required")
            if final_decision != str(adjudication.get("decision") or "").lower():
                errors.append(f"{prefix}.decision must match the adjudication")
    return errors


def _screened_records(review: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = review.get("records") or []
    return deduplicate_records(records)


def derive_counts(review: dict[str, Any]) -> dict[str, int]:
    searches = review.get("search_log") or []
    raw_records = review.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("records must be a list of raw records from every completed search")
    identified = sum(item["hits"] for item in searches)
    if len(raw_records) != identified:
        raise ValueError(
            f"raw record count ({len(raw_records)}) must equal retrieved search hits ({identified}); "
            "do not pass only deduplicated records"
        )
    unique, duplicates = _screened_records(review)
    automation_removed = sum(1 for item in unique if item.get("automation_excluded") is True)
    screened_records = [item for item in unique if item.get("automation_excluded") is not True]
    title_reviews = [item["title_abstract_review"] for item in screened_records]
    title_excluded = sum(1 for item in title_reviews if str(item.get("decision")).lower() == "exclude")
    reports_sought = sum(1 for item in title_reviews if str(item.get("decision")).lower() == "include")
    not_retrieved = sum(1 for item in screened_records if item.get("full_text_status") == "not_retrieved")
    assessed_records = [item for item in screened_records if item.get("full_text_status") == "retrieved"]
    full_reviews = [item["full_text_review"] for item in assessed_records]
    full_excluded = sum(1 for item in full_reviews if str(item.get("decision")).lower() == "exclude")
    included = sum(1 for item in full_reviews if str(item.get("decision")).lower() == "include")
    return {
        "records_identified": identified,
        "duplicates_removed": len(duplicates),
        "records_removed_automation": automation_removed,
        "records_screened": len(screened_records),
        "records_excluded_title_abstract": title_excluded,
        "reports_sought": reports_sought,
        "reports_not_retrieved": not_retrieved,
        "reports_assessed": len(assessed_records),
        "reports_excluded_full_text": full_excluded,
        "studies_included": included,
    }


def validate_counts(review: dict[str, Any]) -> list[str]:
    try:
        derived = derive_counts(review)
    except (KeyError, TypeError, ValueError) as exc:
        return [str(exc)]
    supplied = review.get("counts")
    if supplied is None:
        return []
    if not isinstance(supplied, dict):
        return ["counts must be an object when supplied"]
    errors = []
    for key, value in derived.items():
        if key in supplied and supplied[key] != value:
            errors.append(f"counts.{key} is derived from the record ledger as {value}, not {supplied[key]}")
    return errors


def validate_review(review: dict[str, Any]) -> list[str]:
    if not isinstance(review, dict):
        return ["review document must be a JSON object"]
    errors = validate_protocol(review)
    errors.extend(validate_counts(review))
    records = review.get("records")
    if not isinstance(records, list):
        return errors + ["records must be a list of raw records from every completed search"]
    if errors:
        return errors
    protocol = review["protocol"]
    unique, duplicates = _screened_records(review)
    raw_ids = [str(item.get("record_id") or "").strip() for item in records if isinstance(item, dict)]
    if any(not value for value in raw_ids):
        errors.append("every raw record requires record_id")
    if len(raw_ids) != len(set(raw_ids)):
        errors.append("raw record_id values must be unique")
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
        elif not _nonempty(record.get("title")):
            errors.append(f"records[{index}].title is required")

    for record in unique:
        record_id = str(record.get("record_id") or "unknown")
        if record.get("automation_excluded") is True:
            if not _nonempty(record.get("automation_exclusion_reason")) or not _nonempty(record.get("automation_tool")):
                errors.append(f"{record_id} automation exclusion requires tool and reason")
            if record.get("full_text_status", "not_sought") != "not_sought":
                errors.append(f"{record_id} automation-excluded record must be not_sought")
            continue
        if record.get("automation_excluded", False) is not False:
            errors.append(f"{record_id}.automation_excluded must be boolean")
        title_review = record.get("title_abstract_review")
        errors.extend(_validate_stage_review(title_review, protocol, f"{record_id}.title_abstract_review"))
        decision = str((title_review or {}).get("decision") or "").lower() if isinstance(title_review, dict) else ""
        full_status = str(record.get("full_text_status") or "").lower()
        if decision == "exclude":
            if full_status != "not_sought":
                errors.append(f"{record_id} title/abstract-excluded record must be not_sought")
            if record.get("full_text_review") is not None:
                errors.append(f"{record_id} must not have a full-text review when excluded at title/abstract")
        elif decision == "include":
            if full_status not in {"not_retrieved", "retrieved"}:
                errors.append(f"{record_id} included record must be not_retrieved or retrieved")
            if full_status == "not_retrieved" and record.get("full_text_review") is not None:
                errors.append(f"{record_id} not-retrieved report cannot have a full-text review")
            if full_status == "retrieved":
                full_review = record.get("full_text_review")
                errors.extend(_validate_stage_review(full_review, protocol, f"{record_id}.full_text_review"))
                full_decision = str((full_review or {}).get("decision") or "").lower() if isinstance(full_review, dict) else ""
                if full_decision == "exclude" and not _nonempty((full_review or {}).get("exclusion_reason")):
                    errors.append(f"{record_id} full-text exclusion requires exclusion_reason")
        elif decision:
            errors.append(f"{record_id} title/abstract decision is unresolved")
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
