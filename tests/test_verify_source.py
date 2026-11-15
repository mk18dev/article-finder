"""Tests for scripts/verify_source.py: decision logic only, no network."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_source as vs


def work(**overrides) -> vs.Work:
    base = vs.Work(
        doi="10.1000/x",
        title="A paper",
        container="Journal of Tests",
        publisher="Springer Science and Business Media LLC",
        issns=["0924-1868"],
        volume="12",
        issue="4",
        pages="331-370",
        year=vs.date.today().year - 1,
        authors=["Doe, J."],
        kind="journal",
        abstract="An abstract.",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


ENTRY = {"doi": "10.1000/x", "category": "application", "tier": "B", "keyword": "Method + test"}


class PublisherTests(unittest.TestCase):
    def test_trusted_publisher_passes(self) -> None:
        self.assertTrue(vs.decide(work(), ENTRY)["steps"]["S5"] is True)

    def test_unknown_publisher_is_pending_not_failed(self) -> None:
        article = vs.decide(work(publisher="Tiny Press"), ENTRY)
        self.assertIsNone(article["steps"]["S5"])
        self.assertIn("not on the slide's list", article["notes"]["en"])

    def test_missing_publisher_is_pending(self) -> None:
        self.assertIsNone(vs.decide(work(publisher=""), ENTRY)["steps"]["S5"])


class IdentifierTests(unittest.TestCase):
    def test_valid_issn_passes(self) -> None:
        self.assertTrue(vs.decide(work(), ENTRY)["steps"]["S7"] is True)

    def test_invalid_issn_fails(self) -> None:
        self.assertIs(vs.decide(work(issns=["1234-5678"]), ENTRY)["steps"]["S7"], False)

    def test_no_issn_is_pending_for_journal(self) -> None:
        self.assertIsNone(vs.decide(work(issns=[]), ENTRY)["steps"]["S7"])

    def test_conference_needs_venue_and_doi(self) -> None:
        conference = work(kind="conference", issns=[], container="Proceedings of Tests")
        self.assertIs(vs.decide(conference, ENTRY)["steps"]["S7"], True)


class RecencyTests(unittest.TestCase):
    def test_recent_application_passes(self) -> None:
        self.assertIs(vs.decide(work(), ENTRY)["steps"]["S8"], True)

    def test_old_application_fails(self) -> None:
        old = work(year=vs.date.today().year - vs.RECENCY_YEARS - 1)
        self.assertIs(vs.decide(old, ENTRY)["steps"]["S8"], False)

    def test_old_concept_is_allowed(self) -> None:
        old = work(year=2002)
        entry = {**ENTRY, "category": "concept"}
        self.assertIs(vs.decide(old, entry)["steps"]["S8"], True)

    def test_unspecialised_source_fails(self) -> None:
        entry = {**ENTRY, "specialized": False}
        self.assertIs(vs.decide(work(), entry)["steps"]["S8"], False)


class ExtractionTests(unittest.TestCase):
    def test_abstract_enough_for_application(self) -> None:
        self.assertIs(vs.decide(work(), ENTRY)["steps"]["S11"], True)

    def test_no_abstract_is_pending(self) -> None:
        self.assertIsNone(vs.decide(work(abstract=""), ENTRY)["steps"]["S11"])

    def test_methodology_always_pending(self) -> None:
        entry = {**ENTRY, "category": "methodology"}
        article = vs.decide(work(), entry)
        self.assertIsNone(article["steps"]["S11"])
        self.assertIn("full text is required", article["notes"]["en"])


class GateTests(unittest.TestCase):
    def test_indexing_is_always_pending(self) -> None:
        self.assertIsNone(vs.decide(work(), ENTRY)["steps"]["S6"])

    def test_unknown_crossref_type_fails_source_type(self) -> None:
        self.assertIs(vs.decide(work(kind=None), ENTRY)["steps"]["S4"], False)

    def test_missing_keyword_fails_keyword_gate(self) -> None:
        entry = {**ENTRY, "keyword": ""}
        self.assertIs(vs.decide(work(), entry)["steps"]["S3"], False)

    def test_unknown_category_fails_category_gate(self) -> None:
        entry = {**ENTRY, "category": "other"}
        self.assertIs(vs.decide(work(), entry)["steps"]["S10"], False)


class UrlTests(unittest.TestCase):
    def test_doi_url(self) -> None:
        self.assertEqual(vs.decide(work(), ENTRY)["url"], "https://doi.org/10.1000/x")

    def test_checklist_links_use_issn(self) -> None:
        links = " ".join(vs.s6_links(work()))
        self.assertIn("0924-1868", links)
        self.assertIn("scimagojr", links)

    def test_conference_link_targets_dblp(self) -> None:
        links = " ".join(vs.s6_links(work(kind="conference", issns=[])))
        self.assertIn("dblp", links)


if __name__ == "__main__":
    unittest.main()


class BlacklistTests(unittest.TestCase):
    def test_checklist_starts_with_the_blacklist_link(self) -> None:
        links = vs.s6_links(work())
        self.assertIn("impactfactor.ir", links[0])

    def test_conference_still_gets_dblp_after_blacklist(self) -> None:
        links = " ".join(vs.s6_links(work(kind="conference", issns=[])))
        self.assertIn("impactfactor.ir", links)
        self.assertIn("dblp", links)

    def test_checklist_text_explains_blacklist_is_a_rejection(self) -> None:
        source = work()
        text = vs.checklist([vs.decide(source, ENTRY)], [source])
        self.assertIn("rejection at S6", text)
