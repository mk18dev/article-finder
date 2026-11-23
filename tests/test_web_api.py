from __future__ import annotations

import io
import urllib.error
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import web_api as api


class SourceInputTests(unittest.TestCase):
    def payload(self, **overrides):
        value = {
            "entries": [{
                "doi": "10.3233/IDA-163209",
                "category": "concept",
                "keyword": "Survey + hybrid recommender systems",
                "area": "computer science",
                "subject": "hybrid recommender systems",
            }],
            "cutoff": "B",
            "language": "fa",
        }
        value.update(overrides)
        return value

    def test_validate_payload_returns_validated_entries(self):
        entries, cutoff, language, bibliography = api.validate_source_payload(self.payload())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["doi"], "10.3233/IDA-163209")
        self.assertEqual(cutoff, "B")
        self.assertEqual(language, "fa")
        self.assertIsNone(bibliography)

    def test_accepts_plain_doi_and_doi_url(self):
        self.assertEqual(api.normalize_doi("10.3233/IDA-163209"), "10.3233/IDA-163209")
        self.assertEqual(
            api.normalize_doi("https://doi.org/10.3233/IDA-163209"),
            "10.3233/IDA-163209",
        )

    def test_rejects_foreign_doi_host_and_query_injection(self):
        with self.assertRaises(api.RequestError):
            api.normalize_doi("https://evil.example/10.1234/test")
        with self.assertRaises(api.RequestError):
            api.normalize_doi("10.1234/test?next=https://example.com")
        with self.assertRaises(api.RequestError):
            api.normalize_doi("10.1234/test#fragment")
        with self.assertRaises(api.RequestError):
            api.normalize_doi("https://doi.org:444/10.1234/test")
        with self.assertRaises(api.RequestError):
            api.normalize_doi("http://doi.org/10.1234/test")

    def test_requires_supported_category_and_search_keyword(self):
        payload = self.payload()
        payload["entries"][0]["category"] = "misc"
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)

        payload = self.payload()
        payload["entries"][0]["keyword"] = "hybrid recommender systems"
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)

    def test_rejects_duplicate_dois_and_oversized_batches(self):
        payload = self.payload()
        payload["entries"].append(dict(payload["entries"][0]))
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)

        payload = self.payload()
        payload["entries"] = [dict(payload["entries"][0]) for _ in range(api.MAX_SOURCE_ENTRIES + 1)]
        for index, entry in enumerate(payload["entries"]):
            entry["doi"] = f"10.1234/paper-{index}"
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)

    def test_validates_cutoff_and_language(self):
        payload = self.payload(cutoff="Z")
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)
        payload = self.payload(language="xx")
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)
        payload = self.payload(language=["fa"])
        with self.assertRaises(api.RequestError):
            api.validate_source_payload(payload)


