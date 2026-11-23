""""Evidence-driven A/B/C/D source tier computation for Article Finder."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_POLICY_PATH = Path(__file__).with_name("tier-policy.json")


def load_policy() -> dict[str, Any]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def compute_tier(
    *,
    source_kind: str,
    publisher_recognized: bool | None,
    specialized: bool | None,
    indexing_evidence: list[dict[str, Any]],
    quartile: str | None = None,
    quartile_source: str | None = None,
    blacklisted: bool = False,
    indexing_status: str | None = None,
    source_record_verified: bool | None = None,
    identifier_verified: bool | None = None,
    conference_scope: str | None = None,
    conference_series_established: bool | None = None,
    degree: str | None = None,
    degree_evidence_verified: bool | None = None,
    repository_verified: bool | None = None,
    derived_papers_status: str | None = None,
    derived_papers: list[dict[str, Any]] | None = None,
    university_reputable: bool | None = None,
    main_book: bool | None = None,
    publisher_verified: bool | None = None,
    citation_count: int | None = None,
    relevant_chapters: bool | None = None,
    policy: dict[str, Any] | None = None,
) -> tuple[str | None, str]:
    """Return (tier, rationale); None means the evidence is insufficient."""
    if not isinstance(source_kind, str):
        return None, "Source type must be a string; malformed input remains pending."
    if indexing_status is not None and not isinstance(indexing_status, str):
        return None, "Indexing status must be a string or null; malformed input remains pending."
    policy = policy or load_policy()
    kind = source_kind.strip().lower()
    boolean_inputs = {
        "publisher_recognized": publisher_recognized,
        "specialized": specialized,
        "blacklisted": blacklisted,
        "source_record_verified": source_record_verified,
        "identifier_verified": identifier_verified,
        "conference_series_established": conference_series_established,
        "degree_evidence_verified": degree_evidence_verified,
        "repository_verified": repository_verified,
        "university_reputable": university_reputable,
        "main_book": main_book,
        "publisher_verified": publisher_verified,
        "relevant_chapters": relevant_chapters,
    }
    invalid_boolean = next(
        (name for name, value in boolean_inputs.items()
         if value is not None and type(value) is not bool),
        None,
    )
    if invalid_boolean is not None:
        return None, f"{invalid_boolean} must be a boolean or null; invalid values remain pending."
    if not isinstance(indexing_evidence, list) or any(
        not isinstance(item, dict) for item in indexing_evidence
    ):
        return None, "Indexing evidence must be a list of evidence objects; malformed input remains pending."
    indices = {str(item.get("index") or "").strip().lower() for item in indexing_evidence}
    indices.discard("")
    if blacklisted:
        return "D", "A verified official blacklist hit overrides every positive ranking signal."

    if kind == "journal":
        if indexing_status == "not_indexed":
            return "D", "The reviewer explicitly recorded that the journal is not indexed."
        if identifier_verified is False:
            return "D", "The journal identifier failed verification; tier D is assigned."
        if identifier_verified is not True:
            return None, "A verified journal identifier is required before computing a tier."
        if not indexing_evidence or source_record_verified is not True:
            return None, "A verified indexing record is required before computing a journal tier."
        if specialized is None:
            return None, "Specialization status is required for the journal tier."
        if specialized is False:
            return "C", "The journal is indexed but outside the declared specialization."
        wos_coverage = {
            str(item.get("coverage") or "").strip().upper()
            for item in indexing_evidence
            if str(item.get("index") or "").strip().lower() in {"web of science", "wos"}
        }
        high_index = "scopus" in indices or bool(wos_coverage & {"SCIE", "SSCI", "AHCI"})
        esci = "esci" in indices or "ESCI" in wos_coverage
        if not high_index and not esci and indices & {"isc", "dblp", "doaj", "regional"}:
            return "C", "Only regional/secondary indexing evidence is recorded."
        if not high_index and not esci:
            return None, "The supplied index does not map to a configured tier rule."
        if publisher_recognized is not True:
            return None, "A recognized publisher is required for a WoS/Scopus/ESCI tier."
        if not high_index and esci:
            return "B", "ESCI coverage with a recognized publisher maps to tier B."
        q = (quartile or "").strip().upper()
        source = (quartile_source or "").strip().upper()
        if source not in {"SJR", "JCR"} or q not in {"Q1", "Q2", "Q3", "Q4"}:
            return None, "A valid Q1-Q4 quartile and explicit SJR/JCR source are required."
        if q in {"Q1", "Q2"}:
            return "A", f"{source} {q}, recognized publisher and specialization meet tier A."
        return "B", f"{source} {q} with a recognized publisher meets tier B."

    if kind == "conference":
        if source_record_verified is False or identifier_verified is False:
            return "D", "No verifiable proceedings index or edition/venue record is available."
        if source_record_verified is not True or identifier_verified is not True:
            return None, "A verified proceedings index and edition/venue record are required."
        scope = (conference_scope or "").strip().lower()
        if scope == "national":
            return "C", "A national conference with a verified proceedings record maps to tier C."
        if scope != "international":
            return None, "Conference scope must be explicitly international or national."
        if publisher_recognized is False:
            return "D", "The international proceedings publisher is not recognized or verifiable."
        if publisher_recognized is not True:
            return None, "A recognized proceedings publisher is required for an international tier."
        if conference_series_established is True and specialized is True:
            return "A", "International, established, indexed and specialized proceedings meet tier A."
        if conference_series_established is False or specialized is False:
            return "B", "International proceedings from a recognized publisher meet tier B."
        return None, "Series maturity and specialization must be reviewed."

    if kind == "thesis":
        if degree_evidence_verified is False or repository_verified is False:
            return "D", "The degree or institutional repository record could not be verified."
        if degree_evidence_verified is not True or repository_verified is not True:
            return None, "Degree and institutional repository evidence are required."
        degree_value = (degree or "").strip().lower()
        status = (derived_papers_status or "").strip().lower()
        papers = derived_papers or []
        if status not in {"found", "none"}:
            return None, "A reviewed derived-paper search must be recorded as found or none."
        if degree_value in {"phd", "doctorate", "doctoral"}:
            if status == "none":
                return "B", "A verified PhD dissertation without traceable derived papers maps to tier B."
            has_ab = any(str(item.get("tier") or "").upper() in {"A", "B"} for item in papers)
            if has_ab and university_reputable is True:
                return "A", "A reputable-university PhD with a traceable A/B derived paper maps to tier A."
            return "B", "A PhD with derived papers but without the full tier-A conditions maps to tier B."
        if degree_value in {"master", "masters", "master's", "msc", "ms"}:
            return ("C", "A Master's thesis with traceable derived papers maps to tier C.") if status == "found" else (
                "D", "A Master's thesis without derived papers maps to tier D."
            )
        if degree_value in {"bachelor", "bachelors", "bachelor's", "bsc", "bs"}:
            return "D", "A Bachelor's thesis is below the accepted degree threshold."
        return None, "The thesis degree level is missing or unrecognized."

    if kind == "book":
        if main_book is False or identifier_verified is False or publisher_verified is False:
            return "D", "A collection/non-primary book, invalid ISBN, or unverified publisher maps to tier D."
        if main_book is not True or identifier_verified is not True or publisher_verified is not True:
            return None, "Primary-book, ISBN and publisher verification are required."
        if not isinstance(citation_count, int) or isinstance(citation_count, bool) or citation_count < 0:
            return None, "A non-negative integer citation count is required."
        thresholds = policy.get("book_citations", {})
        high_min = int(thresholds.get("high_min", 50))
        modest_min = int(thresholds.get("modest_min", 10))
        if publisher_recognized is True and citation_count >= high_min and relevant_chapters is True:
            return "A", f"Recognized publisher, at least {high_min} citations and relevant chapters meet tier A."
        if publisher_recognized is True and citation_count >= modest_min:
            return "B", f"Recognized publisher and at least {modest_min} citations meet tier B."
        if publisher_recognized is False:
            return "C", "A verified primary book from a lesser-known publisher maps to tier C."
        return "C", "A primary book below the configured citation threshold maps to tier C."

    return None, "Unsupported source type; no tier was computed."
"