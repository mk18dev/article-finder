#!/usr/bin/env python3
"""Check an article draft against the Chapter 2 rules and print a checklist table.

Usage:
    python3 check_draft.py draft.md [--lang fa|en] [--manual manual.json] [--json]

The draft is a text/markdown file whose sections start with a heading line:
Title, Abstract, Keywords, Affiliation, Introduction, Research Background,
Methodology, Findings, Conclusion, References (Persian headings such as
عنوان، چکیده، کلیدواژه‌ها، مقدمه، پیشینه پژوهش، روش‌شناسی، یافته‌ها،
نتیجه‌گیری، منابع also work). "Keywords: a, b, c" on one line also works.

Rules marked auto are decided here. Rules marked manual (or hint) need a
reader's judgment: pass a JSON file mapping rule IDs to a verdict, e.g.
    {"T2": true, "A3": {"ok": false, "note": "first sentence is 41 words"}}
Without a verdict a manual rule shows ❓. Rule IDs and slide wording:
references/writing-article.md (section 11).

--lang also localizes the detail column and the numbers, so a Persian table
carries no English text.

Exit code 0 always; the table is the result. A section is approved only
when every one of its rules is ✅.
"""
import argparse
import datetime
import json
import re
import sys
from typing import Any, Callable, Iterable

ZW = "\u200c"
LANG = "en"
Row = tuple[str, str, bool | None, str, str, str]
Step = Callable[[str, dict[str, str]], tuple[bool | None, str]]
Rule = tuple[str, str, str, Step | None, str, str]
SECTIONS: list[str] = ["title", "abstract", "keywords", "affiliation", "introduction",
            "background", "methodology", "findings", "conclusion", "references"]

NAMES: dict[str, dict[str, str]] = {
    "en": {"title": "Title", "abstract": "Abstract", "keywords": "Keywords",
           "affiliation": "Affiliation", "introduction": "Introduction",
           "background": "Research Background", "methodology": "Methodology",
           "findings": "Findings", "conclusion": "Conclusion",
           "references": "References"},
    "fa": {"title": "عنوان", "abstract": "چکیده", "keywords": "کلیدواژه‌ها",
           "affiliation": "وابستگی سازمانی", "introduction": "مقدمه",
           "background": "پیشینه پژوهش", "methodology": "روش‌شناسی",
           "findings": "یافته‌ها", "conclusion": "نتیجه‌گیری",
           "references": "منابع"},
}

ALIASES: dict[str, list[str]] = {
    "title": ["title", "عنوان", "عنوان مقاله"],
    "abstract": ["abstract", "چکیده"],
    "keywords": ["keywords", "keyword", "key words", "کلیدواژه", "کلیدواژه ها",
                 "کلید واژه", "کلید واژه ها", "کلمات کلیدی", "واژگان کلیدی"],
    "affiliation": ["affiliation", "affiliations", "وابستگی سازمانی",
                    "نشانی سازمانی", "مشخصات نویسنده"],
    "introduction": ["introduction", "مقدمه"],
    "background": ["research background", "background", "literature review",
                   "پیشینه پژوهش", "پیشینه تحقیق", "پیشینه", "مرور ادبیات"],
    "methodology": ["methodology", "method", "methods", "روش شناسی",
                    "روش پژوهش", "روش تحقیق", "روش"],
    "findings": ["findings", "results", "یافته ها", "یافته", "نتایج"],
    "conclusion": ["conclusion", "conclusions", "نتیجه گیری", "نتیجه"],
    "references": ["references", "منابع", "مراجع"],
}

RANGES: dict[str, tuple[int, int]] = {"title": (8, 15), "abstract": (200, 250), "keywords": (6, 8),
          "introduction": (500, 700), "background": (1000, 1500),
          "methodology": (500, 1000), "findings": (1000, 1500),
          "conclusion": (1000, 1500)}

DIGITS: dict[int, int] = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
FA_DIGITS: dict[int, int] = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def T(en: str, fa: str) -> str:
    return fa if LANG == "fa" else en


def N(value: object) -> str:
    text = str(value)
    return text.translate(FA_DIGITS) if LANG == "fa" else text


def LST(items: Iterable[str]) -> str:
    if not items:
        return T("none", "هیچ")
    return "[" + ", ".join(N(i) for i in items) + "]"


