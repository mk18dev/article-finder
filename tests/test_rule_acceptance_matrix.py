"""Acceptance matrix for all 76 article-draft rules.

Manual rules intentionally remain unresolved until a reviewer records a verdict.
The matrix verifies complete rule exposure, stable mapping, fail-closed defaults,
and explicit human override behavior without pretending to automate judgement.
"""
from __future__ import annotations

import unittest

from scripts import check_draft as cd


class DraftRuleAcceptanceMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        cd.LANG = "en"
        self.sections = {section: "Sample reviewer-authored content." for section in cd.SECTIONS}

    def test_exactly_76_unique_rules_are_registered(self) -> None:
        ids = [rule[0] for rule in cd.RULES]
        self.assertEqual(len(ids), 76)
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_rule_has_one_valid_section_and_source_mapping(self) -> None:
        self.assertEqual(set(cd.RULE_STEP), {rule[0] for rule in cd.RULES})
        for rule_id, section, kind, fn, _en, _fa in cd.RULES:
            with self.subTest(rule=rule_id):
                self.assertIn(section, cd.SECTIONS)
                self.assertIn(rule_id, cd.RULE_STEP)
                self.assertIn(cd.RULE_STEP[rule_id], cd.SECTION_STEPS[section])
                if kind == "manual":
                    self.assertIsNone(fn)
                else:
                    self.assertIn(kind, {"auto", "hint"})
                    self.assertTrue(callable(fn))

    def test_all_76_rules_are_emitted_once(self) -> None:
        rows = cd.evaluate(self.sections, {})
        self.assertEqual(len(rows), 76)
        self.assertEqual([row[0] for row in rows], [rule[0] for rule in cd.RULES])
        for row in rows:
            self.assertIn(row[2], {True, False, None})
            self.assertIsInstance(row[3], str)

    def test_missing_sections_fail_closed_for_every_rule(self) -> None:
        rows = cd.evaluate({}, {})
        self.assertEqual(len(rows), 76)
        self.assertTrue(all(row[2] is False for row in rows))
        self.assertTrue(all("section missing" in row[3] for row in rows))

    def test_every_manual_rule_requires_a_human_verdict(self) -> None:
        manual_rules = [rule for rule in cd.RULES if rule[2] == "manual"]
        self.assertTrue(manual_rules)
        for rule_id, _section, _kind, _fn, _en, _fa in manual_rules:
            with self.subTest(rule=rule_id):
                row = next(item for item in cd.evaluate(self.sections, {}) if item[0] == rule_id)
                self.assertIsNone(row[2])
                accepted = next(
                    item for item in cd.evaluate(self.sections, {rule_id: (True, "reviewed")})
                    if item[0] == rule_id
                )
                rejected = next(
                    item for item in cd.evaluate(self.sections, {rule_id: (False, "reviewed")})
                    if item[0] == rule_id
                )
                self.assertIs(accepted[2], True)
                self.assertIs(rejected[2], False)
                self.assertIn("reviewed", accepted[3])
                self.assertIn("reviewed", rejected[3])

    def test_every_hint_rule_stays_unapproved_without_manual_confirmation(self) -> None:
        hint_rules = [rule for rule in cd.RULES if rule[2] == "hint"]
        self.assertTrue(hint_rules)
        for rule_id, _section, _kind, _fn, _en, _fa in hint_rules:
            with self.subTest(rule=rule_id):
                row = next(item for item in cd.evaluate(self.sections, {}) if item[0] == rule_id)
                self.assertIsNone(row[2])
                accepted = next(
                    item for item in cd.evaluate(self.sections, {rule_id: (True, "human checked")})
                    if item[0] == rule_id
                )
                self.assertIs(accepted[2], True)
                self.assertIn("human checked", accepted[3])

    def test_every_automatic_and_hint_function_obeys_the_result_contract(self) -> None:
        for rule_id, section, kind, fn, _en, _fa in cd.RULES:
            if kind == "manual":
                continue
            with self.subTest(rule=rule_id):
                result = fn(self.sections[section], self.sections)
                self.assertIsInstance(result, tuple)
                self.assertEqual(len(result), 2)
                self.assertIn(result[0], {True, False, None})
                self.assertIsInstance(result[1], str)

    def test_non_boolean_manual_values_never_become_approval(self) -> None:
        for rule_id, _section, kind, _fn, _en, _fa in cd.RULES:
            if kind not in {"manual", "hint"}:
                continue
            with self.subTest(rule=rule_id):
                row = next(
                    item for item in cd.evaluate(self.sections, {rule_id: ("yes", "invalid")})
                    if item[0] == rule_id
                )
                self.assertIsNone(row[2])

    @staticmethod
    def _words(count: int) -> str:
        return " ".join(["word"] * count)

    @staticmethod
    def _tables(count: int) -> str:
        table = "| column |\\n|---|\\n| value |"
        return "\\n\\n".join([table] * count)

    def test_each_automatic_rule_has_positive_negative_and_boundary_cases(self) -> None:
        cases = {
            "T1": (self._words(8), self._words(7), self._words(15)),
            "T5": ("Research title", "Research title.", "Research title。"),
            "A1": (self._words(200), self._words(199), self._words(250)),
            "A10": ("One paragraph.", "First paragraph.\\n\\nSecond paragraph.", "First line.\\nSecond line."),
            "A11": ("Plain abstract text.", "(Smith, 2024)", "شکل 1"),
            "K1": ("a,b,c,d,e,f", "a,b,c,d,e", "a,b,c,d,e,f,g,h"),
            "K3": ("Data Mining, AI", "data mining, ai", "هوش مصنوعی"),
            "F1": ("Department of Computing", "", "   "),
            "F2": ("دانشگاه آزاد Islamic Azad", "Islamic Azad", "دانشگاه ۱۲۳"),
            "I1": (self._words(500), self._words(499), self._words(700)),
            "B1": (self._words(1000), self._words(999), self._words(1500)),
            "B7": ("Models are effective.", "Models and methods.", "Candy is sweet."),
            "M1": (self._words(500), self._words(499), self._words(1000)),
            "M8": ("The population is described in prose.", "- adults\\n- students", "1) adults\\n2) students"),
            "R1": (self._words(1000), self._words(999), self._words(1500)),
            "R4": (self._tables(1), "No table is included.", "Table 1 is mentioned but not rendered."),
            "R5": (self._tables(3), self._tables(2), self._tables(5)),
            "R6": ("![one](one.png)", "No figure.", "![one](one.png)\\n\\n![two](two.png)"),
            "C1": (self._words(1000), self._words(999), self._words(1500)),
            "C2": ("A concise conclusion.", "| value |\\n|---|\\n| 1 |", "(Smith, 2024)"),
            "X1": ("Smith, J. (2024). A paper.", "", "   "),
        }
        automatic_ids = {rule[0] for rule in cd.RULES if rule[2] == "auto"}
        self.assertEqual(set(cases), automatic_ids)
        rule_map = {rule[0]: rule for rule in cd.RULES}
        for rule_id, (positive, negative, boundary) in cases.items():
            _rid, section, _kind, fn, _en, _fa = rule_map[rule_id]
            with self.subTest(rule=rule_id, case="positive"):
                self.assertIs(fn(positive, self.sections)[0], True)
            with self.subTest(rule=rule_id, case="negative"):
                self.assertIs(fn(negative, self.sections)[0], False)
            with self.subTest(rule=rule_id, case="boundary"):
                self.assertIsInstance(fn(boundary, self.sections)[0], bool)

    def test_hint_rules_produce_reviewable_details_without_auto_approval(self) -> None:
        from datetime import date

        current_year = date.today().year
        hint_cases = {
            "I14": (f"Recent work from {current_year}.", "Older work from 1999."),
            "B6": ("Short. Clear.", "This is a deliberately long sentence that should be surfaced by the sentence-length hint."),
            "M5": ("No citations here.", "Prior work supports this method (Smith, 2024)."),
            "R7": ("No table or figure labels.", "Table 1 and Figure 2 are discussed."),
            "R8": ("No table or figure labels.", "Table 1 and Figure 2 are discussed."),
            "R9": ("No chart image or label.", "Chart 1\\n\\n![plot](chart.png)"),
        }
        hint_ids = {rule[0] for rule in cd.RULES if rule[2] == "hint"}
        self.assertEqual(set(hint_cases), hint_ids)
        rule_map = {rule[0]: rule for rule in cd.RULES}
        for rule_id, (baseline, signal) in hint_cases.items():
            _rid, section, _kind, fn, _en, _fa = rule_map[rule_id]
            with self.subTest(rule=rule_id, case="baseline"):
                result, detail = fn(baseline, self.sections)
                self.assertIsNone(result)
                self.assertIsInstance(detail, str)
            with self.subTest(rule=rule_id, case="signal"):
                result, detail = fn(signal, self.sections)
                self.assertIsNone(result)
                self.assertIsInstance(detail, str)
                self.assertNotEqual(detail, fn(baseline, self.sections)[1])

    def test_hint_rules_accept_both_explicit_human_verdicts(self) -> None:
        for rule_id, _section, kind, _fn, _en, _fa in cd.RULES:
            if kind != "hint":
                continue
            with self.subTest(rule=rule_id):
                for verdict in (True, False):
                    row = next(
                        item for item in cd.evaluate(self.sections, {rule_id: (verdict, "human checked")})
                        if item[0] == rule_id
                    )
                    self.assertIs(row[2], verdict)
                    self.assertIn("human checked", row[3])


if __name__ == "__main__":
    unittest.main()
