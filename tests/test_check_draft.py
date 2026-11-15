"""Regression tests for scripts/check_draft.py. Run: python -m unittest discover tests"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_draft as cd


def run(draft: str, lang: str = "en", manual: dict | None = None) -> list[tuple]:
    cd.LANG = lang
    sections = cd.parse(draft)
    return cd.evaluate(sections, manual or {})


def rule(draft: str, rule_id: str, lang: str = "en", manual: dict | None = None) -> tuple:
    for row in run(draft, lang, manual):
        if row[0] == rule_id:
            return row[2], row[3]
    raise AssertionError(f"rule {rule_id} not produced")


def table(draft: str, lang: str = "en", manual: dict | None = None) -> str:
    cd.LANG = lang
    return cd.render(run(draft, lang, manual), lang)


def load_manual_text(payload: str) -> dict:
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    with handle as stream:
        stream.write(payload)
    try:
        return cd.load_manual(handle.name)
    finally:
        Path(handle.name).unlink()


DRAFT = """# عنوان آزمایشی یک مقاله

## چکیده

یافته‌های پیشین نشان داده است که مدل ترکیبی بهتر عمل می‌کند (۱۴۰۲). این جمله دوم است.

## یافته‌ها

مقایسه مدل‌ها در جدول 1 آمده است.

## نتیجه‌گیری

نتایج با پژوهش‌های قبلی هم‌راستاست (Smith، ۱۴۰۲).
"""

WITH_TABLE = """## یافته‌ها

