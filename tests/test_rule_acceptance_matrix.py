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


if __name__ == "__main__":
    unittest.main()
