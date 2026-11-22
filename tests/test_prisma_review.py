import unittest

from scripts.prisma_review import (
    deduplicate_records,
    derive_counts,
    normalize_doi,
    normalize_title,
    render_prisma_flow,
    validate_review,
)


def valid_review():
    return {
        "protocol": {
            "review_type": "systematic",
            "question": "Does intervention X improve outcome Y?",
            "inclusion_criteria": ["Peer-reviewed studies", "Population matches protocol"],
            "exclusion_criteria": ["Editorials", "Wrong population"],
            "registration": {"registry": "OSF", "id": "osf-example"},
        },
        "search_log": [
            {
                "database": "Crossref",
                "platform": "REST API",
                "query": '"intervention X" AND "outcome Y"',
                "date_run": "2026-11-23",
                "hits": 10,
                "limits": "2018-2026; English",
            }
        ],
        "counts": {
            "duplicates_removed": 2,
            "records_removed_automation": 0,
            "records_excluded_title_abstract": 3,
            "reports_not_retrieved": 1,
            "full_text_exclusions": {"wrong study design": 2},
        },
        "records": [
            {"record_id": "a", "title": "Included paper", "stage": "full_text", "decision": "include"},
            {"record_id": "b", "title": "Excluded paper", "stage": "full_text", "decision": "exclude",
             "exclusion_reason": "wrong study design"},
        ],
    }


class PrismaReviewTests(unittest.TestCase):
    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC"), "10.1234/abc")
        self.assertEqual(normalize_doi("doi: 10.1234/ABC"), "10.1234/abc")

    def test_title_normalization(self):
        self.assertEqual(normalize_title("A Study: Recommender-Systems!"), "a study recommender systems")

    def test_deduplicate_by_doi_and_preserve_canonical(self):
        records = [
            {"record_id": "first", "title": "Paper A", "doi": "10.1234/ABC"},
            {"record_id": "second", "title": "Different title", "doi": "https://doi.org/10.1234/abc"},
            {"record_id": "third", "title": "Unique Paper"},
        ]
        unique, duplicates = deduplicate_records(records)
        self.assertEqual([item["record_id"] for item in unique], ["first", "third"])
        self.assertEqual(duplicates[0]["duplicate_of"], "first")
        self.assertEqual(duplicates[0]["key_type"], "doi")

    def test_deduplicate_by_normalized_title_as_last_resort(self):
        unique, duplicates = deduplicate_records([
            {"record_id": "a", "title": "A Study on AI"},
            {"record_id": "b", "title": "a-study on AI!"},
        ])
        self.assertEqual(len(unique), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["key_type"], "title")

    def test_protocol_requires_reproducible_search_log(self):
        review = valid_review()
        review["search_log"][0]["query"] = ""
        self.assertTrue(any("search_log[1].query" in error for error in validate_review(review)))

    def test_search_date_must_be_iso_date(self):
        review = valid_review()
        review["search_log"][0]["date_run"] = "23/11/2026"
        self.assertTrue(any("YYYY-MM-DD" in error for error in validate_review(review)))

    def test_counts_reconcile(self):
        counts = derive_counts(valid_review())
        self.assertEqual(counts["records_identified"], 10)
        self.assertEqual(counts["records_screened"], 8)
        self.assertEqual(counts["reports_sought"], 5)
        self.assertEqual(counts["reports_assessed"], 4)
        self.assertEqual(counts["studies_included"], 2)

    def test_negative_downstream_count_is_rejected(self):
        review = valid_review()
        review["counts"]["duplicates_removed"] = 20
        self.assertTrue(any("inconsistent" in error for error in validate_review(review)))

    def test_full_text_exclusions_require_reason_counts(self):
        review = valid_review()
        review["counts"]["full_text_exclusions"] = {"": 1}
        self.assertTrue(any("non-empty reasons" in error for error in validate_review(review)))

    def test_mermaid_flow_uses_derived_counts(self):
        flow = render_prisma_flow(derive_counts(valid_review()))
        self.assertIn("Records identified from databases (n=10)", flow)
        self.assertIn("Studies included (n=2)", flow)
        self.assertIn("flowchart TD", flow)


if __name__ == "__main__":
    unittest.main()
