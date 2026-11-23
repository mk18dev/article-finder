import unittest
from unittest.mock import patch

from scripts.verify_citations import (
    normalize_doi,
    title_similarity,
    update_status,
    verify_all,
    verify_metadata,
)


class CitationVerificationTests(unittest.TestCase):
    def setUp(self):
        self.citation = {
            "doi": "https://doi.org/10.1234/example",
            "title": "Reliable Systems for Research",
            "year": 2024,
            "first_author": "Smith",
        }
        self.message = {
            "DOI": "10.1234/EXAMPLE",
            "title": ["Reliable Systems for Research"],
            "author": [{"given": "Jane", "family": "Smith"}],
            "published-print": {"date-parts": [[2024, 3, 1]]},
            "update-to": [],
        }

    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC"), "10.1234/abc")

    def test_exact_metadata_match_is_verified(self):
        result = verify_metadata(self.citation, self.message)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["title_similarity"], 1.0)

    def test_title_mismatch_is_not_verified(self):
        message = dict(self.message, title=["Completely unrelated publication"])
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "mismatch")
        self.assertTrue(result["mismatches"])

    def test_year_mismatch_is_not_verified(self):
        message = dict(self.message, **{"published-print": {"date-parts": [[2020]]}})
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "mismatch")
        self.assertTrue(any("year mismatch" in item for item in result["mismatches"]))

    def test_retraction_takes_precedence(self):
        message = dict(self.message, **{"update-to": [{"type": "retraction", "DOI": "10.1234/retract"}]})
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "retracted")

    def test_correction_is_flagged_not_silently_verified(self):
        message = dict(self.message, **{"update-to": [{"type": "correction", "DOI": "10.1234/correction"}]})
        status, updates = update_status(message)
        self.assertEqual(status, "corrected")
        self.assertEqual(len(updates), 1)
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "corrected")
        self.assertEqual(result["updates"][0]["type"], "correction")

    @patch("scripts.verify_citations.fetch_json")
    def test_no_doi_search_returns_pending_candidates(self, fetch):
        fetch.return_value = {"message": {"items": [
            {"DOI": "10.1234/candidate", "title": ["Reliable Systems for Research"]}
        ]}}
        result = verify_all([{"title": "Reliable Systems for Research"}])[0]
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["candidates"][0]["doi"], "10.1234/candidate")

    @patch("scripts.verify_citations.fetch_json", side_effect=TimeoutError("network"))
    def test_lookup_failure_stays_pending(self, fetch):
        result = verify_all([self.citation])[0]
        self.assertEqual(result["status"], "pending")
        self.assertIn("metadata lookup failed", result["reason"])

    def test_rejects_non_doi_resolver_urls(self):
        with self.assertRaises(ValueError):
            normalize_doi("https://evil.example/10.1234/example")

    def test_full_first_author_name_matches_crossref_family(self):
        citation = dict(self.citation, first_author="Jane Smith")
        result = verify_metadata(citation, self.message)
        self.assertEqual(result["status"], "verified")

    def test_withdrawal_is_treated_as_retracted(self):
        message = dict(self.message, **{"update-to": [{"type": "withdrawal", "DOI": "10.1234/withdrawal"}]})
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "retracted")

    def test_relation_correction_is_flagged(self):
        message = dict(self.message, relation={"is-corrected-by": [{"id": "10.1234/correction"}]})
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "corrected")

    def test_missing_returned_doi_stays_pending(self):
        message = dict(self.message)
        message.pop("DOI")
        result = verify_metadata(self.citation, message)
        self.assertEqual(result["status"], "pending")

    def test_invalid_doi_is_pending_without_crashing_batch(self):
        result = verify_all([{"doi": "https://evil.example/10.1234/x", "title": "Example"}])[0]
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["doi"], "")

    def test_citation_batch_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            verify_all([{"title": f"Paper {index}"} for index in range(101)])

    def test_title_similarity_is_normalized(self):
        self.assertEqual(title_similarity("A Reliable-System", "a reliable system"), 1.0)

    def test_invalid_document_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_all({"items": []})


    def test_venue_and_publisher_are_checked(self):
        citation = dict(self.citation, venue="Journal of Reliable Systems", publisher="Example Press")
        message = dict(self.message, **{
            "container-title": ["Journal of Reliable Systems"],
            "publisher": "Example Press",
        })
        self.assertEqual(verify_metadata(citation, message)["status"], "verified")
        message["container-title"] = ["Unrelated Journal"]
        result = verify_metadata(citation, message)
        self.assertEqual(result["status"], "mismatch")
        self.assertTrue(any("venue mismatch" in item for item in result["mismatches"]))

    def test_missing_expected_year_stays_pending(self):
        citation = dict(self.citation)
        citation.pop("year")
        self.assertEqual(verify_metadata(citation, self.message)["status"], "pending")

    def test_missing_requested_publisher_metadata_stays_pending(self):
        citation = dict(self.citation, publisher="Example Press")
        self.assertEqual(verify_metadata(citation, self.message)["status"], "pending")

    def test_persian_year_and_author_normalization(self):
        citation = {
            "doi": "10.1234/example",
            "title": "سامانه‌های قابل اعتماد",
            "year": "۱۴۰۲",
            "first_author": "رضایی، علی",
        }
        message = {
            "DOI": "10.1234/example",
            "title": ["سامانه‌های قابل اعتماد"],
            "author": [{"family": "رضایی"}],
            "published-print": {"date-parts": [[1402]]},
        }
        self.assertEqual(verify_metadata(citation, message)["status"], "verified")

    @patch("scripts.verify_citations.fetch_json")
    def test_duplicate_dois_in_batch_are_flagged(self, fetch):
        fetch.return_value = {"message": self.message}
        citations = [dict(self.citation), dict(self.citation, doi="https://doi.org/10.1234/EXAMPLE")]
        results = verify_all(citations)
        self.assertTrue(all(item["duplicate_doi"] for item in results))
        self.assertTrue(all(item["status"] == "mismatch" for item in results))


    def test_correction_report_contains_notice_doi_url(self):
        message = dict(self.message, **{
            "update-to": [{"type": "correction", "DOI": "10.1234/correction"}]
        })
        status, updates = update_status(message)
        self.assertEqual(status, "corrected")
        self.assertEqual(updates[0]["url"], "https://doi.org/10.1234/correction")

    def test_metadata_result_exposes_crossref_provenance(self):
        result = verify_metadata(self.citation, self.message)
        self.assertEqual(result["metadata_provider"], "Crossref")
        self.assertEqual(
            result["metadata_record_url"],
            "https://api.crossref.org/works/10.1234/example",
        )

    def test_markdown_report_surfaces_update_and_pending_reasons(self):
        from scripts.verify_citations import render_markdown
        result = verify_metadata(self.citation, dict(self.message, **{
            "update-to": [{"type": "retraction", "DOI": "10.1234/retract"}]
        }))
        result["index"] = 1
        result["input"] = self.citation
        report = render_markdown([result])
        self.assertIn("retracted", report)
        self.assertIn("https://doi.org/10.1234/retract", report)
        self.assertIn("First author", report)


if __name__ == "__main__":
    unittest.main()
