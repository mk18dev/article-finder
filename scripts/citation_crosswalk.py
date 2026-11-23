#!/usr/bin/env python3
"""Cross-check in-text APA/IEEE citations against a structured reference list."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

IEEE_RE = re.compile(r"\[(\d+(?:\s*[-–]\s*\d+)?(?:\s*[,،]\s*\d+(?:\s*[-–]\s*\d+)?)*)\]")
APA_PAREN_RE = re.compile(r"\(([^()]{0,240}(?:13|14|19|20)\d{2}[a-z]?[^()]*)\)", re.UNICODE)
APA_PAIR_RE = re.compile(
    r"([^\W\d_][^\d,;()]{0,80}?),?\s*((?:13|14|19|20)\d{2}[a-z]?)",
    re.UNICODE,
)
APA_NARRATIVE_RE = re.compile(
    r"([^\W\d_][^\d()]{0,80}?)\s+\(((?:13|14|19|20)\d{2}[a-z]?)\)",
    re.UNICODE,
)


REFERENCE_HEADING_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:references|bibliography|works cited|منابع|مراجع)\s*$"
)
IEEE_BRACKET_RE = re.compile(r"\[[^\]]*\d[^\]]*\]")


def _body_text(text: str) -> str:
    match = REFERENCE_HEADING_RE.search(text)
    return text[:match.start()] if match else text


def _references(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        refs = document
    elif isinstance(document, dict):
        if "references" in document:
            refs = document["references"]
        elif "citations" in document:
            refs = document["citations"]
        else:
            raise ValueError("reference object must contain references or citations")
    else:
        raise ValueError("reference input must be a list or an object")
    if not isinstance(refs, list) or not all(isinstance(item, dict) for item in refs):
        raise ValueError("reference input must be a list or contain references/citations list")
    return refs


def _doi(value: Any) -> str:
    raw = str(value or "").strip()
    raw = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw, flags=re.I)
    raw = re.sub(r"^doi:\s*", "", raw, flags=re.I)
    return raw.rstrip(" .").casefold()


def _author_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = text.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": ""}))
    text = text.replace("\u200c", "").replace("\u200f", "").replace("\u200e", "")
    if not text:
        return ""
    text = re.sub(r"\s+et\s+al\.?$", "", text, flags=re.I)
    text = re.split(r"\s*(?:&|and|و)\s*", text, maxsplit=1, flags=re.I)[0]
    if re.search(r"[,،]", text):
        family = re.split(r"[,،]", text, maxsplit=1)[0]
    else:
        family = text.split()[-1] if text.split() else ""
    return re.sub(r"[^\w]", "", family.casefold(), flags=re.UNICODE)



def _year(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    match = re.search(r"(?:13|14|19|20)\d{2}[a-z]?", normalized, flags=re.I)
    return match.group(0).casefold() if match else ""



def _reference_author(reference: dict[str, Any]) -> str:
    value = reference.get("first_author") or reference.get("author")
    if not value and isinstance(reference.get("authors"), list) and reference["authors"]:
        value = reference["authors"][0]
    if isinstance(value, dict):
        value = value.get("family") or value.get("name")
    return _author_key(value)


def _expand_ieee(body: str) -> list[int]:
    result: list[int] = []
    for token in re.split(r"[,،]", body):
        token = token.strip()
        if "-" in token or "–" in token:
            parts = re.split(r"[-–]", token)
            if len(parts) != 2 or not all(part.strip().isdigit() for part in parts):
                raise ValueError(f"invalid IEEE range: {token}")
            start, end = (int(part.strip()) for part in parts)
            if end < start or end - start > 100:
                raise ValueError(f"unsafe IEEE citation range: {token}")
            result.extend(range(start, end + 1))
        elif token.isdigit():
            result.append(int(token))
        else:
            raise ValueError(f"invalid IEEE citation number: {token}")
    return result


def audit_ieee(text: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    text = _body_text(text)
    ref_numbers: dict[int, dict[str, Any]] = {}
    errors = []
    for index, reference in enumerate(references, 1):
        raw = reference.get("ref_id", reference.get("number", index))
        try:
            number = int(raw)
        except (TypeError, ValueError):
            errors.append(f"reference {index} has a non-numeric ref_id")
            continue
        if number in ref_numbers:
            errors.append(f"duplicate bibliography number: {number}")
        ref_numbers[number] = reference
    cited: list[int] = []
    malformed = []
    valid_spans = set()
    for match in IEEE_RE.finditer(text):
        valid_spans.add(match.span())
        try:
            cited.extend(_expand_ieee(match.group(1)))
        except ValueError as exc:
            malformed.append(str(exc))
    for match in IEEE_BRACKET_RE.finditer(text):
        if match.span() not in valid_spans:
            malformed.append(f"unrecognized IEEE citation: {match.group(0)}")
    cited_set = set(cited)
    missing = sorted(cited_set - set(ref_numbers))
    uncited = sorted(set(ref_numbers) - cited_set)
    duplicate_dois = _duplicate_dois(references)
    return {
        "style": "IEEE",
        "status": "pass" if not (errors or malformed or missing or uncited or duplicate_dois) else "review",
        "in_text_citation_count": len(cited),
        "unique_in_text_numbers": sorted(cited_set),
        "missing_bibliography_numbers": missing,
        "uncited_bibliography_numbers": uncited,
        "duplicate_dois": duplicate_dois,
        "malformed_citations": malformed,
        "reference_input_errors": errors,
    }


def audit_apa(text: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    text = _body_text(text)
    reference_keys: dict[tuple[str, str], list[int]] = defaultdict(list)
    invalid = []
    for index, reference in enumerate(references, 1):
        author = _reference_author(reference)
        year = _year(reference.get("year"))
        if not author or not year:
            invalid.append(f"reference {index} requires first author and year")
            continue
        reference_keys[(author, year)].append(index)

    citations: list[dict[str, str]] = []
    malformed = []
    narrative_matches = list(APA_NARRATIVE_RE.finditer(text))
    for match in APA_PAREN_RE.finditer(text):
        # A year-only parenthetical belonging to "Smith (2020)" is narrative,
        # not a malformed parenthetical citation.
        if any(narrative.start() <= match.start() and narrative.end() == match.end()
               for narrative in narrative_matches):
            continue
        body = match.group(1)
        found_pairs = 0
        for part in body.split(";"):
            pairs = APA_PAIR_RE.findall(part)
            found_pairs += len(pairs)
            for author, year in pairs:
                citations.append({"author": _author_key(author), "year": year.casefold(), "raw": part.strip()})
        if not found_pairs:
            malformed.append(f"unrecognized APA citation: ({body})")
    for match in narrative_matches:
        citations.append({
            "author": _author_key(match.group(1)),
            "year": match.group(2).casefold(),
            "raw": match.group(0),
        })

    matched_reference_indices = set()
    unmatched = []
    for citation in citations:
        key = (citation["author"], citation["year"])
        candidates = reference_keys.get(key, [])
        if candidates:
            matched_reference_indices.update(candidates)
        else:
            unmatched.append(citation)

    uncited = [
        index for indices in reference_keys.values() for index in indices
        if index not in matched_reference_indices
    ]
    duplicate_keys = [
        {"author": key[0], "year": key[1], "reference_indices": indices}
        for key, indices in reference_keys.items() if len(indices) > 1
    ]
    duplicate_dois = _duplicate_dois(references)
    return {
        "style": "APA",
        "status": "pass" if not (invalid or unmatched or uncited or duplicate_keys or duplicate_dois or malformed) else "review",
        "in_text_citation_count": len(citations),
        "matched_reference_indices": sorted(matched_reference_indices),
        "unmatched_in_text_citations": unmatched,
        "malformed_citations": malformed,
        "uncited_reference_indices": sorted(uncited),
        "duplicate_author_year_keys": duplicate_keys,
        "duplicate_dois": duplicate_dois,
        "reference_input_errors": invalid,
    }


def _duplicate_dois(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, list[int]] = defaultdict(list)
    for index, reference in enumerate(references, 1):
        doi = _doi(reference.get("doi"))
        if doi:
            seen[doi].append(index)
    return [{"doi": doi, "reference_indices": indices}
            for doi, indices in seen.items() if len(indices) > 1]


def _normalize_digits(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )


def audit(text: str, document: Any, style: str) -> dict[str, Any]:
    references = _references(document)
    text = _normalize_digits(text)
    normalized = style.strip().upper()
    if normalized == "IEEE":
        return audit_ieee(text, references)
    if normalized == "APA":
        return audit_apa(text, references)
    raise ValueError("style must be APA or IEEE")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-check manuscript citations against a reference list.")
    parser.add_argument("manuscript", help="plain-text manuscript")
    parser.add_argument("references", help="JSON list or object containing references")
    parser.add_argument("--style", choices=("APA", "IEEE"), required=True)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    try:
        text = Path(args.manuscript).read_text(encoding="utf-8")
        refs = json.loads(Path(args.references).read_text(encoding="utf-8"))
        result = audit(text, refs, args.style)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0 if result["status"] == "pass" else 1
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
