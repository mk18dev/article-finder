import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from tier_policy import compute_tier


class TierPolicyTests(unittest.TestCase):
    def compute(self, **overrides):
        values = {
            "source_kind": "journal",
            "publisher_recognized": True,
            "specialized": True,
            "indexing_evidence": [{"index": "Scopus"}],
            "quartile": "Q3",
            "quartile_source": "SJR",
            "source_record_verified": True,
            "identifier_verified": True,
        }
        values.update(overrides)
        return compute_tier(**values)

    def test_journal_q1_computes_a(self):
        self.assertEqual(self.compute(quartile="Q1")[0], "A")

    def test_journal_q2_jcr_computes_a(self):
        self.assertEqual(self.compute(quartile="Q2", quartile_source="JCR")[0], "A")

    def test_journal_q3_computes_b(self):
        self.assertEqual(self.compute(quartile="Q3")[0], "B")

    def test_journal_q4_computes_b(self):
        self.assertEqual(self.compute(quartile="Q4")[0], "B")

    def test_wos_scie_q1_computes_a(self):
        self.assertEqual(self.compute(
            indexing_evidence=[{"index": "Web of Science", "coverage": "SCIE"}],
            quartile="Q1",
        )[0], "A")

    def test_wos_esci_computes_b(self):
        self.assertEqual(self.compute(
            indexing_evidence=[{"index": "Web of Science", "coverage": "ESCI"}],
            quartile=None, quartile_source=None,
        )[0], "B")

    def test_wos_without_coverage_is_pending(self):
        self.assertIsNone(self.compute(
            indexing_evidence=[{"index": "Web of Science"}],
            quartile="Q1",
        )[0])

    def test_esci_computes_b_without_quartile(self):
        self.assertEqual(self.compute(
            indexing_evidence=[{"index": "ESCI"}],
            quartile=None, quartile_source=None,
        )[0], "B")

    def test_only_isc_computes_c(self):
        self.assertEqual(self.compute(
            indexing_evidence=[{"index": "ISC"}],
            quartile=None, quartile_source=None,
        )[0], "C")

    def test_only_dblp_or_doaj_computes_c(self):
        self.assertEqual(self.compute(
            indexing_evidence=[{"index": "DBLP"}, {"index": "DOAJ"}],
            quartile=None, quartile_source=None,
        )[0], "C")

    def test_off_specialization_computes_c(self):
        self.assertEqual(self.compute(specialized=False)[0], "C")

    def test_non_boolean_specialization_never_approves_a_tier(self):
        for value in ("false", "true", 0, 1, [], {}):
            with self.subTest(value=value):
                self.assertIsNone(self.compute(specialized=value)[0])

    def test_non_boolean_blacklist_signal_fails_closed(self):
        self.assertIsNone(self.compute(blacklisted="false")[0])

    def test_non_boolean_conference_review_signal_fails_closed(self):
        self.assertIsNone(self.compute(
            source_kind="conference",
            conference_scope="international",
            conference_series_established="true",
            publisher_recognized=True,
            source_record_verified=True,
            identifier_verified=True,
        )[0])

    def test_malformed_indexing_evidence_fails_closed(self):
        self.assertIsNone(self.compute(indexing_evidence=[None])[0])
        self.assertIsNone(self.compute(indexing_evidence={"index": "Scopus"})[0])

    def test_verified_blacklist_hit_overrides_q1_and_computes_d(self):
        self.assertEqual(self.compute(blacklisted=True, quartile="Q1")[0], "D")

    def test_explicit_not_indexed_computes_d(self):
        self.assertEqual(self.compute(indexing_status="not_indexed")[0], "D")

    def test_missing_index_evidence_is_pending(self):
        self.assertIsNone(self.compute(indexing_evidence=[])[0])

    def test_missing_quartile_is_pending_for_scopus(self):
        self.assertIsNone(self.compute(quartile=None)[0])

    def test_missing_quartile_source_is_pending_for_scopus(self):
        self.assertIsNone(self.compute(quartile_source=None)[0])

    def test_unrecognized_publisher_keeps_top_journal_tier_pending(self):
        self.assertIsNone(self.compute(publisher_recognized=False)[0])

    def test_conference_international_established_specialized_is_a(self):
        self.assertEqual(self.compute(
            source_kind="conference",
            conference_scope="international",
            conference_series_established=True,
            publisher_recognized=True,
            source_record_verified=True,
            identifier_verified=True,
        )[0], "A")

    def test_conference_international_new_series_is_b(self):
        self.assertEqual(self.compute(
            source_kind="conference",
            conference_scope="international",
            conference_series_established=False,
            publisher_recognized=True,
            source_record_verified=True,
            identifier_verified=True,
        )[0], "B")

    def test_conference_international_off_specialization_is_b(self):
        self.assertEqual(self.compute(
            source_kind="conference",
            conference_scope="international",
            conference_series_established=True,
            specialized=False,
            publisher_recognized=True,
            source_record_verified=True,
            identifier_verified=True,
        )[0], "B")

    def test_national_conference_with_proceedings_is_c(self):
        self.assertEqual(self.compute(
            source_kind="conference",
            conference_scope="national",
            publisher_recognized=False,
            source_record_verified=True,
            identifier_verified=True,
        )[0], "C")

    def test_unverifiable_conference_proceedings_is_d(self):
        self.assertEqual(self.compute(
            source_kind="conference",
            conference_scope="international",
            source_record_verified=False,
            identifier_verified=True,
        )[0], "D")

    def test_unrecognized_international_conference_publisher_is_d(self):
        self.assertEqual(self.compute(
            source_kind="conference",
            conference_scope="international",
            publisher_recognized=False,
            source_record_verified=True,
            identifier_verified=True,
        )[0], "D")

    def test_conference_missing_scope_is_pending(self):
        self.assertIsNone(self.compute(
            source_kind="conference",
            conference_scope=None,
            source_record_verified=True,
            identifier_verified=True,
        )[0])

    def test_phd_with_reputable_university_and_ab_derived_paper_is_a(self):
        self.assertEqual(self.compute(
            source_kind="thesis",
            degree="PhD",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status="found",
            derived_papers=[{"tier": "A"}],
            university_reputable=True,
        )[0], "A")

    def test_phd_without_derived_papers_is_b(self):
        self.assertEqual(self.compute(
            source_kind="thesis",
            degree="PhD",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status="none",
            derived_papers=[],
        )[0], "B")

    def test_phd_without_reputable_university_does_not_get_a(self):
        self.assertEqual(self.compute(
            source_kind="thesis",
            degree="PhD",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status="found",
            derived_papers=[{"tier": "A"}],
            university_reputable=False,
        )[0], "B")

    def test_masters_with_derived_paper_is_c(self):
        self.assertEqual(self.compute(
            source_kind="thesis",
            degree="Masters",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status="found",
            derived_papers=[{"tier": "B"}],
        )[0], "C")

    def test_masters_without_derived_paper_is_d(self):
        self.assertEqual(self.compute(
            source_kind="thesis",
            degree="Masters",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status="none",
        )[0], "D")

    def test_bachelors_thesis_is_d(self):
        self.assertEqual(self.compute(
            source_kind="thesis",
            degree="Bachelors",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status="none",
        )[0], "D")

    def test_thesis_without_reviewed_derived_paper_search_is_pending(self):
        self.assertIsNone(self.compute(
            source_kind="thesis",
            degree="PhD",
            degree_evidence_verified=True,
            repository_verified=True,
            derived_papers_status=None,
        )[0])

    def test_book_with_high_citations_and_relevant_chapters_is_a(self):
        self.assertEqual(self.compute(
            source_kind="book",
            publisher_recognized=True,
            main_book=True,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=100,
            relevant_chapters=True,
        )[0], "A")

    def test_book_with_modest_citations_is_b(self):
        self.assertEqual(self.compute(
            source_kind="book",
            publisher_recognized=True,
            main_book=True,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=15,
            relevant_chapters=False,
        )[0], "B")

    def test_book_from_lesser_known_verified_publisher_is_c(self):
        self.assertEqual(self.compute(
            source_kind="book",
            publisher_recognized=False,
            main_book=True,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=30,
            relevant_chapters=True,
        )[0], "C")

    def test_book_below_modest_citation_threshold_is_c(self):
        self.assertEqual(self.compute(
            source_kind="book",
            publisher_recognized=True,
            main_book=True,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=5,
            relevant_chapters=False,
        )[0], "C")

    def test_non_primary_book_is_d(self):
        self.assertEqual(self.compute(
            source_kind="book",
            main_book=False,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=100,
        )[0], "D")

    def test_invalid_isbn_is_d(self):
        self.assertEqual(self.compute(
            source_kind="book",
            main_book=True,
            identifier_verified=False,
            publisher_verified=True,
            citation_count=100,
        )[0], "D")

    def test_unverified_book_publisher_is_d(self):
        self.assertEqual(self.compute(
            source_kind="book",
            main_book=True,
            identifier_verified=True,
            publisher_verified=False,
            citation_count=100,
        )[0], "D")

    def test_book_missing_citation_count_is_pending(self):
        self.assertIsNone(self.compute(
            source_kind="book",
            main_book=True,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=None,
        )[0])

    def test_book_citation_thresholds_are_configurable(self):
        policy = {"book_citations": {"high_min": 200, "modest_min": 25}}
        self.assertEqual(self.compute(
            source_kind="book",
            publisher_recognized=True,
            main_book=True,
            identifier_verified=True,
            publisher_verified=True,
            citation_count=100,
            relevant_chapters=True,
            policy=policy,
        )[0], "B")


if __name__ == "__main__":
    unittest.main()
