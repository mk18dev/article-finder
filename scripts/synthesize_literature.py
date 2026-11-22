#!/usr/bin/env python3
"""Evidence-traceable thematic synthesis from reviewer-extracted study records."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DIRECTIONS = {"positive", "negative", "null", "mixed", "unclear"}
QUALITY = {"high", "moderate", "low", "unclear"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _evidence_ok(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("reviewed") is not True:
        return False
    url = value.get("url")
    note = value.get("note")
    locator = value.get("locator", "")
    return (
        isinstance(url, str) and url.startswith("https://")
        and isinstance(note, str) and len(note.strip()) >= 8
        and isinstance(locator, str)
    )


def validate_bundle(bundle: Any) -> list[str]:
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]
    studies = bundle.get("studies")
    if not isinstance(studies, list) or not studies:
        return ["studies must be a non-empty list"]
    errors: list[str] = []
    ids: set[str] = set()
    for index, study in enumerate(studies, 1):
        prefix = f"studies[{index}]"
        if not isinstance(study, dict):
            errors.append(f"{prefix} must be an object")
            continue
        study_id = str(study.get("study_id") or "").strip()
        if not study_id:
            errors.append(f"{prefix}.study_id is required")
        elif study_id in ids:
            errors.append(f"duplicate study_id: {study_id}")
        ids.add(study_id)
        for field in ("title", "theme", "finding_summary"):
            if not _text(study.get(field)):
                errors.append(f"{prefix}.{field} is required")
        direction = str(study.get("direction") or "unclear").lower()
        if direction not in DIRECTIONS:
            errors.append(f"{prefix}.direction must be one of {', '.join(sorted(DIRECTIONS))}")
        review_status = str(study.get("review_status") or "abstract_only").lower()
        if review_status not in {"full_text", "abstract_only", "metadata_only", "not_retrieved"}:
            errors.append(f"{prefix}.review_status is invalid")
        if review_status == "full_text" and not _evidence_ok(study.get("extraction_evidence")):
            errors.append(f"{prefix} full-text extraction requires reviewed HTTPS evidence and a note")
        quality = study.get("quality_appraisal")
        if quality is not None:
            if not isinstance(quality, dict) or str(quality.get("rating") or "").lower() not in QUALITY:
                errors.append(f"{prefix}.quality_appraisal.rating must be high, moderate, low, or unclear")
            elif not _evidence_ok(quality.get("evidence")):
                errors.append(f"{prefix} quality rating requires reviewed evidence")
    claims = bundle.get("claims", [])
    if not isinstance(claims, list):
        errors.append("claims must be a list")
    else:
        for index, claim in enumerate(claims, 1):
            prefix = f"claims[{index}]"
            if not isinstance(claim, dict) or not _text(claim.get("claim_text")):
                errors.append(f"{prefix}.claim_text is required")
                continue
            linked = claim.get("study_ids")
            if not isinstance(linked, list) or not linked:
                errors.append(f"{prefix}.study_ids must link at least one study")
                continue
            unknown = [str(item) for item in linked if str(item) not in ids]
            if unknown:
                errors.append(f"{prefix} references unknown study IDs: {', '.join(unknown)}")
            evidence = claim.get("source_evidence", [])
            if not isinstance(evidence, list):
                errors.append(f"{prefix}.source_evidence must be a list")
    return errors


def synthesize(bundle: dict[str, Any]) -> dict[str, Any]:
    errors = validate_bundle(bundle)
    if errors:
        raise ValueError("evidence bundle validation failed:\n- " + "\n- ".join(errors))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for study in bundle["studies"]:
        groups[str(study["theme"]).strip()].append(study)

    themes = []
    for theme, studies in sorted(groups.items(), key=lambda item: item[0].casefold()):
        directions = Counter(str(study.get("direction") or "unclear").lower() for study in studies)
        observed = {key for key in directions if key in {"positive", "negative", "null"}}
        full_text = sum(1 for study in studies if study.get("review_status") == "full_text")
        quality_rated = sum(1 for study in studies if isinstance(study.get("quality_appraisal"), dict))
        flags = []
        if len(studies) < 2:
            flags.append("single-study theme; consistency cannot be assessed")
        if full_text == 0:
            flags.append("no full-text-reviewed study")
        if quality_rated == 0:
            flags.append("no evidence-backed quality appraisal")
        if len(observed) > 1 or "mixed" in directions:
            flags.append("conflicting or mixed reported directions")
        themes.append({
            "theme": theme,
            "study_count": len(studies),
            "direction_counts": dict(sorted(directions.items())),
            "full_text_reviewed": full_text,
            "quality_appraised": quality_rated,
            "conflict_flag": len(observed) > 1 or "mixed" in directions,
            "coverage_flags": flags,
            "studies": [
                {
                    "study_id": study["study_id"],
                    "title": study["title"],
                    "doi": study.get("doi", ""),
                    "year": study.get("year"),
                    "study_design": study.get("study_design", ""),
                    "population": study.get("population", ""),
                    "method": study.get("method", ""),
                    "outcome": study.get("outcome", ""),
                    "direction": study.get("direction", "unclear"),
                    "finding_summary": study["finding_summary"],
                    "limitations": study.get("limitations", []),
                    "review_status": study.get("review_status", "abstract_only"),
                    "quality_appraisal": study.get("quality_appraisal"),
                }
                for study in studies
            ],
        })

    study_ids = {str(study["study_id"]) for study in bundle["studies"]}
    claim_map = []
    for claim in bundle.get("claims", []):
        evidence_by_id = {
            str(item.get("study_id")): item for item in claim.get("source_evidence", [])
            if isinstance(item, dict)
        }
        linked = [str(item) for item in claim["study_ids"]]
        supported = [
            study_id for study_id in linked
            if study_id in study_ids
            and _evidence_ok({
                "reviewed": evidence_by_id.get(study_id, {}).get("reviewed"),
                "url": evidence_by_id.get(study_id, {}).get("url"),
                "note": evidence_by_id.get(study_id, {}).get("quote"),
                "locator": evidence_by_id.get(study_id, {}).get("locator", ""),
            })
        ]
        claim_map.append({
            "claim_text": claim["claim_text"],
            "study_ids": linked,
            "evidence_linked_study_ids": supported,
            "status": "evidence_linked" if set(supported) == set(linked) else "pending",
        })

    return {
        "review_title": bundle.get("review_title", ""),
        "themes": themes,
        "claim_map": claim_map,
        "study_count": len(bundle["studies"]),
        "theme_count": len(themes),
        "limitations": [
            "The synthesis summarizes reviewer-supplied extraction fields; it does not read papers or independently verify findings.",
            "Direction counts are descriptive and are not effect estimates or a meta-analysis.",
            "Coverage flags are prompts for review, not proof that a research gap exists.",
            "Claim-to-source links require a reviewed excerpt and locator; a DOI alone is not claim support.",
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = ["# Evidence synthesis", ""]
    if result.get("review_title"):
        lines.extend([str(result["review_title"]), ""])
    lines.extend([f'- Studies: {result["study_count"]}', f'- Themes: {result["theme_count"]}', ""])
    for item in result["themes"]:
        lines.extend([
            f'## {item["theme"]}',
            "",
            f'- Studies: {item["study_count"]}',
            f'- Reported directions: {json.dumps(item["direction_counts"], ensure_ascii=False)}',
            f'- Full-text reviewed: {item["full_text_reviewed"]}',
            f'- Quality appraised: {item["quality_appraised"]}',
        ])
        for flag in item["coverage_flags"]:
            lines.append(f'- Coverage flag: {flag}')
        lines.extend(["", "| Study | Year | Design | Direction | Finding extracted by reviewer | Limitations |",
                      "|---|---:|---|---|---|---|"])
        for study in item["studies"]:
            def safe(value):
                return str(value or "").replace("|", "\\|").replace("\n", " ")
            limitations = "; ".join(study.get("limitations") or [])
            lines.append("| " + " | ".join((
                safe(study["title"]), safe(study.get("year")), safe(study.get("study_design")),
                safe(study.get("direction")), safe(study.get("finding_summary")), safe(limitations),
            )) + " |")
        lines.append("")
    lines.extend(["## Claim-to-source map", ""])
    if not result["claim_map"]:
        lines.append("No manuscript claims were supplied for mapping.")
    for claim in result["claim_map"]:
        lines.append(f'- **{claim["status"]}** — {claim["claim_text"]}')
        lines.append(f'  - Linked studies: {", ".join(claim["study_ids"])}')
        lines.append(f'  - Excerpt-backed studies: {", ".join(claim["evidence_linked_study_ids"]) or "none"}')
    lines.extend(["", "## Methodological limitations", ""])
    lines.extend(f"- {item}" for item in result["limitations"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an evidence matrix and cautious thematic synthesis.")
    parser.add_argument("input", help="JSON bundle of reviewer-extracted studies")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    try:
        bundle = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = synthesize(bundle)
        output = (json.dumps(result, ensure_ascii=False, indent=2)
                  if args.format == "json" else render_markdown(result))
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
