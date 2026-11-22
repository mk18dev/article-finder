import unittest

from scripts.prisma_review import (
    deduplicate_records,
    derive_counts,
    normalize_doi,
    normalize_title,
    render_prisma_flow,
    validate_review,
)


def stage_review(decision, second_decision=None, reviewer="R1", second_reviewer="R2"):
    result = {
        "reviewer_id": reviewer,
        "decision": decision,
        "reviewed_at": "2026-11-23T10:00:00Z",
        "second_review": {
            "reviewer_id": second_reviewer,
            "decision": second_decision or decision,
            "reviewed_at": "2026-11-23T10:05:00Z",
        },
    }
    if second_decision and second_decision != decision:
        result["adjudication"] = {
            "reviewer_id": "R3",
            "decision": decision,
            "reviewed_at": "2026-11-23T10:10:00Z",
            "note": "Independent adjudication after reviewer disagreement.",
        }
    return result


def valid_review():
    records = [
        {
            "record_id": "r1", "doi": "10.1234/a", "title": "Included Paper A",
            "automation_excluded": False,
            "title_abstract_review": stage_review("include"),
            "full_text_status": "retrieved",
            "full_text_review": stage_review("include"),
            "study_id": "study-a",
        },
        {
            "record_id": "r2", "title": "Excluded Paper B",
            "automation_excluded": False,
            "title_abstract_review": stage_review("include"),
            "full_text_status": "retrieved",
            "full_text_review": dict(stage_review("exclude"), exclusion_reason="wrong study design"),
        },
        {
            "record_id": "r3", "title": "Title Abstract Exclusion C",
            "automation_excluded": False,
            "title_abstract_review": stage_review("exclude"),
            "title_abstract_exclusion_reason": "editorial",
            "full_text_status": "not_sought",
        },
        {
            "record_id": "r4", "title": "Title Abstract Exclusion D",
            "automation_excluded": False,
            "title_abstract_review": stage_review("exclude"),
            "title_abstract_exclusion_reason": "wrong population",
            "full_text_status": "not_sought",
        },
        {
            "record_id": "r5", "title": "Title Abstract Exclusion E",
            "automation_excluded": False,
            "title_abstract_review": stage_review("exclude"),
            "title_abstract_exclusion_reason": "no relevant outcome",
            "full_text_status": "not_sought",
        },
        {
            "record_id": "r6", "title": "Full Text Exclusion F",
            "automation_excluded": False,
            "title_abstract_review": stage_review("include"),
            "full_text_status": "retrieved",
            "full_text_review": dict(stage_review("exclude"), exclusion_reason="wrong study design"),
        },
        {
            "record_id": "r7", "title": "Included Paper G",
            "automation_excluded": False,
            "title_abstract_review": stage_review("include"),
            "full_text_status": "retrieved",
            "full_text_review": stage_review("include"),
            "study_id": "study-g",
        },
        {
            "record_id": "r8", "title": "Not Retrieved H",
            "automation_excluded": False,
            "title_abstract_review": stage_review("include"),
            "full_text_status": "not_retrieved",
        },
        {
            "record_id": "r9", "doi": "https://doi.org/10.1234/a",
            "title": "Conflicting Duplicate Title",
        },
        {
            "record_id": "r10", "title": "Excluded Paper B",
        },
    ]
    return {
        "protocol": {
            "review_type": "systematic",
            "question": "Does intervention X improve outcome Y?",
            "inclusion_criteria": ["Peer-reviewed studies", "Population matches protocol"],
            "exclusion_criteria": ["Editorials", "Wrong population"],
            "registration": {"registry": "OSF", "id": "osf-example"},
            "reviewers": ["R1", "R2", "R3"],
            "dual_screening": True,
        },
        "search_log": [{
            "database": "Crossref",
            "platform": "REST API",
            "query": '"intervention X" AND "outcome Y"',
            "date_run": "2026-11-23",
            "search_url": "https://api.crossref.org/works?query=intervention",
            "hits": 10,
            "limits": "2018-2026; English",
            "status": "ok",
        }],
        "counts": {
            "records_identified": 10,
            "duplicates_removed": 2,
            "records_removed_automation": 0,
            "records_screened": 8,
            "records_excluded_title_abstract": 3,
            "reports_sought": 5,
            "reports_not_retrieved": 1,
            "reports_assessed": 4,
            "reports_excluded_full_text": 2,
            "studies_included": 2,
            "reports_of_included_studies": 2,
        },
        "records": records,
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
        self.assertEqual(duplicates[0]["metadata_conflicts"][0]["field"], "title")

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

    def test_counts_derive_from_raw_screening_ledger(self):
        counts = derive_counts(valid_review())
        self.assertEqual(counts["records_identified"], 10)
        self.assertEqual(counts["duplicates_removed"], 2)
        self.assertEqual(counts["records_screened"], 8)
        self.assertEqual(counts["reports_sought"], 5)
        self.assertEqual(counts["reports_assessed"], 4)
        self.assertEqual(counts["studies_included"], 2)
        self.assertEqual(counts["reports_of_included_studies"], 2)

    def test_count_tampering_is_detected(self):
        review = valid_review()
        review["counts"]["duplicates_removed"] = 20
        self.assertTrue(any("derived from the record ledger" in error for error in validate_review(review)))

    def test_raw_record_count_must_match_search_hits(self):
        review = valid_review()
        review["records"].pop()
        self.assertTrue(any("raw record count" in error for error in validate_review(review)))

    def test_title_abstract_exclusion_requires_reason(self):
        review = valid_review()
        review["records"][2].pop("title_abstract_exclusion_reason")
        self.assertTrue(any("title/abstract exclusion requires" in error for error in validate_review(review)))

    def test_full_text_exclusion_requires_reason(self):
        review = valid_review()
        review["records"][1]["full_text_review"].pop("exclusion_reason")
        self.assertTrue(any("full-text exclusion requires" in error for error in validate_review(review)))

    def test_dual_screeners_must_be_independent(self):
        review = valid_review()
        review["records"][0]["title_abstract_review"]["second_review"]["reviewer_id"] = "R1"
        self.assertTrue(any("must be independent" in error for error in validate_review(review)))

    def test_disagreement_requires_independent_adjudication(self):
        review = valid_review()
        stage = review["records"][0]["title_abstract_review"]
        stage["second_review"]["decision"] = "exclude"
        stage.pop("adjudication", None)
        self.assertTrue(any("requires an adjudication" in error for error in validate_review(review)))

    def test_included_report_requires_study_id(self):
        review = valid_review()
        review["records"][0].pop("study_id")
        self.assertTrue(any("requires study_id" in error for error in validate_review(review)))

    def test_study_count_deduplicates_multiple_reports(self):
        review = valid_review()
        review["records"][6]["study_id"] = "study-a"
        counts = derive_counts(review)
        self.assertEqual(counts["studies_included"], 1)
        self.assertEqual(counts["reports_of_included_studies"], 2)

    def test_mermaid_flow_uses_derived_counts(self):
        flow = render_prisma_flow(derive_counts(valid_review()))
        self.assertIn("Records identified from databases (n=10)", flow)
        self.assertIn("Studies included (n=2)", flow)
        self.assertIn("Reports of included studies (n=2)", flow)
        self.assertIn("flowchart TD", flow)


if __name__ == "__main__":
    unittest.main()