class SourceDiscoveryTests(unittest.TestCase):
    def test_crossref_candidates_include_exact_query_and_search_evidence(self):
        response = {"message": {"items": [{
            "DOI": "10.1234/example.1",
            "title": ["A Real Candidate"],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "published-online": {"date-parts": [[2025, 4, 1]]},
            "type": "journal-article",
            "publisher": "Example Publisher",
            "container-title": ["Example Journal"],
        }]}}
        with patch.object(api.http_util, "fetch_json", return_value=response) as fetch:
            result = api.run_source_discovery({
                "keyword": "Survey + recommender systems",
                "category": "concept",
                "limit": 4,
            })
        fetch.assert_called_once()
        self.assertEqual(result["provider"], "Crossref")
        self.assertEqual(result["total_returned"], 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["doi"], "10.1234/example.1")
        self.assertEqual(candidate["title"], "A Real Candidate")
        self.assertEqual(candidate["authors"], ["Ada Lovelace"])
        self.assertEqual(candidate["year"], 2025)
        evidence = result["plan"][0]["search_evidence"]
        self.assertEqual(evidence["query"], "Survey + recommender systems")
        self.assertEqual(evidence["doi"], candidate["doi"])
        self.assertTrue(evidence["url"].startswith("https://api.crossref.org/works?"))
        self.assertTrue(evidence["searched_at"].endswith("Z"))

    def test_discovery_rejects_invalid_query_category_and_limit(self):
        with self.assertRaises(api.RequestError):
            api.run_source_discovery({"keyword": "recommender systems"})
        with self.assertRaises(api.RequestError):
            api.run_source_discovery({"keyword": "Survey + recommender systems", "category": "other"})
        with self.assertRaises(api.RequestError):
            api.run_source_discovery({"keyword": "Survey + recommender systems", "limit": 5})

    def test_discovery_skips_malformed_and_duplicate_dois(self):
        response = {"message": {"items": [
            {"DOI": "not-a-doi", "title": ["Bad"]},
            {"DOI": "10.1234/dup", "title": ["First"]},
            {"DOI": "10.1234/dup", "title": ["Duplicate"]},
            {"DOI": "10.1234/no-title", "title": []},
        ]}}
        with patch.object(api.http_util, "fetch_json", return_value=response):
            result = api.run_source_discovery({"keyword": "Survey + recommender systems"})
        self.assertEqual([item["title"] for item in result["candidates"]], ["First"])

    def test_discovery_rejects_malformed_crossref_payload(self):
        with patch.object(api.http_util, "fetch_json", return_value={"unexpected": []}):
            with self.assertRaises(api.RequestError) as caught:
                api.run_source_discovery({"keyword": "Survey + recommender systems"})
        self.assertEqual(caught.exception.status, 502)

    def test_discovery_reports_upstream_failure_as_bad_gateway(self):
        with patch.object(api.http_util, "fetch_json", side_effect=OSError("offline")):
            with self.assertRaises(api.RequestError) as caught:
                api.run_source_discovery({"keyword": "Survey + recommender systems"})
        self.assertEqual(caught.exception.status, 502)


class SourceExecutionTests(unittest.TestCase):
    def test_existing_verifier_and_renderer_are_used(self):
        doi = "10.3233/IDA-163209"
        article = {
            "title": "A Test Research Paper",
            "authors": ["Writer, A."],
            "year": 2025,
            "type": "journal",
            "venue": "Test Journal",
            "publisher": "IEEE",
            "url": f"https://doi.org/{doi}",
            "doi": doi,
            "category": "concept",
            "tier": "B",
            "tier_verified": True,
            "keyword": "Survey + hybrid recommender systems",
            "cited_by": 4,
            "integrity_status": "not_flagged",
            "crossref_updates": [],
            "steps": {f"S{i}": True for i in range(1, 12)},
            "evidence": {},
            "notes": {"en": "", "fa": ""},
        }
        work = SimpleNamespace(
            kind="journal",
            title=article["title"],
            publisher="IEEE",
            issns=[],
            source_issn="",
        )
        with patch.object(api.verify_source, "build", return_value=(article, work)) as build:
            result = api.run_source_verification({
                "entries": [{
                    "doi": doi,
                    "category": "concept",
                    "keyword": "Survey + hybrid recommender systems",
                }],
                "language": "en",
            })
        build.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["approved"], 1)
        self.assertEqual(result["results"][0]["verdict"], "approved")
        self.assertIn("Approved sources", result["table_markdown"])

    def test_upstream_failure_is_reported_per_doi(self):
        doi = "10.3233/IDA-163209"
        failure = urllib.error.HTTPError(
            url="https://api.crossref.org/works/" + doi,
            code=404,
            msg="not found",
            hdrs=None,
            fp=io.BytesIO(b""),
        )
        with patch.object(api.verify_source, "build", side_effect=failure):
            result = api.run_source_verification({
                "entries": [{
                    "doi": doi,
                    "category": "concept",
                    "keyword": "Survey + hybrid recommender systems",
                }],
            })
        self.assertEqual(result["summary"]["errors"], 1)
        self.assertEqual(result["errors"][0]["message"], "رکورد در Crossref پیدا نشد.")


