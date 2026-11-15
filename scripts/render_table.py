#!/usr/bin/env python3
"""Render the article-finder checklist tables from a JSON results file.

Usage:
    python3 render_table.py results.json [--lang fa|en] [--cutoff A|B|C|D] [--evidence]
                                         [--bibliography apa|ieee]

Input JSON: either a list of articles or {"cutoff": "B", "articles": [...]}.
Each article:
    {
      "title":    "Paper title",                 (required)
      "authors":  ["Family, G. I.", "Other, A."], (optional; used by --bibliography)
      "year":     2024,
      "type":     "journal|conference|thesis|book",
      "venue":    "Journal / conference / university / publisher",
      "url":      "https://...",
      "category": "concept|challenge|application|methodology",
      "tier":     "A|B|C|D",
      "keyword":  "keyword pair that found it",
      "steps":    {"S1": true, "S2": true, ... "S11": null},
      "evidence": {"S6": "Scopus Q1, SJR 2024"},  (optional, shown with --evidence)
      "notes":    "Why it failed, or what the user must verify"
    }
Step values: true = verified, false = checked and failed, null/missing = not verified.
S9 (tier is not below the cut-off) is computed here from "tier" and the cut-off,
so any value given for it is ignored.

Verdict: APPROVED only if all 11 steps are true; REJECTED if any is false;
otherwise PENDING. Only approved articles appear in the first table.

Duplicate records (same "doi", same "url", or the same normalised title) are
collapsed before evaluation, so a source found by two keyword pairs cannot be
counted twice.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Iterable

STEPS: list[str] = [f"S{i}" for i in range(1, 12)]
TIER_RANK: dict[str, int] = {"A": 1, "B": 2, "C": 3, "D": 4}
MARK: dict[bool | None, str] = {True: "✅", False: "❌", None: "❓"}
CATEGORY_ORDER: list[str] = ["concept", "challenge", "application", "methodology"]

LABELS: dict[str, dict[str, Any]] = {
    "en": {
        "S1": "Area", "S2": "Subject", "S3": "Keyword", "S4": "Source type",
        "S5": "Publisher/venue", "S6": "Indexing", "S7": "Identifiers",
        "S8": "Specialization & year", "S9": "Tier ≥ cut-off", "S10": "Category",
        "S11": "Extraction",
        "approved": "Approved sources (all steps ticked)",
        "pending": "Pending: needs your verification",
        "rejected": "Rejected",
        "article": "Article", "type": "Type", "tier": "Tier", "category": "Category",
        "step": "Step", "reason": "Reason / what to check",
        "legend": "Steps", "summary": "Summary", "cutoff": "Tier cut-off",
        "none": "None.",
        "n_approved": "approved", "n_pending": "pending", "n_rejected": "rejected",
        "cat": {"concept": "Concept", "challenge": "Challenge",
                "application": "Application", "methodology": "Methodology"},
        "typ": {"journal": "Journal", "conference": "Conference",
                "thesis": "Thesis", "book": "Book"},
        "evidence": "Evidence", "bibliography": "References",
        "bib_pending": "Included but still pending — verify before submitting",
        "duplicates": "duplicates merged",
    },
    "fa": {
        "S1": "حوزه", "S2": "موضوع", "S3": "کلیدواژه", "S4": "نوع منبع",
        "S5": "ناشر/محل انتشار", "S6": "نمایه‌سازی", "S7": "شناسه‌ها (ISSN/ISBN)",
        "S8": "تخصص و سال", "S9": "رتبه ≥ حد نصاب", "S10": "دسته‌بندی",
        "S11": "استخراج",
        "approved": "منابع تأییدشده (همه مراحل تیک‌خورده)",
        "pending": "در انتظار بررسی شما",
        "rejected": "ردشده",
        "article": "منبع", "type": "نوع", "tier": "رتبه", "category": "دسته",
        "step": "مرحله", "reason": "دلیل / مورد بررسی",
        "legend": "مراحل", "summary": "خلاصه", "cutoff": "حد نصاب رتبه",
        "none": "موردی نیست.",
        "n_approved": "تأییدشده", "n_pending": "در انتظار", "n_rejected": "ردشده",
        "cat": {"concept": "مفهوم", "challenge": "چالش",
                "application": "کاربرد", "methodology": "روش‌شناسی"},
        "typ": {"journal": "مقاله ژورنالی", "conference": "مقاله کنفرانسی",
                "thesis": "پایان‌نامه", "book": "کتاب"},
        "evidence": "مستندات", "bibliography": "فهرست منابع",
        "bib_pending": "در فهرست آمده ولی هنوز در انتظار است — پیش از ارسال وارسی کن",
        "duplicates": "رکورد تکراری ادغام شد",
    },
}


def esc(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def title_cell(article: dict[str, Any]) -> str:
    title = esc(article.get("title", "(untitled)"))
    year = article.get("year")
    suffix = f" ({year})" if year else ""
    url = article.get("url")
    return f"[{title}]({url}){suffix}" if url else f"{title}{suffix}"


def notes_text(article: dict[str, Any], lang: str) -> str:
    notes = article.get("notes", "")
    if isinstance(notes, dict):
        return str(notes.get(lang) or notes.get("en") or "")
    return str(notes)


def identity(article: dict[str, Any]) -> str:
    for key in ("doi",):
        if article.get(key):
            return str(article[key]).lower()
    if article.get("url"):
        return str(article["url"]).lower()
    return re.sub(r"\W+", "", str(article.get("title", "")).lower())


def dedupe(articles: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for article in articles:
        key = identity(article)
        if key in seen:
            merged_steps = seen[key].setdefault("steps", {})
            for step, value in article.get("steps", {}).items():
                if merged_steps.get(step) is None and value is not None:
                    merged_steps[step] = value
            continue
        seen[key] = article
        order.append(key)
    return [seen[k] for k in order], len(articles) - len(order)


def evaluate(article: dict[str, Any], cutoff: str) -> tuple[dict[str, bool | None], str]:
    steps: dict[str, bool | None] = {s: article.get("steps", {}).get(s) for s in STEPS}
    tier = str(article.get("tier", "")).upper()
    steps["S9"] = TIER_RANK[tier] <= TIER_RANK[cutoff] if tier in TIER_RANK else None
    if any(v is False for v in steps.values()):
        verdict = "REJECTED"
    elif any(v is None for v in steps.values()):
        verdict = "PENDING"
    else:
        verdict = "APPROVED"
    return steps, verdict


def first_step(steps: dict[str, bool | None], wanted: bool | None) -> str:
    for step in STEPS:
        if steps[step] is wanted:
            return step
    return "S1"


def sort_key(article: dict[str, Any]) -> tuple[int, int, int]:
    category = str(article.get("category", "")).lower()
    return (
        CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else len(CATEGORY_ORDER),
        TIER_RANK.get(str(article.get("tier", "")).upper(), 9),
        -(article.get("year") or 0),
    )


def split_author(name: str) -> tuple[str, str]:
    if "," in name:
        family, given = name.split(",", 1)
        return family.strip(), given.strip()
    parts = name.split()
    return parts[-1], " ".join(parts[:-1])


def apa_authors(names: list[str]) -> str:
    if not names:
        return "(no author recorded)"
    formatted = [f"{split_author(n)[0]}, {split_author(n)[1]}" for n in names[:20]]
    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + ", & " + formatted[-1]


def ieee_authors(names: list[str]) -> str:
    if not names:
        return "(no author recorded)"
    formatted = []
    for name in names[:6]:
        family, given = split_author(name)
        formatted.append(f"{given} {family}".strip())
    tail = ", et al." if len(names) > 6 else ""
    return ", ".join(formatted) + tail


def bibliography(articles: list[dict[str, Any]], style: str, lang: str) -> str:
    label = LABELS[lang]["bibliography"]
    lines = [f"### {label}\n"]
    pending = 0
    for index, article in enumerate(articles, 1):
        verdict = evaluate(article, "D")[1]
        if verdict == "REJECTED":
            continue
        pending += verdict == "PENDING"
        authors = article.get("authors") or []
        title = esc(article.get("title", "(untitled)")).rstrip(".")
        venue = esc(article.get("venue", ""))
        volume = esc(article.get("volume", ""))
        pages = esc(article.get("pages", ""))
        year = article.get("year") or "n.d."
        doi = article.get("doi") or ""
        link = f"https://doi.org/{doi}" if doi else article.get("url", "")
        if style == "apa":
            tail = ", ".join(p for p in (venue, volume, pages) if p)
            lines.append(f"{index}. {apa_authors(authors)} ({year}). {title}. {tail}. {link}".strip(" .") + ".")
        else:
            tail = ", ".join(p for p in (venue, str(year), f"pp. {pages}" if pages else "") if p)
            lines.append(f"[{index}] {ieee_authors(authors)}, \u201c{title},\u201d {tail}. {link}".strip())
    lines.append("")
    if pending:
        lines.append(f"**{LABELS[lang]['bib_pending']}:** {pending}")
    return "\n".join(lines)


def render(data: dict[str, Any] | list[dict[str, Any]], lang: str, cutoff: str,
           with_evidence: bool, bib_style: str | None) -> str:
    L = LABELS[lang]
    raw = data["articles"] if isinstance(data, dict) else data
    articles, merged = dedupe(raw)
    evaluated: list[tuple[dict[str, Any], dict[str, bool | None], str]] = []
    for article in articles:
        steps, verdict = evaluate(article, cutoff)
        evaluated.append((article, steps, verdict))

    out: list[str] = []
    approved = sorted([e for e in evaluated if e[2] == "APPROVED"], key=lambda e: sort_key(e[0]))
    pending = [e for e in evaluated if e[2] == "PENDING"]
    rejected = [e for e in evaluated if e[2] == "REJECTED"]

    out.append(f"### {L['approved']}\n")
    if approved:
        head = ["#", L["article"], L["type"], L["tier"], L["category"]] + [s[1:] for s in STEPS]
        out.append("| " + " | ".join(head) + " |")
        out.append("|" + "|".join(["---"] * len(head)) + "|")
        for i, (article, steps, _) in enumerate(approved, 1):
            row = [
                str(i), title_cell(article),
                L["typ"].get(str(article.get("type", "")).lower(), esc(article.get("type", ""))),
                str(article.get("tier", "")).upper(),
                L["cat"].get(str(article.get("category", "")).lower(), esc(article.get("category", ""))),
            ] + [MARK[steps[s]] for s in STEPS]
            out.append("| " + " | ".join(row) + " |")
    else:
        out.append(L["none"])
    out.append("")

    legend = " · ".join(f"{s[1:]} = {L[s]}" for s in STEPS)
    out.append(f"**{L['legend']}:** {legend}\n")

    if with_evidence and approved:
        out.append(f"#### {L['evidence']}\n")
        for i, (article, _, _) in enumerate(approved, 1):
            evidence = article.get("evidence") or {}
            if evidence:
                items = "; ".join(f"{k[1:]}: {esc(v)}"
                                  for k, v in sorted(evidence.items(), key=lambda kv: int(kv[0][1:])))
                out.append(f"- #{i} → {items}")
        out.append("")

    out.append(f"### {L['pending']}\n")
    if pending:
        out.append(f"| # | {L['article']} | {L['step']} | {L['reason']} |")
        out.append("|---|---|---|---|")
        for i, (article, steps, _) in enumerate(pending, 1):
            step = first_step(steps, None)
            out.append(f"| {i} | {title_cell(article)} | {step[1:]} {L[step]} ❓ | {esc(notes_text(article, lang))} |")
    else:
        out.append(L["none"])
    out.append("")

    out.append(f"### {L['rejected']}\n")
    if rejected:
        out.append(f"| # | {L['article']} | {L['step']} | {L['reason']} |")
        out.append("|---|---|---|---|")
        for i, (article, steps, _) in enumerate(rejected, 1):
            step = first_step(steps, False)
            out.append(f"| {i} | {title_cell(article)} | {step[1:]} {L[step]} ❌ | {esc(notes_text(article, lang))} |")
    else:
        out.append(L["none"])
    out.append("")

    summary = (
        f"**{L['summary']}:** {len(approved)} {L['n_approved']} · "
        f"{len(pending)} {L['n_pending']} · {len(rejected)} {L['n_rejected']} "
        f"({L['cutoff']}: {cutoff})"
    )
    if merged:
        summary += f" · {merged} {L['duplicates']}"
    out.append(summary)

    if bib_style:
        out.append("")
        out.append(bibliography([e[0] for e in evaluated], bib_style, lang))
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the article-finder checklist tables.")
    parser.add_argument("input", help="path to the results JSON file")
    parser.add_argument("--lang", choices=["fa", "en"], default="en")
    parser.add_argument("--cutoff", choices=list(TIER_RANK), default=None,
                        help="lowest tier that is kept (default: B, or the value in the file)")
    parser.add_argument("--evidence", action="store_true", help="list the evidence behind each tick")
    parser.add_argument("--bibliography", choices=["apa", "ieee"],
                        help="also print the reference list for every non-rejected source")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as handle:
        data = json.load(handle)
    cutoff = args.cutoff or (data.get("cutoff") if isinstance(data, dict) else None) or "B"
    cutoff = str(cutoff).upper()
    if cutoff not in TIER_RANK:
        sys.exit(f"invalid cut-off: {cutoff}")
    print(render(data, args.lang, cutoff, args.evidence, args.bibliography))
    return 0


if __name__ == "__main__":
    sys.exit(main())

