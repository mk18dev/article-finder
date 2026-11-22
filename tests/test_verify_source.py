"""Evidence-gate regression tests; deterministic and network-free."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_source as vs


def evidence(note: str = "Checked against the source record") -> dict:
    return {"reviewed": True, "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "record section 1", "url": "https://evidence.example/source", "note": note}


def work(**overrides) -> vs.Work:
    values = dict(
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
    values.update(overrides)
    return vs.Work(**values)


ENTRY = {
    "doi": "10.1000/x",
    "category": "application",
    "tier": "B",
    "tier_evidence": {
        "verified": True,
        "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "ranking table",
        "url": "https://evidence.example/tier",
        "basis": "Ranking reviewed against the stated rubric",
    },
    "keyword": "Method + test",
    "search_evidence": {
        "query": "Method + test",
        "doi": "10.1000/x",
        "url": "https://api.crossref.org/works?query=Method%20%2B%20test",
        "searched_at": "2026-11-23T10:00:00Z",
    },
    "area": "Computer Science",
    "subject": "network anomaly detection",
    "specialized": True,
    "specialization_evidence": evidence("Journal scope matches the research area"),
    "judgements": {
        "S1": {"ok": True, **evidence("Source belongs to computing"), "evidence_url": "https://evidence.example/area"},
        "S2": {"ok": True, **evidence("Relevance directly assessed"), "evidence_url": "https://evidence.example/subject"},
        "S10": {"ok": True, **evidence("Source fits application category"), "evidence_url": "https://evidence.example/category"},
    },
    "blacklist_status": "clear",
    "blacklist_evidence": {**evidence("Iranian blacklist checked on official source"), "url": "https://impactfactor.ir/"},
    "indexing_evidence": [{
        "index": "Scopus", "verified": True,
        "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "source profile",
        "url": "https://www.scopus.com/sources.uri?zone=TopNavBar",
        "note": "Checked source entry and coverage",
    }],
    "reading_evidence": {
        "abstract": evidence("Abstract read and reviewed"),
        "introduction": evidence("Introduction read and reviewed"),
        "conclusion": evidence("Conclusion read and reviewed"),
    },
}


def decide(source: vs.Work | None = None, entry: dict | None = None) -> dict:
    return vs.decide(source or work(), ENTRY if entry is None else entry)


class PublisherTests(unittest.TestCase):
    def test_trusted_publisher_passes(self) -> None:
        self.assertIs(decide()["steps"]["S5"], True)

    def test_unknown_publisher_is_pending_not_failed(self) -> None:
        article = decide(work(publisher="Tiny Press"))
        self.assertIsNone(article["steps"]["S5"])
        self.assertIn("requires confirmation", article["notes"]["en"])

    def test_missing_publisher_is_pending(self) -> None:
        self.assertIsNone(decide(work(publisher=""))["steps"]["S5"])

    def test_untrusted_publisher_name_cannot_pass_by_substring(self) -> None:
        self.assertFalse(vs.publisher_trusted("Not Elsevier Publishing"))

    def test_trusted_publisher_legal_suffix_is_normalized(self) -> None:
        self.assertTrue(vs.publisher_trusted("Elsevier B.V."))



class SearchAndJudgementTests(unittest.TestCase):
    def test_search_evidence_allows_keyword_gate(self) -> None:
        self.assertIs(decide()["steps"]["S3"], True)

    def test_missing_search_execution_is_pending(self) -> None:
        entry = {**ENTRY}
        entry.pop("search_evidence")
        self.assertIsNone(decide(entry=entry)["steps"]["S3"])

    def test_search_doi_must_match_record(self) -> None:
        entry = {**ENTRY, "search_evidence": {**ENTRY["search_evidence"], "doi": "10.1000/other"}}
        self.assertIsNone(decide(entry=entry)["steps"]["S3"])

    def test_search_query_must_match_pair(self) -> None:
        entry = {**ENTRY, "search_evidence": {**ENTRY["search_evidence"], "query": "Different + query"}}
        self.assertIsNone(decide(entry=entry)["steps"]["S3"])

    def test_invalid_keyword_pair_fails(self) -> None:
        entry = {**ENTRY, "keyword": "not-a-course-keyword"}
        self.assertIs(decide(entry=entry)["steps"]["S3"], False)

    def test_s1_s2_s10_need_review_records(self) -> None:
        article = decide()
        for step in ("S1", "S2", "S10"):
            self.assertIs(article["steps"][step], True)

    def test_missing_judgement_is_pending_even_when_label_exists(self) -> None:
        entry = {**ENTRY, "judgements": {}}
        article = decide(entry=entry)
        self.assertIsNone(article["steps"]["S1"])
        self.assertIsNone(article["steps"]["S2"])
        self.assertIsNone(article["steps"]["S10"])


    def test_manual_evidence_requires_reviewer_identity_timestamp_and_locator(self) -> None:
        for field in ("reviewer_id", "reviewed_at", "locator"):
            with self.subTest(field=field):
                entry = {**ENTRY, "judgements": {
                    **ENTRY["judgements"],
                    "S1": {**ENTRY["judgements"]["S1"], field: ""},
                }}
                self.assertIsNone(decide(entry=entry)["steps"]["S1"])

    def test_judgement_requires_url_and_note(self) -> None:
        entry = {**ENTRY, "judgements": {
            **ENTRY["judgements"],
            "S1": {"ok": True, "reviewed": True, "evidence_url": "", "note": "Looks relevant"},
        }}
        self.assertIsNone(decide(entry=entry)["steps"]["S1"])

    def test_malformed_evidence_url_stays_pending_without_crashing(self) -> None:
        entry = {**ENTRY, "judgements": {
            **ENTRY["judgements"],
            "S1": {"ok": True, "reviewed": True, "evidence_url": "https://[", "note": "Malformed URL"},
        }}
        self.assertIsNone(decide(entry=entry)["steps"]["S1"])

    def test_non_dict_review_records_stay_pending(self) -> None:
        entry = {**ENTRY, "reading_evidence": ["not", "a", "mapping"]}
        self.assertIsNone(decide(entry=entry)["steps"]["S11"])


class IdentifierTests(unittest.TestCase):
    def test_valid_journal_issn_and_metadata_pass(self) -> None:
        self.assertIs(decide()["steps"]["S7"], True)

    def test_invalid_issn_fails(self) -> None:
        self.assertIs(decide(work(issns=["1234-5678"]))["steps"]["S7"], False)

    def test_missing_issn_is_pending(self) -> None:
        self.assertIsNone(decide(work(issns=[]))["steps"]["S7"])

    def test_journal_missing_issue_is_pending(self) -> None:
        self.assertIsNone(decide(work(issue=""))["steps"]["S7"])

    def test_conference_needs_edition_venue_and_evidence(self) -> None:
        conference = work(kind="conference", issns=[], container="Proceedings of Tests")
        self.assertIsNone(decide(conference)["steps"]["S7"])
        entry = {
            **ENTRY, "conference_edition": "12th", "conference_venue": "Berlin",
            "conference_evidence": evidence("Edition and venue verified"),
        }
        self.assertIs(decide(conference, entry)["steps"]["S7"], True)

    def test_book_needs_primary_book_and_valid_isbn(self) -> None:
        book = work(kind="book", issns=[], isbns=["9780262033848"])
        self.assertIsNone(decide(book)["steps"]["S7"])
        entry = {**ENTRY, "main_book": True, "book_evidence": evidence("Contents identify main book")}
        self.assertIs(decide(book, entry)["steps"]["S7"], True)

    def test_book_chapter_is_not_misclassified_as_book(self) -> None:
        self.assertIs(decide(work(kind="book_chapter"))["steps"]["S4"], False)

    def test_thesis_needs_repository_record_and_evidence(self) -> None:
        thesis = work(kind="thesis", issns=[], container="University")
        self.assertIsNone(decide(thesis)["steps"]["S7"])
        entry = {
            **ENTRY, "degree": "PhD", "degree_evidence": evidence("Doctoral degree confirmed in the repository"),
            "record_id": "TH-123", "institution": "Test University",
            "repository_url": "https://repository.example/thesis",
            "thesis_evidence": evidence("Institutional repository record checked"),
        }
        self.assertIs(decide(thesis, entry)["steps"]["S7"], True)

    def test_bachelors_thesis_is_rejected(self) -> None:
        thesis = work(kind="thesis", issns=[])
        self.assertIs(decide(thesis, {**ENTRY, "degree": "bachelor"})["steps"]["S4"], False)

    def test_thesis_without_degree_is_pending(self) -> None:
        self.assertIsNone(decide(work(kind="thesis", issns=[]))["steps"]["S4"])

    def test_thesis_degree_without_evidence_is_pending(self) -> None:
        thesis = work(kind="thesis", issns=[])
        entry = {**ENTRY, "degree": "PhD"}
        self.assertIsNone(decide(thesis, entry)["steps"]["S4"])


class RecencyTests(unittest.TestCase):
    def test_recent_application_passes(self) -> None:
        self.assertIs(decide()["steps"]["S8"], True)

    def test_old_application_fails(self) -> None:
        old = work(year=vs.date.today().year - vs.RECENCY_YEARS - 1)
        self.assertIs(decide(old)["steps"]["S8"], False)

    def test_old_concept_is_allowed(self) -> None:
        old = work(year=2002)
        self.assertIs(decide(old, {**ENTRY, "category": "concept"})["steps"]["S8"], True)

    def test_old_challenge_is_pending_not_automatically_passed(self) -> None:
        old = work(year=2002)
        self.assertIsNone(decide(old, {**ENTRY, "category": "challenge"})["steps"]["S8"])

    def test_future_publication_year_fails(self) -> None:
        future = work(year=vs.date.today().year + 1)
        self.assertIs(decide(future)["steps"]["S8"], False)

    def test_specialization_missing_is_pending(self) -> None:
        entry = {k: v for k, v in ENTRY.items() if k != "specialized"}
        self.assertIsNone(decide(entry=entry)["steps"]["S8"])

    def test_specialization_boolean_without_evidence_is_pending(self) -> None:
        entry = {k: v for k, v in ENTRY.items() if k != "specialization_evidence"}
        self.assertIsNone(decide(entry=entry)["steps"]["S8"])

    def test_unspecialised_source_fails(self) -> None:
        self.assertIs(decide(entry={**ENTRY, "specialized": False})["steps"]["S8"], False)


class BlacklistTests(unittest.TestCase):
    def test_verified_index_with_clear_blacklist_passes(self) -> None:
        self.assertIs(decide()["steps"]["S6"], True)

    def test_blacklist_hit_hard_rejects(self) -> None:
        self.assertIs(decide(entry={**ENTRY, "blacklist_status": "listed"})["steps"]["S6"], False)

    def test_missing_blacklist_status_is_pending(self) -> None:
        entry = {k: v for k, v in ENTRY.items() if k != "blacklist_status"}
        self.assertIsNone(decide(entry=entry)["steps"]["S6"])

    def test_clear_blacklist_without_indexing_is_pending(self) -> None:
        self.assertIsNone(decide(entry={**ENTRY, "indexing_evidence": []})["steps"]["S6"])

    def test_clear_blacklist_without_blacklist_evidence_is_pending(self) -> None:
        entry = {k: v for k, v in ENTRY.items() if k != "blacklist_evidence"}
        self.assertIsNone(decide(entry=entry)["steps"]["S6"])

    def test_legacy_http_blacklist_domain_is_allowed_only_for_s6(self) -> None:
        legacy = {
            "reviewed": True, "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "blacklist result",
            "url": "http://impactfactor.ir/",
            "note": "Checked the official blacklist record",
        }
        entry = {**ENTRY, "blacklist_evidence": legacy}
        self.assertIs(decide(entry=entry)["steps"]["S6"], True)
        self.assertIsNone(vs.judgement({
            "judgements": {"S1": {
                "ok": True, "reviewed": True, "evidence_url": "http://impactfactor.ir/",
                "note": "This is not accepted for a normal review judgement",
            }}
        }, "S1"))

    def test_invalid_index_evidence_is_pending(self) -> None:
        bad = [{"index": "Scopus", "verified": True, "url": "http://index.example", "note": "checked"}]
        self.assertIsNone(decide(entry={**ENTRY, "indexing_evidence": bad})["steps"]["S6"])


    def test_fake_index_domain_does_not_pass_s6(self) -> None:
        bad = [{"index": "Scopus", "verified": True,
                "url": "https://scopus.com.attacker.example/source",
                "note": "Looks like an index record"}]
        self.assertIsNone(decide(entry={**ENTRY, "indexing_evidence": bad})["steps"]["S6"])

    def test_fake_blacklist_domain_does_not_pass_s6(self) -> None:
        entry = {**ENTRY, "blacklist_evidence": {
            "reviewed": True, "url": "https://impactfactor.ir.attacker.example/",
            "note": "Claimed to be official blacklist evidence",
        }}
        self.assertIsNone(decide(entry=entry)["steps"]["S6"])

    def test_fake_search_domain_does_not_pass_s3(self) -> None:
        entry = {**ENTRY, "search_evidence": {
            **ENTRY["search_evidence"], "url": "https://crossref.org.attacker.example/search",
        }}
        self.assertIsNone(decide(entry=entry)["steps"]["S3"])

    def test_search_timestamp_must_include_timezone(self) -> None:
        entry = {**ENTRY, "search_evidence": {
            **ENTRY["search_evidence"], "searched_at": "2026-11-23T10:00:00",
        }}
        self.assertIsNone(decide(entry=entry)["steps"]["S3"])

    def test_checklist_starts_with_blacklist_link(self) -> None:
        self.assertIn("impactfactor.ir", vs.s6_links(work())[0])

    def test_conference_checklist_keeps_dblp_without_journal_blacklist_link(self) -> None:
        links = " ".join(vs.s6_links(work(kind="conference", issns=[])))
        self.assertIn("dblp", links)
        self.assertNotIn("impactfactor.ir", links)

    def test_checklist_explains_evidence_fields(self) -> None:
        source = work()
        content = vs.checklist([decide(source)], [source])
        self.assertIn("blacklist_status", content)
        self.assertIn("indexing_evidence", content)


class ReadingDepthTests(unittest.TestCase):
    def test_abstract_alone_does_not_pass_s11(self) -> None:
        entry = {**ENTRY, "reading_evidence": {"abstract": evidence("Abstract checked")}}
        self.assertIs(decide(entry=entry)["steps"]["S11"], None)

    def test_article_requires_abstract_intro_and_conclusion(self) -> None:
        self.assertIs(decide()["steps"]["S11"], True)

    def test_methodology_requires_full_text(self) -> None:
        entry = {**ENTRY, "category": "methodology"}
        self.assertIsNone(decide(entry=entry)["steps"]["S11"])
        entry["reading_evidence"] = {"full_text": evidence("Full text reviewed across sections")}
        self.assertIs(decide(entry=entry)["steps"]["S11"], True)

    def test_book_requires_chapters_one_and_two(self) -> None:
        book = work(kind="book", issns=[], isbns=["9780262033848"])
        entry = {**ENTRY, "category": "concept",
                 "reading_evidence": {"abstract": evidence(), "chapter_1": evidence()}}
        self.assertIsNone(decide(book, entry)["steps"]["S11"])
        entry["reading_evidence"]["chapter_2"] = evidence("Second chapter reviewed")
        self.assertIs(decide(book, entry)["steps"]["S11"], True)


class TierTests(unittest.TestCase):
    def test_tier_needs_reviewer_evidence(self) -> None:
        article = decide(entry={k: v for k, v in ENTRY.items() if k != "tier_evidence"})
        self.assertEqual(article["tier"], "")
        self.assertIs(article["tier_verified"], False)

    def test_verified_tier_is_preserved(self) -> None:
        article = decide()
        self.assertEqual(article["tier"], "B")
        self.assertIs(article["tier_verified"], True)


class UrlTests(unittest.TestCase):
    def test_doi_url(self) -> None:
        self.assertEqual(decide()["url"], "https://doi.org/10.1000/x")

    def test_checklist_links_use_issn(self) -> None:
        links = " ".join(vs.s6_links(work()))
        self.assertIn("0924-1868", links)
        self.assertIn("scimagojr", links)

    def test_conference_link_targets_dblp(self) -> None:
        links = " ".join(vs.s6_links(work(kind="conference", issns=[])))
        self.assertIn("dblp", links)



class LegacyBehaviourRegressionTests(unittest.TestCase):
    def test_unknown_crossref_type_is_rejected_at_s4(self) -> None:
        self.assertIs(decide(work(kind=None))["steps"]["S4"], False)

    def test_missing_keyword_fails_keyword_gate(self) -> None:
        entry = {**ENTRY, "keyword": ""}
        self.assertIs(decide(entry=entry)["steps"]["S3"], False)

    def test_unknown_category_fails_category_gate(self) -> None:
        entry = {**ENTRY, "category": "other"}
        self.assertIs(decide(entry=entry)["steps"]["S10"], False)

    def test_missing_reading_record_is_pending_even_with_abstract_metadata(self) -> None:
        entry = {k: v for k, v in ENTRY.items() if k != "reading_evidence"}
        self.assertIsNone(decide(entry=entry)["steps"]["S11"])

    def test_methodology_without_full_text_is_pending(self) -> None:
        article = decide(entry={**ENTRY, "category": "methodology"})
        self.assertIsNone(article["steps"]["S11"])
        self.assertIn("full text", article["notes"]["en"].lower())

    def test_checklist_mentions_blacklist_rejection(self) -> None:
        source = work()
        content = vs.checklist([decide(source)], [source])
        self.assertIn("blacklist", content.lower())



class SourceSpecificS6Tests(unittest.TestCase):
    def test_thesis_s6_requires_irandoc_or_university_repository(self) -> None:
        thesis = work(kind="thesis", issns=[])
        evidence = {
            "repository": "Irandoc", "verified": True,
            "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "record TH-123",
            "url": "https://irandoc.ac.ir/record/123",
            "note": "Institutional thesis record was inspected",
        }
        self.assertIs(decide(thesis, {**ENTRY, "thesis_repository_evidence": evidence})["steps"]["S6"], True)

    def test_thesis_s6_does_not_accept_journal_index_only(self) -> None:
        thesis = work(kind="thesis", issns=[])
        self.assertIs(decide(thesis)["steps"]["S6"], None)

    def test_book_s6_requires_citations_and_publisher_confirmation(self) -> None:
        book = work(kind="book", issns=[], isbns=["9780262033848"])
        evidence = {
            "source": "Google Books", "verified": True,
            "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "book record",
            "url": "https://books.google.com/books?id=example",
            "note": "Book record and publisher were inspected",
            "citation_count": 27, "publisher_verified": True,
        }
        self.assertIs(decide(book, {**ENTRY, "book_s6_evidence": evidence})["steps"]["S6"], True)

    def test_book_s6_is_pending_without_citation_count(self) -> None:
        book = work(kind="book", issns=[], isbns=["9780262033848"])
        evidence = {
            "source": "Google Books", "verified": True,
            "url": "https://books.google.com/books?id=example",
            "note": "Book record and publisher were inspected",
            "publisher_verified": True,
        }
        self.assertIs(decide(book, {**ENTRY, "book_s6_evidence": evidence})["steps"]["S6"], None)

    def test_book_s6_is_pending_without_publisher_confirmation(self) -> None:
        book = work(kind="book", issns=[], isbns=["9780262033848"])
        evidence = {
            "source": "Amazon", "verified": True,
            "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "product details",
            "url": "https://www.amazon.com/dp/example",
            "note": "Book record and citation count were inspected",
            "citation_count": 12, "publisher_verified": False,
        }
        self.assertIs(decide(book, {**ENTRY, "book_s6_evidence": evidence})["steps"]["S6"], None)


    def test_conference_s6_needs_indexing_but_not_journal_blacklist(self) -> None:
        conference = work(kind="conference", issns=[], container="Proceedings of Tests")
        evidence = [{
            "index": "DBLP", "verified": True,
            "reviewer_id": "reviewer-1", "reviewed_at": "2026-11-23T10:00:00Z", "locator": "proceedings record",
            "url": "https://dblp.org/db/conf/example",
            "note": "Conference proceedings record was inspected",
        }]
        self.assertIs(decide(conference, {**ENTRY, "indexing_evidence": evidence})["steps"]["S6"], True)

    def test_conference_s6_without_index_record_is_pending(self) -> None:
        conference = work(kind="conference", issns=[], container="Proceedings of Tests")
        self.assertIsNone(decide(conference, {"category": "application"})["steps"]["S6"])

    def test_thesis_s6_link_points_to_irandoc(self) -> None:
        links = " ".join(vs.s6_links(work(kind="thesis", issns=[])))
        self.assertIn("irandoc.ac.ir", links)

    def test_book_s6_links_point_to_google_books_and_amazon(self) -> None:
        links = " ".join(vs.s6_links(work(kind="book", issns=[], isbns=["9780262033848"])))
        self.assertIn("books.google.com", links)
        self.assertIn("amazon.com", links)

    def test_book_s6_rejects_boolean_as_citation_count(self) -> None:
        book = work(kind="book", issns=[], isbns=["9780262033848"])
        evidence = {
            "source": "Google Books", "verified": True,
            "url": "https://books.google.com/books?id=example",
            "note": "Book record and publisher were inspected",
            "citation_count": True, "publisher_verified": True,
        }
        self.assertIsNone(decide(book, {**ENTRY, "book_s6_evidence": evidence})["steps"]["S6"])
if __name__ == "__main__":
    unittest.main()