class DraftExecutionTests(unittest.TestCase):
    def test_multiline_persian_draft_is_accepted(self):
        result = api.run_draft_check({
            "draft": "# عنوان\nاین یک پیش‌نویس آزمایشی برای بررسی ساختار مقاله است.\n\n## چکیده\nمتن آزمایشی.",
            "language": "fa",
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "draft")
        self.assertEqual(result["summary"]["total_sections"], 10)
        self.assertGreater(result["summary"]["total_checks"], 0)
        self.assertIn("عنوان", result["table_markdown"])

    def test_manual_rules_are_limited_to_known_rule_ids(self):
        self.assertTrue(api.validate_manual({"T2": {"ok": False, "note": "شاهد کافی نیست"}}))
        with self.assertRaises(api.RequestError):
            api.validate_manual({"UNKNOWN": True})

    def test_manual_verdict_must_be_boolean_or_null(self):
        with self.assertRaises(api.RequestError):
            api.validate_manual({"T2": {"ok": "yes"}})


class RequestBoundaryTests(unittest.TestCase):
    def test_health_contract_exposes_four_modes_and_cli_only_boundaries(self):
        request = object.__new__(api.handler)
        request.headers = {}
        request.path = "/api"
        sent = {}
        request._send = lambda status, payload: sent.update(status=status, payload=payload)
        request.do_GET()
        self.assertEqual(sent["status"], 200)
        self.assertEqual(
            {mode["id"]: mode["surface"] for mode in sent["payload"]["modes"]},
            {
                "source-verification": "web-api",
                "draft-checking": "web-api",
                "systematic-review": "cli-only",
                "citation-identity-audit": "cli-only",
            },
        )
        self.assertIn("full-text-retrieval-cli", sent["payload"]["capabilities"])

    def test_draft_limit_is_enforced_at_180000_characters(self):
        with self.assertRaises(api.RequestError) as raised:
            api.run_draft_check({"draft": "x" * (api.MAX_DRAFT_CHARS + 1), "language": "fa"})
        self.assertEqual(raised.exception.status, 422)

    def test_same_origin_guard_rejects_scheme_mismatch(self):
        request = object.__new__(api.handler)
        request.headers = {
            "Origin": "https://article-finder.vercel.app",
            "Host": "article-finder.vercel.app",
            "X-Forwarded-Proto": "http",
        }
        self.assertFalse(request._same_origin())

    def test_same_origin_guard_rejects_external_origin(self):
        request = object.__new__(api.handler)
        request.headers = {
            "Origin": "https://attacker.example",
            "Host": "article-finder.vercel.app",
        }
        self.assertFalse(request._same_origin())

    def test_same_origin_guard_accepts_matching_origin(self):
        request = object.__new__(api.handler)
        request.headers = {
            "Origin": "https://article-finder.vercel.app",
            "Host": "article-finder.vercel.app",
            "X-Forwarded-Proto": "https",
        }
        self.assertTrue(request._same_origin())

    def test_optional_bearer_key_uses_constant_time_comparison(self):
        request = object.__new__(api.handler)
        request.headers = {"Authorization": "Bearer correct-test-key"}
        with patch.dict("os.environ", {"ARTICLE_FINDER_API_KEY": "correct-test-key"}, clear=False):
            self.assertTrue(request._authorized())
        request.headers = {"Authorization": "Bearer incorrect-test-key"}
        with patch.dict("os.environ", {"ARTICLE_FINDER_API_KEY": "correct-test-key"}, clear=False):
            self.assertFalse(request._authorized())

    def test_no_configured_key_keeps_local_public_mode_explicit(self):
        request = object.__new__(api.handler)
        request.headers = {}
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(request._auth_mode(), "public")
            self.assertTrue(request._authorized())

    def test_vercel_without_key_fails_closed(self):
        request = object.__new__(api.handler)
        request.headers = {}
        with patch.dict("os.environ", {"VERCEL": "1"}, clear=True):
            self.assertEqual(request._auth_mode(), "misconfigured")
            self.assertFalse(request._authorized())

    def test_vercel_public_mode_requires_explicit_opt_in(self):
        request = object.__new__(api.handler)
        request.headers = {}
        with patch.dict("os.environ", {"VERCEL": "1", "ARTICLE_FINDER_PUBLIC_MODE": "1"}, clear=True):
            self.assertEqual(request._auth_mode(), "public")
            self.assertTrue(request._authorized())


if __name__ == "__main__":
    unittest.main()