| مدل | دقت |
|---|---|
| الف | 91 |
| ب | 88 |
"""


class ParseTests(unittest.TestCase):
    def test_persian_headings(self) -> None:
        sections = cd.parse(DRAFT)
        self.assertIn("abstract", sections)
        self.assertIn("findings", sections)
        self.assertIn("conclusion", sections)

    def test_english_headings(self) -> None:
        sections = cd.parse("## Abstract\n\ntext\n\n## Findings\n\ntext\n")
        self.assertEqual(sorted(sections), ["abstract", "findings"])

    def test_keywords_on_one_line(self) -> None:
        sections = cd.parse("## کلیدواژه‌ها: الف، ب، C\n")
        self.assertEqual(cd.keyword_items(sections["keywords"]), ["الف", "ب", "C"])

    def test_heading_alias_with_colon(self) -> None:
        sections = cd.parse("Research Background: some text\n")
        self.assertIn("background", sections)


class CitationTests(unittest.TestCase):
    def test_persian_year_detected(self) -> None:
        self.assertTrue(cd.CITE.search("پیشین (۱۴۰۲)".translate(cd.DIGITS)))

    def test_persian_author_year_detected(self) -> None:
        self.assertTrue(cd.CITE.search("(Smith، ۱۴۰۲)".translate(cd.DIGITS)))

    def test_latin_year_detected(self) -> None:
        self.assertTrue(cd.CITE.search("(2023)"))

    def test_bracketed_number_detected(self) -> None:
        self.assertTrue(cd.CITE.search("[۱،۲]".translate(cd.DIGITS)))

    def test_plain_four_digit_number_ignored(self) -> None:
        self.assertFalse(cd.CITE.search("(1234)"))

    def test_abstract_with_persian_citation_fails(self) -> None:
        ok, detail = rule(DRAFT, "A11", "fa")
        self.assertIs(ok, False)
        self.assertIn("ارجاع", detail)

    def test_conclusion_with_persian_citation_fails(self) -> None:
        ok, _ = rule(DRAFT, "C2", "fa")
        self.assertIs(ok, False)


class CountingTests(unittest.TestCase):
    def test_table_mention_is_not_a_table(self) -> None:
        ok, detail = rule(DRAFT, "R4", "fa")
        self.assertIs(ok, False)
        self.assertIn("۰ جدول", detail)

    def test_real_table_is_counted(self) -> None:
        ok, detail = rule(WITH_TABLE, "R4", "en")
        self.assertIs(ok, True)
        self.assertIn("1 table", detail)

    def test_three_to_five_tables(self) -> None:
        one = rule(WITH_TABLE, "R5", "en")
        self.assertIs(one[0], False)
        self.assertIn("slide: 3-5", one[1])

    def test_figure_label_is_not_a_figure(self) -> None:
        ok, detail = rule("## یافته‌ها\n\nشکل 1 روند را نشان می‌دهد.\n", "R6", "fa")
        self.assertIs(ok, False)
        self.assertIn("اشاره شکل نیست", detail)

    def test_image_counts_as_figure(self) -> None:
        ok, _ = rule("## Findings\n\n![fig](a.png)\n", "R6", "en")
        self.assertIs(ok, True)

    def test_keyword_count(self) -> None:
        ok, _ = rule("## Keywords: A, B, C, D, E, F, G, H, I\n", "K1", "en")
        self.assertIs(ok, False)

    def test_no_and_rule(self) -> None:
        ok, detail = rule("## پیشینه پژوهش\n\nاین روش دقیق و سریع است.\n", "B7", "fa")
        self.assertIs(ok, False)
        self.assertIn("«و»", detail)

    def test_population_list_rejected(self) -> None:
        ok, _ = rule("## Methodology\n\n- one\n- two\n", "M8", "en")
        self.assertIs(ok, False)


class LocalisationTests(unittest.TestCase):
    def test_persian_detail_has_no_latin(self) -> None:
        output = table(DRAFT, "fa")
        offenders = [
            line for line in output.splitlines()
            if re.match(r"^\| [A-Z]\d+ \|", line) and re.search(r"\| (?:✅|❌|❓) \| .*[A-Za-z]", line)
        ]
        self.assertEqual(offenders, [])

    def test_persian_digits_in_numbers(self) -> None:
        _, detail = rule("## Title\n\nshort\n", "T1", "fa")
        self.assertIn("۱ کلمه", detail)

    def test_english_detail_unchanged(self) -> None:
        ok, detail = rule("## Title\n\nshort\n", "T1", "en")
        self.assertIs(ok, False)
        self.assertEqual(detail, "1 words (slide: 8-15)")

    def test_manual_override_applies(self) -> None:
        manual = load_manual_text('{"T3": {"ok": false, "note": "موضوع روشن نیست"}}')
        ok, detail = rule(DRAFT, "T3", "fa", manual)
        self.assertIs(ok, False)
        self.assertIn("موضوع روشن نیست", detail)

    def test_manual_true_is_recorded(self) -> None:
        manual = load_manual_text('{"T3": true}')
        ok, detail = rule(DRAFT, "T3", "fa", manual)
        self.assertIs(ok, True)
        self.assertIn("قضاوت ثبت شد", detail)

    def test_missing_section_is_failed(self) -> None:
        ok, detail = rule("## عنوان\n\nx\n", "A1", "en")
        self.assertIs(ok, False)
        self.assertIn("section missing", detail)

    def test_section_verdict_and_summary(self) -> None:
        output = table(DRAFT, "fa")
        self.assertIn("### چکیده", output)
        self.assertIn("بخش تأییدشده", output)


if __name__ == "__main__":
    unittest.main()

class StepMapTests(unittest.TestCase):
    def test_every_rule_has_a_step(self) -> None:
        missing = [r[0] for r in cd.RULES if r[0] not in cd.RULE_STEP]
        self.assertEqual(missing, [])

    def test_step_map_covers_exactly_the_rules(self) -> None:
        self.assertEqual(len(cd.RULE_STEP), len(cd.RULES))
        self.assertEqual(len(cd.RULE_STEP), 76)

    def test_known_anchors(self) -> None:
        self.assertEqual(cd.RULE_STEP["T1"], (34, 41))
        self.assertEqual(cd.RULE_STEP["A11"], (37, 44))
        self.assertEqual(cd.RULE_STEP["B7"], (45, 52))
        self.assertEqual(cd.RULE_STEP["R4"], (49, 56))
        self.assertEqual(cd.RULE_STEP["C2"], (51, 58))
        self.assertEqual(cd.RULE_STEP["X2"], (53, 60))

    def test_every_section_has_steps(self) -> None:
        missing = [s for s in cd.SECTIONS if s not in cd.SECTION_STEPS]
        self.assertEqual(missing, [])

    def test_step_follows_the_slide_of_its_section(self) -> None:
        for rule_id, (step, page) in cd.RULE_STEP.items():
            section = next(r[1] for r in cd.RULES if r[0] == rule_id)
            self.assertIn((step, page), cd.SECTION_STEPS[section])

    def test_persian_step_cell_has_no_latin(self) -> None:
        cd.LANG = "fa"
        for rule_id in cd.RULE_STEP:
            self.assertIsNone(re.search(r"[A-Za-z]", cd.step_cell(rule_id)))

    def test_table_has_a_step_column(self) -> None:
        self.assertIn("| قدم |", table(DRAFT, "fa"))
        self.assertIn("| Step |", table(DRAFT, "en"))

    def test_section_heading_names_its_steps(self) -> None:
        self.assertIn("قدم ۳۴", table(DRAFT, "fa"))