def norm(s: str) -> str:
    s = s.replace(ZW, " ").lower()
    s = re.sub(r"[*_`#:.\-–—]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ALIAS_MAP: dict[str, str] = {norm(a): k for k, v in ALIASES.items() for a in v}


def heading(line: str) -> tuple[str | None, str]:
    """Return (section, inline_text) if the line is a section heading."""
    stripped = re.sub(r"^\s*(?:#{1,6}\s*)?(?:\d+\s*[.)]\s*)?", "", line)
    n = norm(stripped)
    if n in ALIAS_MAP:
        return ALIAS_MAP[n], ""
    m = re.match(r"^\s*(?:\*\*)?([^:：]{2,30}?)(?:\*\*)?\s*[:：]\s*(\S.*)$", stripped)
    if m and norm(m.group(1)) in ALIAS_MAP:
        return ALIAS_MAP[norm(m.group(1))], m.group(2).strip()
    return None, ""


def parse(text: str) -> dict[str, str]:
    buckets, present, cur, fallback = {}, [], None, None
    for ln in text.splitlines():
        key, inline = heading(ln)
        if key:
            cur = key
            if key not in buckets:
                buckets[key] = []
                present.append(key)
            if inline:
                buckets[key].append(inline)
            continue
        if cur is None:
            if fallback is None and ln.strip().startswith("#"):
                fallback = ln.strip().lstrip("#").strip()
            continue
        buckets[cur].append(ln)
    out = {k: "\n".join(v).strip() for k, v in buckets.items()}
    if "title" not in out and fallback:
        out["title"] = fallback
    return out


def prose(text: str) -> str:
    keep = []
    in_code = False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or ln.strip().startswith("|") or re.match(r"^\s*!\[", ln):
            continue
        keep.append(re.sub(r"[*_`#>]", " ", ln))
    return "\n".join(keep)


def count_words(text: str) -> int:
    return sum(1 for t in prose(text).split() if any(c.isalnum() for c in t))


def sentences(text: str) -> list[str]:
    flat = prose(text).replace("\n", " ")
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+", flat) if s.strip()]


def keyword_items(text: str) -> list[str]:
    parts = re.split(r"[,،;؛\n•·|]+", text)
    out = []
    for p in parts:
        p = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", p).strip()
        if p:
            out.append(p)
    return out


CITE_YEAR = r"(?:(?:19|20)[0-9]{2}|1[34][0-9]{2})"
CITE = re.compile(
    r"\[\s*[0-9]+(?:\s*[-–,،]\s*[0-9]+)*\s*\]"
    rf"|\([^()]*?(?<![0-9]){CITE_YEAR}[a-z]?(?![0-9])\)"
)
LABEL: dict[str, re.Pattern[str]] = {
    "table": re.compile(r"(?:\bTable|جدول)\s*([0-9۰-۹]+)", re.I),
    "figure": re.compile(r"(?:\bFigure|\bFig\.?|شکل)\s*([0-9۰-۹]+)", re.I),
    "chart": re.compile(r"(?:\bChart|نمودار)\s*([0-9۰-۹]+)", re.I),
}
SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")


def labels(kind: str, text: str) -> set[str]:
    return {m.translate(DIGITS) for m in LABEL[kind].findall(text)}


def counts(text: str) -> dict[str, Any]:
    md_tables = sum(1 for ln in text.splitlines() if "|" in ln and SEP.match(ln))
    images = len(re.findall(r"!\[", text))
    return {"tables": md_tables, "figures": images,
            "table_labels": labels("table", text),
            "figure_labels": labels("figure", text),
            "chart_labels": labels("chart", text)}


EXTRAS = [("table", re.compile(r"^\s*\|"), "table row", "سطر جدول"),
          ("image", re.compile(r"!\["), "image", "تصویر"),
          ("table", None, "table mention", "اشاره به جدول"),
          ("figure", None, "figure mention", "اشاره به شکل"),
          ("chart", None, "chart mention", "اشاره به نمودار"),
          ("cite", None, "in-text reference", "ارجاع درون‌متنی")]


# ---- auto rules: fn(text, ctx) -> (True|False|None, detail) -----------------

def r_words(sec: str) -> Step:
    lo, hi = RANGES[sec]

    def f(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
        if sec == "keywords":
            n = len(keyword_items(t))
            return lo <= n <= hi, T(f"{n} terms (slide: {lo}-{hi})",
                                    f"{N(n)} کلیدواژه (اسلاید: {N(lo)} تا {N(hi)})")
        n = count_words(t)
        return lo <= n <= hi, T(f"{n} words (slide: {lo}-{hi})",
                                f"{N(n)} کلمه (اسلاید: {N(lo)} تا {N(hi)})")
    return f


def r_no_period(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    ok = not t.strip().endswith((".", "。"))
    return ok, T("ends with a period" if not ok else "no period at the end",
                 "در انتها نقطه دارد" if not ok else "در انتها نقطه ندارد")


def r_single_paragraph(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    ok = not re.search(r"\n\s*\n", t.strip())
    return ok, T("one paragraph" if ok else "blank line(s) split it into several paragraphs",
                 "یک پاراگراف" if ok else "خط خالی آن را به چند پاراگراف شکسته")


def r_no_extras(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    found = []
    if any(ln.strip().startswith("|") or SEP.match(ln) for ln in t.splitlines() if "|" in ln):
        found.append(T("table row", "سطر جدول"))
    if "![" in t:
        found.append(T("image", "تصویر"))
    for kind, _, en, fa in EXTRAS[2:5]:
        if labels(kind, t):
            found.append(T(en, fa))
    if CITE.search(t.translate(DIGITS)):
        found.append(T("in-text reference", "ارجاع درون‌متنی"))
    return not found, (T("found: ", "یافت شد: ") + T(", ", "، ").join(found)) if found else T("none found", "چیزی یافت نشد")


def r_keywords_caps(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    bad = [k for k in keyword_items(t) if re.search(r"[A-Za-z]", k) and
           not re.match(r"^[^A-Za-z]*[A-Z]", k)]
    if not bad:
        return True, T("all capitalized", "همه با حرف بزرگ شروع می‌شوند")
    return False, T("not capitalized: " + "; ".join(bad[:5]),
                    "با حرف کوچک: " + "؛ ".join(bad[:5]))


def r_present(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    ok = bool(t.strip())
    return ok, T("present" if ok else "empty", "موجود است" if ok else "خالی است")


def r_both_scripts(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    fa = bool(re.search(r"[\u0600-\u06FF]", t))
    en = bool(re.search(r"[A-Za-z]", t))
    return fa and en, T(f"Persian: {'yes' if fa else 'no'}, English: {'yes' if en else 'no'}",
                        f"فارسی: {'بله' if fa else 'خیر'}، انگلیسی: {'بله' if en else 'خیر'}")


def r_no_and(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    bad = [s for s in sentences(t) if re.search(r"(?<!\w)(?:and|و)(?!\w)", s, re.I)]
    if not bad:
        return True, T("no sentence contains the word and / و", "هیچ جمله‌ای «و» ندارد")
    ex = bad[0][:70] + ("…" if len(bad[0]) > 70 else "")
    return False, T(f"{len(bad)} sentence(s) contain and / و, e.g. “{ex}”",
                    f"{N(len(bad))} جمله «و» دارد، مثلاً «{ex}»")


def r_no_list(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    lines = [ln for ln in t.splitlines() if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", ln)]
    if not lines:
        return True, T("no list lines", "فهرست‌وار نیست")
    return False, T(f"{len(lines)} list line(s) found in this section (slide wants the population described as a paragraph)",
                    f"{N(len(lines))} خط فهرستی در این بخش (اسلاید پاراگراف می‌خواهد)")


def r_tables_used(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    n = counts(t)["tables"]
    return n >= 1, T(f"{n} table(s)", f"{N(n)} جدول")


def r_tables_range(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    n = counts(t)["tables"]
    return 3 <= n <= 5, T(f"{n} table(s) (slide: 3-5)", f"{N(n)} جدول (اسلاید: ۳ تا ۵)")


def r_figures_range(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    c = counts(t)
    n, lab = c["figures"], len(c["figure_labels"])
    if n == 0 and lab:
        return False, T(f"0 images, {lab} figure label(s) only: a mention is not a figure",
                        f"هیچ تصویری نیست، فقط {N(lab)} بار «شکل» نام برده شده؛ اشاره شکل نیست")
    return 1 <= n <= 2, T(f"{n} figure(s) (slide: 1-2)", f"{N(n)} شکل (اسلاید: ۱ تا ۲)")


def r_charts(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    """A chart label is not proof that a chart exists; require human review."""
    summary = counts(t)
    labels_found = sorted(summary["chart_labels"])
    figures = summary["figures"]
    if labels_found and figures:
        detail = T(
            f"{len(labels_found)} chart label(s) and {figures} image(s) found; inspect whether an image is actually a chart",
            f"{N(len(labels_found))} برچسب نمودار و {N(figures)} تصویر یافت شد؛ بررسی کن که تصویر واقعاً نمودار باشد",
        )
    elif labels_found:
        detail = T(
            f"{len(labels_found)} chart label(s) found but no image; a mention is not a chart",
            f"{N(len(labels_found))} برچسب نمودار پیدا شد اما تصویری نیست؛ صرف اشاره نمودار نیست",
        )
    elif figures:
        detail = T(
            f"{figures} image(s) found; judge whether any figure is a chart",
            f"{N(figures)} تصویر پیدا شد؛ خودت بررسی کن کدام‌یک نمودار است",
        )
    else:
        detail = T("no chart image or label found; inspect the rendered findings section",
                   "نه تصویر و نه برچسب نمودار پیدا شد؛ بخش یافته‌های نهایی را بررسی کن")
    return None, detail


# ---- hints: return (None, detail) -------------------------------------------

def h_short_sentences(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    ss = sentences(t)
    if not ss:
        return None, T("no sentences found", "جمله‌ای یافت نشد")
    lens = [len(s.split()) for s in ss]
    avg, longest = sum(lens) / len(lens), max(lens)
    return None, T(f"{len(ss)} sentences, average {avg:.0f} words, longest {longest}",
                   f"{N(len(ss))} جمله، میانگین {N(f'{avg:.0f}')} کلمه، بلندترین {N(longest)}")


def h_citations(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    n = len(CITE.findall(t.translate(DIGITS)))
    return None, T(f"{n} in-text reference(s) detected", f"{N(n)} ارجاع درون‌متنی شناسایی شد")


def h_recent_years(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    this = datetime.date.today().year
    txt = t.translate(DIGITS)
    greg = sorted({int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", txt)})
    solar = sorted({int(y) for y in re.findall(r"\b1[34]\d{2}\b", txt)})
    lo, hi = this - 5, this
    recent = [y for y in greg if lo <= y <= hi] + [y for y in solar if lo - 621 <= y <= hi - 621]
    return None, T(f"years mentioned: {greg + solar or 'none'}; within the last 5 years ({lo}-{hi}): {recent or 'none'}",
                   f"سال‌های ذکرشده: {LST(greg + solar)}؛ در ۵ سال اخیر ({N(lo)}-{N(hi)}): {LST(recent)}")


def h_table_labels(t: str, ctx: dict[str, str]) -> tuple[bool | None, str]:
    c = counts(t)
    return None, T(f"table labels {sorted(c['table_labels']) or 'none'}, figures {sorted(c['figure_labels']) or 'none'}",
                   f"برچسب جدول {LST(sorted(c['table_labels']))}، برچسب شکل {LST(sorted(c['figure_labels']))}")


# ---- rule table: (id, section, kind, fn, English, Persian) ------------------

def M(i: str, s: str, en: str, fa: str) -> Rule:
    return (i, s, "manual", None, en, fa)


RULES: list[Rule] = [
    ("T1", "title", "auto", r_words("title"), "8-15 words", "۸ تا ۱۵ کلمه"),
    M("T2", "title", "Grabs the reader's attention", "توجه خواننده را جلب می‌کند"),
    M("T3", "title", "Clearly states the main topic", "موضوع اصلی پژوهش را روشن بیان می‌کند"),
    M("T4", "title", "As specific as possible; shows scope (research design + statistical population + geographic area)", "تا حد ممکن دقیق است و دامنه را نشان می‌دهد (طرح پژوهش + جامعه آماری + حوزه جغرافیایی)"),
    ("T5", "title", "auto", r_no_period, "No period at the end", "در انتها نقطه ندارد"),
    M("T6", "title", "Written after the article was completed", "پس از تکمیل مقاله نوشته شده است"),

    ("A1", "abstract", "auto", r_words("abstract"), "200-250 words", "۲۰۰ تا ۲۵۰ کلمه"),
    M("A2", "abstract", "Grabs the reader's attention", "توجه خواننده را جلب می‌کند"),
    M("A3", "abstract", "Begins with a short sentence", "با یک جمله‌ی کوتاه شروع می‌شود"),
    M("A4", "abstract", "Shows the main purpose", "هدف اصلی پژوهش را نشان می‌دهد"),
    M("A5", "abstract", "Shows scientific or practical importance", "اهمیت علمی یا کاربردی را نشان می‌دهد"),
    M("A6", "abstract", "Briefly shows the methodology", "روش‌شناسی را به‌اختصار نشان می‌دهد"),
    M("A7", "abstract", "Summarizes the findings", "یافته‌ها را خلاصه می‌کند"),
    M("A8", "abstract", "Briefly states the challenges", "چالش‌ها را به‌اختصار بیان می‌کند"),
    M("A9", "abstract", "Highlights practical or theoretical implications", "پیامدهای عملی یا نظری را برجسته می‌کند"),
    ("A10", "abstract", "auto", r_single_paragraph, "Single paragraph", "در یک پاراگراف است"),
    ("A11", "abstract", "auto", r_no_extras, "No tables, figures, diagrams, in-text references", "جدول، شکل، نمودار و ارجاع درون‌متنی ندارد"),
    M("A12", "abstract", "Written after the article was completed", "پس از تکمیل مقاله نوشته شده است"),

    ("K1", "keywords", "auto", r_words("keywords"), "6-8 keywords", "۶ تا ۸ کلیدواژه"),
    M("K2", "keywords", "Work as traffic lights that attract attention", "مثل چراغ راهنما توجه خواننده را جلب می‌کنند"),
    ("K3", "keywords", "auto", r_keywords_caps, "English keywords start with a capital letter", "حرف اول کلیدواژه‌های انگلیسی بزرگ است"),

    ("F1", "affiliation", "auto", r_present, "Affiliation present", "وابستگی سازمانی آمده است"),
    ("F2", "affiliation", "auto", r_both_scripts, "Persian and English versions (as in the slide example)", "نسخه‌ی فارسی و انگلیسی (مطابق نمونه‌ی اسلاید)"),

    ("I1", "introduction", "auto", r_words("introduction"), "500-700 words", "۵۰۰ تا ۷۰۰ کلمه"),
    M("I2", "introduction", "States the general topic of the research", "موضوع کلی پژوهش را بیان می‌کند"),
    M("I3", "introduction", "Answers: what is the benefit of reading this article?", "فایده‌ی خواندن مقاله را پاسخ می‌دهد"),
    M("I4", "introduction", "Names the most important related previous studies", "مهم‌ترین پژوهش‌های پیشین مرتبط را نام می‌برد"),
    M("I5", "introduction", "Main problem and question stated (short problem statement or main research question)", "مسئله و پرسش اصلی بیان شده (بیانیه‌ی کوتاه مسئله یا پرسش اصلی)"),
    M("I6", "introduction", "Specific objectives clearly stated, from most general to most specific", "اهداف اختصاصی روشن و از کلی به اختصاصی آمده‌اند"),
    M("I7", "introduction", "Background in which the research was conducted is stated", "زمینه‌ی انجام پژوهش بیان شده است"),
    M("I8", "introduction", "Unit of analysis clearly stated", "واحد تحلیل روشن بیان شده است"),
    M("I9", "introduction", "Challenge and solution to the problem clearly stated", "چالش مسئله و راه‌حل آن روشن بیان شده است"),
    M("I10", "introduction", "Ends with a general outline of the other parts", "در پایان طرح کلی بخش‌های دیگر را می‌دهد"),
    M("I11", "introduction", "Opening paragraph in simple, non-technical language", "پاراگراف آغازین ساده و غیرفنی است"),
    M("I12", "introduction", "Guides the reader step by step to the formal problem statement", "خواننده را گام‌به‌گام به بیان رسمی مسئله می‌رساند"),
    M("I13", "introduction", "Attractive opening sentence", "جمله‌ی آغازین جذاب است"),
    ("I14", "introduction", "hint", h_recent_years, "Summarizes research of the last three to five years", "پژوهش‌های سه تا پنج سال اخیر را خلاصه می‌کند"),
    M("I15", "introduction", "Recent research is directly related to the problem", "پژوهش‌های اخیر مستقیماً به مسئله مربوط‌اند"),

    ("B1", "background", "auto", r_words("background"), "1000-1500 words", "۱۰۰۰ تا ۱۵۰۰ کلمه"),
    M("B2", "background", "Reviews what other researchers have done on the topic", "کار پژوهشگران دیگر را مرور می‌کند"),
    M("B3", "background", "Not just a summary: critically evaluates, reorganizes, synthesizes", "فقط خلاصه نیست؛ نقد، بازسازماندهی و ترکیب می‌کند"),
    M("B4", "background", "Discovers inconsistencies and contradictions that form the basis of the research", "ناسازگاری‌ها و تناقض‌ها را که مبنای پژوهش‌اند کشف می‌کند"),
    M("B5", "background", "Explains the material from beginning to end", "مطلب را از ابتدا تا انتها توضیح می‌دهد"),
    ("B6", "background", "hint", h_short_sentences, "Sentences are kept short", "جمله‌ها کوتاه‌اند"),
    ("B7", "background", "auto", r_no_and, "No sentence contains the word “and” (و)", "جمله‌ای با کلمه‌ی «and» (و) نیست"),
    M("B8", "background", "“Reviewing a poorly written article” (slide wording)", "«Reviewing a poorly written article» (عبارت اسلاید)"),
    M("B9", "background", "Other people have read the article", "دیگران مقاله را خوانده‌اند"),

    ("M1", "methodology", "auto", r_words("methodology"), "500-1000 words", "۵۰۰ تا ۱۰۰۰ کلمه"),
    M("M2", "methodology", "Explains the research steps", "مراحل پژوهش را توضیح می‌دهد"),
    M("M3", "methodology", "Justifies the steps of the research method", "مراحل روش پژوهش را توجیه می‌کند"),
    M("M4", "methodology", "Explains the appropriateness of the chosen method", "مناسب‌بودن روش انتخابی را توضیح می‌دهد"),
    ("M5", "methodology", "hint", h_citations, "Names articles to justify the choice", "برای توجیه انتخاب، مقاله‌ها را نام می‌برد"),
    M("M6", "methodology", "Statistical population fully described", "جامعه‌ی آماری کامل توصیف شده است"),
    M("M7", "methodology", "All statistical populations are stated (if several)", "همه‌ی جامعه‌های آماری ذکر شده‌اند"),
    ("M8", "methodology", "auto", r_no_list, "Population described as a regular paragraph, not a list", "جامعه‌ی آماری به‌صورت پاراگراف توصیف شده نه فهرست"),
    M("M9", "methodology", "Data collection tool introduced (questionnaire, interview, library)", "ابزار گردآوری داده معرفی شده (پرسشنامه، مصاحبه، کتابخانه‌ای)"),
    M("M10", "methodology", "Time of data collection stated", "زمان گردآوری داده‌ها ذکر شده است"),
    M("M11", "methodology", "Measured variables listed", "متغیرهای اندازه‌گیری‌شده فهرست شده‌اند"),

    ("R1", "findings", "auto", r_words("findings"), "1000-1500 words", "۱۰۰۰ تا ۱۵۰۰ کلمه"),
    M("R2", "findings", "Research findings are discussed", "یافته‌ها بحث شده‌اند"),
    M("R3", "findings", "Results presented with full explanations", "نتایج با توضیح کامل آمده‌اند"),
    ("R4", "findings", "auto", r_tables_used, "Tables are used to display the findings", "یافته‌ها با جدول نمایش داده شده‌اند"),
    ("R5", "findings", "auto", r_tables_range, "Three to five tables", "۳ تا ۵ جدول"),
    ("R6", "findings", "auto", r_figures_range, "One to two figures", "۱ تا ۲ شکل"),
    ("R7", "findings", "hint", h_table_labels, "Table and figure information is summarized and explained in the text", "اطلاعات جدول‌ها و شکل‌ها در متن خلاصه و توضیح داده شده"),
    ("R8", "findings", "hint", h_table_labels, "Clear references to tables and figures appear before them", "ارجاع روشن به جدول‌ها و شکل‌ها پیش از آن‌ها آمده است"),
    ("R9", "findings", "hint", r_charts, "Charts are used as well", "از نمودار هم استفاده شده است"),

    ("C1", "conclusion", "auto", r_words("conclusion"), "1000-1500 words", "۱۰۰۰ تا ۱۵۰۰ کلمه"),
    ("C2", "conclusion", "auto", r_no_extras, "No figures, tables, or in-text references", "شکل، جدول و ارجاع درون‌متنی ندارد"),
    M("C3", "conclusion", "States the main objective of the article", "هدف اصلی مقاله را بیان می‌کند"),
    M("C4", "conclusion", "States the significance of the research", "اهمیت پژوهش را بیان می‌کند"),
    M("C5", "conclusion", "States the relevant results", "نتایج مرتبط را بیان می‌کند"),
    M("C6", "conclusion", "States the findings", "یافته‌ها را بیان می‌کند"),
    M("C7", "conclusion", "Main limitation of the study fully stated", "محدودیت اصلی پژوهش کامل بیان شده است"),

    ("X1", "references", "auto", r_present, "Reference list present", "فهرست منابع وجود دارد"),
    M("X2", "references", "Managed with Word or Endnote", "با Word یا Endnote مدیریت شده است"),
]

SECTION_STEPS: dict[str, list[tuple[int, int]]] = {
    "title": [(34, 41), (35, 42)],
    "abstract": [(36, 43), (37, 44)],
    "keywords": [(38, 45)],
    "affiliation": [(39, 46)],
    "introduction": [(40, 47), (41, 48), (42, 49), (43, 50)],
    "background": [(44, 51), (45, 52)],
    "methodology": [(46, 53), (47, 54), (48, 55)],
    "findings": [(49, 56), (50, 57)],
    "conclusion": [(51, 58), (52, 59)],
    "references": [(53, 60)],
}

RULE_STEP: dict[str, tuple[int, int]] = {
    **dict.fromkeys(("T1", "T2", "T3", "T4", "T5", "T6"), (34, 41)),
    **dict.fromkeys(("A1", "A2", "A3", "A4", "A5", "A6"), (36, 43)),
    **dict.fromkeys(("A7", "A8", "A9", "A10", "A11", "A12"), (37, 44)),
    **dict.fromkeys(("K1", "K2", "K3"), (38, 45)),
    **dict.fromkeys(("F1", "F2"), (39, 46)),
    **dict.fromkeys(("I1", "I2", "I3", "I4"), (40, 47)),
    **dict.fromkeys(("I5", "I6", "I7", "I8", "I9", "I10"), (41, 48)),
    **dict.fromkeys(("I11", "I12", "I13", "I14"), (42, 49)),
    **dict.fromkeys(("I15",), (43, 50)),
    **dict.fromkeys(("B1", "B2", "B3", "B4", "B5"), (44, 51)),
    **dict.fromkeys(("B6", "B7", "B8", "B9"), (45, 52)),
    **dict.fromkeys(("M1", "M2", "M3", "M4", "M5"), (46, 53)),
    **dict.fromkeys(("M6", "M7"), (47, 54)),
    **dict.fromkeys(("M8", "M9", "M10", "M11"), (48, 55)),
    **dict.fromkeys(("R1", "R2", "R3", "R4", "R5"), (49, 56)),
    **dict.fromkeys(("R6", "R7", "R8", "R9"), (50, 57)),
    **dict.fromkeys(("C1", "C2"), (51, 58)),
    **dict.fromkeys(("C3", "C4", "C5", "C6", "C7"), (52, 59)),
    **dict.fromkeys(("X1", "X2"), (53, 60)),
}

MARK: dict[bool | None, str] = {True: "✅", False: "❌", None: "❓"}
HEAD: dict[str, tuple[str, ...]] = {
    "en": ("ID", "Rule", "Result", "Detail", "Section", "Rules", "Verdict",
           "approved", "needs work", "Summary", "sections approved", "Step"),
    "fa": ("شناسه", "قاعده", "نتیجه", "توضیح", "بخش", "قاعده‌ها", "وضعیت",
           "تأییدشده", "نیازمند اصلاح", "خلاصه", "بخش تأییدشده", "قدم"),
}


def step_cell(rule_id: str) -> str:
    step, page = RULE_STEP[rule_id]
    return T(f"{step} (p{page})", f"{N(step)} (ص {N(page)})")


def section_steps(sec: str) -> str:
    pairs = SECTION_STEPS.get(sec, [])
    if not pairs:
        return ""
    steps = ", ".join(N(step) for step, _ in pairs)
    pages = ", ".join(N(page) for _, page in pairs)
    return T(f" · steps {steps} (pages {pages})", f" · قدم {steps} (ص {pages})")


def esc(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def load_manual(path: str | None) -> dict[str, tuple[bool | None, str]]:
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            out[k] = (v.get("ok"), v.get("note", ""))
        else:
            out[k] = (v, "")
    return out


def evaluate(secs: dict[str, str], manual: dict[str, tuple[bool | None, str]]) -> list[Row]:
    results = []
    for rid, sec, kind, fn, en, fa in RULES:
        if sec not in secs:
            results.append((rid, sec, False, T("section missing from the draft",
                                               "این بخش در پیش‌نویس نیست"), en, fa))
            continue
        res, detail = (None, T("needs a reader's judgment", "نیازمند قضاوت خواننده"))
        if fn:
            res, detail = fn(secs[sec], secs)
        if kind in ("manual", "hint") and rid in manual:
            ok, note = manual[rid]
            res = ok if isinstance(ok, bool) else None
            recorded = note or T("verdict recorded", "قضاوت ثبت شد")
            detail = (detail + T("; ", "؛ ") if kind == "hint" else "") + recorded
        results.append((rid, sec, res, detail, en, fa))
    return results


def render(results: list[Row], lang: str) -> str:
    H = HEAD[lang]
    out = []
    summary = []
    for sec in SECTIONS:
        rows = [r for r in results if r[1] == sec]
        n_ok = sum(1 for r in rows if r[2] is True)
        n_bad = sum(1 for r in rows if r[2] is False)
        n_unk = sum(1 for r in rows if r[2] is None)
        verdict = "✅" if n_ok == len(rows) else ("❌" if n_bad else "❓")
        summary.append((sec, len(rows), n_ok, n_bad, n_unk, verdict))
        out.append(f"### {NAMES[lang][sec]} {verdict} ({N(n_ok)}/{N(len(rows))}){section_steps(sec)}\n")
        out.append(f"| {H[0]} | {H[1]} | {H[2]} | {H[3]} | {H[11]} |")
        out.append("|---|---|---|---|---|")
        for rid, _, res, detail, en, fa in rows:
            out.append(f"| {rid} | {esc(en if lang == 'en' else fa)} | {MARK[res]} | {esc(detail)} | {step_cell(rid)} |")
        out.append("")
    out.append(f"### {H[9]}\n")
    out.append(f"| {H[4]} | {H[5]} | ✅ | ❌ | ❓ | {H[6]} |")
    out.append("|---|---|---|---|---|---|")
    for sec, n, ok, bad, unk, v in summary:
        out.append(f"| {NAMES[lang][sec]} | {N(n)} | {N(ok)} | {N(bad)} | {N(unk)} | {v} |")
    done = sum(1 for s in summary if s[5] == "✅")
    out.append(f"\n**{N(done)}/{N(len(SECTIONS))} {H[10]}**")
    return "\n".join(out)


def main() -> int:
    global LANG
    p = argparse.ArgumentParser(description="Check an article draft against the Chapter 2 rules.")
    p.add_argument("draft")
    p.add_argument("--lang", choices=["fa", "en"], default="en")
    p.add_argument("--manual", help="JSON file with verdicts for manual rules")
    p.add_argument("--json", action="store_true", help="print results as JSON")
    a = p.parse_args()
    LANG = a.lang
    with open(a.draft, encoding="utf-8") as f:
        secs = parse(f.read())
    results = evaluate(secs, load_manual(a.manual))
    if a.json:
        print(json.dumps([{"id": r[0], "section": r[1], "ok": r[2], "detail": r[3],
                           "step": RULE_STEP[r[0]][0], "page": RULE_STEP[r[0]][1]} for r in results],
                         ensure_ascii=False, indent=2))
    else:
        print(render(results, a.lang))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

