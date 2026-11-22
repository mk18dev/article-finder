import unittest

from scripts.prisma_review import (
    deduplicate_records,
    derive_counts,
    normalize_doi,
    normalize_title,
    render_prisma_flow,
    validate_review,
)


STAMP = "2026-11-23T10:00:00Z"


def stage_review(decision, reviewer="reviewer-a"):
    return {"decision": decision, "reviewer_id": reviewer, "reviewed_at": STAMP}


def valid_review():
    records = []
    for index in range(1, 4):
        records.append({
            "record_id": f"r{index}",
            "doi": f"10.1234/{index}",
            "title": f"Excluded title {index}",
            "title_abstract_review": stage_review("exclude"),
            "full_text_status": "not_sought",
        })
    records.append({
        "record_id": "r4", "doi": "10.1234/4", "title": "Unavailable full text",
        "title_abstract_review": stage_review("include"),
        "full_text_status": "not_retrieved",
    })
    for index in (5, 6):
        records.append({
            "record_id": f"r{index}", "doi": f"10.1234/{index}", "title": f"Full text excluded {index}",
            "title_abstract_review": stage_review("include"),
            "full_text_status": "retrieved",
            "full_text_review": {
                **stage_review("exclude"),
                "exclusion_reason": "wrong study design" if index == 5 else "wrong population",
            },
        })
    for index in (7, 8):
        records.append({
            "record_id": f"r{index}", "doi": f"10.1234/{index}", "title": f"Included study {index}",
            "title_abstract_review": stage_review("include"),
            "full_text_status": "retrieved",
            "full_text_review": stage_review("include"),
        })
    records.extend([
        {"record_id": "dup1", "doi": "10.1234/1", "title": "Duplicate of record 1"},
        {"record_id": "dup2", "doi": "10.1234/2", "title": "Duplicate of record 2"},
    ])
    return {
        "protocol": {
            "review_type": "systematic",
            "question": "Does intervention X improve outcome Y?",
            "inclusion_criteria": ["Peer-reviewed studies", "Population matches protocol"],
            "exclusion_criteria": ["Editorials", "Wrong population"],
            "registration": {"registry": "OSF", "id": "osf-example"},
            "reviewers": ["reviewer-a"],
            "dual_screening": False,
            "single_reviewer_justification": "This pilot review was screened by one reviewer.",
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
        "records": records,
    }


class PrismaReviewTests(unittest.TestCase):
    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC"), "10.1234/abc")
        self.assertEqual(normalize_doi("doi: 10.1234/ABC"), "10.1234/abc")

    def test_title_normalization(self):
        self.assertEqual(normalize_title("A Study: Recommender-Systems!"), "a study recommender systems")

    def test_deduplicate_by_doi_and_preserve_canonical(self):
        unique, duplicates = deduplicate_records([
            {"record_id": "first", "title": "Paper A", "doi": "10.1234/ABC"},
            {"record_id": "second", "title": "Different title", "doi": "https://doi.org/10.1234/abc"},
            {"record_id": "third", "title": "Unique Paper"},
        ])
        self.assertEqual([item["record_id"] for item in unique], ["first", "third"])
        self.assertEqual(duplicates[0]["duplicate_of"], "first")
        self.assertEqual(duplicates[0]["key_type"], "doi")

    def test_deduplicate_by_normalized_title_as_last_resort(self):
        unique, duplicates = deduplicate_records([
            {"record_id": "a", "title": "A Study on AI"},
            {"record_id": "b", "title": "a-study on AI!"},
        ])
        self.assertEqual(len(unique), 1)
        self.assertEqual(duplicates[0]["key_type"], "title")

    def test_protocol_requires_reproducible_search_log(self):
        review = valid_review()
        review["search_log"][0]["query"] = ""
        self.assertTrue(any("search_log[1].query" in error for error in validate_review(review)))

    def test_search_date_must_be_iso_date(self):
        review = valid_review()
        review["search_log"][0]["date_run"] = "23/11/2026"
        self.assertTrue(any("YYYY-MM-DD" in error for error in validate_review(review)))

    def test_failed_provider_cannot_count_as_completed_search(self):
        review = valid_review()
        review["search_log"][0]["status"] = "error"
        self.assertTrue(any("marked failed" in error for error in validate_review(review)))

    def test_counts_are_derived_from_raw_record_ledger(self):
        counts = derive_counts(valid_review())
        self.assertEqual(counts["records_identified"], 10)
        self.assertEqual(counts["duplicates_removed"], 2)
        self.assertEqual(counts["records_screened"], 8)
        self.assertEqual(counts["records_excluded_title_abstract"], 3)
        self.assertEqual(counts["reports_sought"], 5)
        self.assertEqual(counts["reports_not_retrieved"], 1)
        self.assertEqual(counts["reports_assessed"], 4)
        self.assertEqual(counts["reports_excluded_full_text"], 2)
        self.assertEqual(counts["studies_included"], 2)

    def test_raw_records_must_match_retrieved_search_hits(self):
        review = valid_review()
        review["records"].pop()
        self.assertTrue(any("must equal retrieved search hits" in error for error in validate_review(review)))

    def test_manual_count_cannot_override_record_ledger(self):
        review = valid_review()
        review["counts"] = {"records_screened": 999}
        self.assertTrue(any("derived from the record ledger" in error for error in validate_review(review)))

    def test_full_text_exclusions_require_reason(self):
        review = valid_review()
        review["records"][4]["full_text_review"].pop("exclusion_reason")
        self.assertTrue(any("requires exclusion_reason" in error for error in validate_review(review)))

    def test_reviewer_timestamp_must_be_timezone_aware(self):
        review = valid_review()
        review["records"][0]["title_abstract_review"]["reviewed_at"] = "2026-11-23T10:00:00"
        self.assertTrue(any("timezone-aware" in error for error in validate_review(review)))

    def test_dual_screening_requires_independent_second_reviewer(self):
        review = valid_review()
        review["protocol"]["dual_screening"] = True
        review["protocol"]["reviewers"] = ["reviewer-a", "reviewer-b"]
        self.assertTrue(any("second_review" in error for error in validate_review(review)))

    def test_dual_reviewer_disagreement_requires_adjudication(self):
        review = valid_review()
        review["protocol"]["dual_screening"] = True
        review["protocol"]["reviewers"] = ["reviewer-a", "reviewer-b"]
        for record in review["records"][:8]:
            stage = record.get("title_abstract_review")
            if stage:
                stage["second_review"] = {
                    "decision": "exclude" if stage["decision"] == "include" else "include",
                    "reviewer_id": "reviewer-b",
                    "reviewed_at": STAMP,
                }
        self.assertTrue(any("disagreement requires an adjudication" in error for error in validate_review(review)))


    def test_dual_screening_passes_with_independent_adjudicator(self):
        review = valid_review()
        review["protocol"]["dual_screening"] = True
        review["protocol"]["reviewers"] = ["reviewer-a", "reviewer-b", "reviewer-c"]
        for record in review["records"][:8]:
            for field in ("title_abstract_review", "full_text_review"):
                stage = record.get(field)
                if stage:
                    stage["second_review"] = {
                        "decision": stage["decision"],
                        "reviewer_id": "reviewer-b",
                        "reviewed_at": STAMP,
                    }
        first = review["records"][0]["title_abstract_review"]
        first["second_review"]["decision"] = "include"
        first["adjudication"] = {
            "decision": "exclude",
            "reviewer_id": "reviewer-c",
            "reviewed_at": STAMP,
            "note": "Adjudicated against the prespecified inclusion criteria.",
        }
        self.assertEqual(validate_review(review), [])

    def test_automation_exclusion_is_counted_and_requires_reason(self):
        review = valid_review()
        record = review["records"][7]
        record["automation_excluded"] = True
        record["automation_tool"] = "dedicated duplicate classifier"
        record["automation_exclusion_reason"] = "Exact duplicate of a retained record"
        record["full_text_status"] = "not_sought"
        record.pop("title_abstract_review")
        record.pop("full_text_review", None)
        counts = derive_counts(review)
        self.assertEqual(counts["records_removed_automation"], 1)
        self.assertEqual(counts["records_screened"], 7)

    def test_mermaid_flow_uses_derived_counts(self):
        flow = render_prisma_flow(derive_counts(valid_review()))
        self.assertIn("Records identified from databases (n=10)", flow)
        self.assertIn("Studies included (n=2)", flow)
        self.assertIn("flowchart TD", flow)


if __name__ == "__main__":
    unittest.main()
