import unittest
from unittest.mock import patch

from scripts.search_databases import discover, search_crossref, search_openalex


class SearchDatabasesTests(unittest.TestCase):
    @patch("scripts.search_databases.fetch_json")
    def test_crossref_logs_retrieved_count_not_total_available(self, fetch):
        fetch.return_value = {
            "message": {
                "total-results": 900,
                "items": [
                    {"DOI": "10.1234/a", "title": ["Paper A"], "author": [],
                     "issued": {"date-parts": [[2024]]}, "publisher": "Publisher"}
                ],
            }
        }
        records, log = search_crossref("hybrid systems", 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(log["hits"], 1)
        self.assertEqual(log["total_available"], 900)
        self.assertEqual(log["query"], "hybrid systems")
        self.assertTrue(log["search_url"].startswith("https://api.crossref.org/"))

    @patch("scripts.search_databases.fetch_json")
    def test_openalex_maps_doi_and_retraction_flag(self, fetch):
        fetch.return_value = {
            "meta": {"count": 50},
            "results": [{
                "doi": "https://doi.org/10.1234/b",
                "title": "Paper B",
                "publication_year": 2023,
                "authorships": [{"author": {"display_name": "Jane Smith"}}],
                "primary_location": {"source": {"display_name": "Journal"}},
                "is_retracted": False,
            }],
        }
        records, log = search_openalex("recommender systems", 1)
        self.assertEqual(records[0]["doi"], "10.1234/b")
        self.assertFalse(records[0]["is_retracted"])
        self.assertEqual(log["hits"], 1)
        self.assertEqual(log["total_available"], 50)

    @patch("scripts.search_databases.search_crossref")
    @patch("scripts.search_databases.search_openalex")
    def test_discover_merges_duplicate_dois_and_preserves_search_logs(self, openalex, crossref):
        crossref.return_value = (
            [{"doi": "10.1234/a", "title": "Paper A", "source_provider": "Crossref"}],
            {"database": "Crossref", "hits": 1, "status": "ok"},
        )
        openalex.return_value = (
            [{"doi": "10.1234/A", "title": "Paper A duplicate", "source_provider": "OpenAlex"}],
            {"database": "OpenAlex", "hits": 1, "status": "ok"},
        )
        result = discover("paper search", 5)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(len(result["raw_records"]), 2)
        self.assertEqual(len(result["duplicates"]), 1)
        self.assertTrue(all(item.get("record_id") for item in result["raw_records"]))
        self.assertEqual(len(result["search_log"]), 2)
        self.assertEqual(result["providers_succeeded"], ["Crossref", "OpenAlex"])
        self.assertEqual([item["record_id"] for item in result["raw_records"]], ["crossref-1", "openalex-2"])

    @patch("scripts.search_databases.search_crossref")
    @patch("scripts.search_databases.search_openalex", side_effect=TimeoutError("offline"))
    def test_partial_provider_failure_is_explicit(self, openalex, crossref):
        crossref.return_value = (
            [{"doi": "10.1234/a", "title": "Paper A"}],
            {"database": "Crossref", "hits": 1, "status": "ok"},
        )
        result = discover("paper search", 5)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["errors"], [{"provider": "openalex", "error": "TimeoutError"}])
        self.assertEqual(result["search_log"][1]["status"], "error")

    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError):
            discover("  ")

    def test_limit_bounds_enforced(self):
        with self.assertRaises(ValueError):
            discover("topic", 101)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            discover("topic", 10, ("unknown",))


if __name__ == "__main__":
    unittest.main()
