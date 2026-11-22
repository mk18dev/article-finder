"""Regression tests for scripts/render_table.py. Run: python -m unittest discover tests"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import render_table as rt


def article(**overrides) -> dict:
    base = {
        "title": "A paper",
        "authors": ["Burke, R."],
        "year": 2024,
        "type": "journal",
        "venue": "Some Journal, 1(2), 1-9",
        "url": "https://example.org/a",
        "doi": "10.1000/a",
        "category": "concept",
        "tier": "A",
        "tier_verified": True,
        "integrity_status": "not_flagged",
        "steps": {f"S{i}": True for i in range(1, 12) if i != 9},
    }
    base.update(overrides)
    return base


class VerdictTests(unittest.TestCase):
    def test_all_true_is_approved(self) -> None:
        steps, verdict = rt.evaluate(article(), "B")
        self.assertEqual(verdict, "APPROVED")
        self.assertIs(steps["S9"], True)

    def test_null_is_pending(self) -> None:
        broken = article(steps={**article()["steps"], "S6": None})
        self.assertEqual(rt.evaluate(broken, "B")[1], "PENDING")

    def test_false_is_rejected(self) -> None:
        broken = article(steps={**article()["steps"], "S4": False})
        self.assertEqual(rt.evaluate(broken, "B")[1], "REJECTED")


    def test_retracted_source_is_rejected_even_when_all_eleven_gates_pass(self) -> None:
        steps, verdict = rt.evaluate(article(integrity_status="retracted"), "B")
        self.assertIs(steps["S0"], False)
        self.assertEqual(verdict, "REJECTED")
        self.assertEqual(rt.first_step(steps, False), "integrity")

    def test_corrected_source_remains_pending_for_human_review(self) -> None:
        steps, verdict = rt.evaluate(article(integrity_status="corrected"), "B")
        self.assertIsNone(steps["S0"])
        self.assertEqual(verdict, "PENDING")
        self.assertEqual(rt.first_step(steps, None), "integrity")


    def test_paratext_source_is_pending_for_eligibility_review(self) -> None:
        steps, verdict = rt.evaluate(article(integrity_status="paratext"), "B")
        self.assertIsNone(steps["S0"])
        self.assertEqual(verdict, "PENDING")

    def test_missing_integrity_status_fails_closed(self) -> None:
        item = article()
        item.pop("integrity_status")
        steps, verdict = rt.evaluate(item, "B")
        self.assertIsNone(steps["S0"])
        self.assertEqual(verdict, "PENDING")

    def test_false_beats_null(self) -> None:
        broken = article(steps={**article()["steps"], "S4": False, "S6": None})
        self.assertEqual(rt.evaluate(broken, "B")[1], "REJECTED")

    def test_tier_below_cutoff_fails_s9(self) -> None:
        weak = article(tier="C")
        steps, verdict = rt.evaluate(weak, "B")
        self.assertIs(steps["S9"], False)
        self.assertEqual(verdict, "REJECTED")

    def test_tier_at_cutoff_passes_s9(self) -> None:
        weak = article(tier="C")
        self.assertIs(rt.evaluate(weak, "C")[0]["S9"], True)

    def test_given_s9_is_ignored(self) -> None:
        steps = {**article()["steps"], "S9": False}
        self.assertIs(rt.evaluate(article(steps=steps), "B")[0]["S9"], True)

    def test_unknown_tier_leaves_s9_unknown(self) -> None:
        steps, verdict = rt.evaluate(article(tier=""), "B")
        self.assertIsNone(steps["S9"])
        self.assertEqual(verdict, "PENDING")


class DedupeTests(unittest.TestCase):
    def test_same_doi_merged(self) -> None:
        first = article()
        second = article(url="https://other.example/x", steps={"S6": True})
        merged, count = rt.dedupe([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(count, 1)

    def test_missing_steps_filled_from_duplicate(self) -> None:
        first = article(steps={"S1": True, "S6": None})
        second = article(steps={"S6": True, "S7": True})
        merged, _ = rt.dedupe([first, second])
        self.assertIs(merged[0]["steps"]["S6"], True)
        self.assertIs(merged[0]["steps"]["S7"], True)
        self.assertIs(merged[0]["steps"]["S1"], True)

    def test_different_doi_kept(self) -> None:
        merged, count = rt.dedupe([article(), article(doi="10.1000/b")])
        self.assertEqual((len(merged), count), (2, 0))


class BibliographyTests(unittest.TestCase):
    def test_apa_entry(self) -> None:
        out = rt.bibliography([article()], "apa", "en")
        self.assertIn("Burke, R. (2024).", out)
        self.assertIn("https://doi.org/10.1000/a", out)

    def test_ieee_entry(self) -> None:
        out = rt.bibliography([article()], "ieee", "en")
        self.assertIn('R. Burke, \u201cA paper,\u201d', out)
        self.assertIn("[1]", out)

    def test_two_authors_apa(self) -> None:
        out = rt.bibliography([article(authors=["Cano, E.", "Morisio, M."])], "apa", "en")
        self.assertIn("Cano, E., & Morisio, M.", out)

    def test_rejected_source_excluded(self) -> None:
        bad = article(doi="10.1000/bad", steps={**article()["steps"], "S4": False})
        out = rt.bibliography([bad], "apa", "en")
        self.assertNotIn("10.1000/bad", out)

    def test_pending_source_flagged(self) -> None:
        half = article(steps={**article()["steps"], "S6": None})
        out = rt.bibliography([half], "apa", "en")
        self.assertIn("still pending", out)


class RenderTests(unittest.TestCase):
    def test_tables_and_summary(self) -> None:
        out = rt.render({"articles": [article()]}, "fa", "B", True, None)
        self.assertIn("منابع تأییدشده", out)
        self.assertIn("1 تأییدشده", out)

    def test_pending_row_names_first_unknown_step(self) -> None:
        half = article(steps={**article()["steps"], "S6": None})
        out = rt.render([half], "en", "B", False, None)
        self.assertIn("6 Indexing ❓", out)

    def test_rejected_row_names_first_failed_step(self) -> None:
        bad = article(steps={**article()["steps"], "S5": False})
        out = rt.render([bad], "en", "B", False, None)
        self.assertIn("5 Publisher/venue ❌", out)

    def test_duplicate_count_reported(self) -> None:
        out = rt.render([article(), article()], "en", "B", False, None)
        self.assertIn("1 duplicates merged", out)

    def test_evidence_block_only_when_approved(self) -> None:
        half = article(steps={**article()["steps"], "S6": None})
        self.assertNotIn("#### Evidence", rt.render([half], "en", "B", True, None))




class EvidenceConflictTests(unittest.TestCase):
    def test_conflicting_step_evidence_is_not_auto_merged(self) -> None:
        first = article()
        second = article(steps={**article()["steps"], "S6": False})
        merged, count = rt.dedupe([first, second])
        self.assertEqual(count, 1)
        self.assertIsNone(merged[0]["steps"]["S6"])
        self.assertTrue(merged[0]["evidence_conflicts"])
        self.assertEqual(rt.evaluate(merged[0], "B")[1], "PENDING")

    def test_conflicting_metadata_invalidates_related_gate(self) -> None:
        first = article()
        second = article(year=2020)
        merged, _ = rt.dedupe([first, second])
        self.assertIsNone(merged[0]["steps"]["S8"])
        self.assertEqual(rt.evaluate(merged[0], "B")[1], "PENDING")

    def test_tier_requires_review_evidence(self) -> None:
        unverified = article(tier_verified=False)
        self.assertIsNone(rt.evaluate(unverified, "B")[0]["S9"])
        self.assertEqual(rt.evaluate(unverified, "B")[1], "PENDING")

    def test_conflicts_are_visible_in_rendered_notes(self) -> None:
        first = article()
        second = article(steps={**article()["steps"], "S6": False})
        output = rt.render([first, second], "en", "B", False, None)
        self.assertIn("contradictory values", output)


if __name__ == "__main__":
    unittest.main()
