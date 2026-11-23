"""End-to-end orchestration tests for PDF retrieval, without network access."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fetch_pdf as fp


PDF = b"%PDF-1.7\n" + b"0" * fp.MIN_PDF_BYTES
PRIMARY_URL = "https://open.example/paper.pdf"
SECONDARY_URL = "https://mirror.example/paper.pdf"


def openalex_record(*urls: str) -> dict:
    return {
        "best_oa_location": {"is_oa": True, "pdf_url": urls[0]} if urls else {},
        "locations": [{"is_oa": True, "pdf_url": value} for value in urls[1:]],
        "open_access": {},
        "ids": {},
    }


def fetched(body: bytes, url: str, content_type: str = "application/pdf") -> fp.FetchResponse:
    return fp.FetchResponse(body=body, final_url=url, content_type=content_type)


class DownloadOneIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.source = fp.Source(
            title="Hybrid Recommender Systems: A Survey",
            doi="10.1234/integration.1",
            year=2024,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_download_one_fetches_valid_pdf_and_persists_it(self):
        with (
            patch.object(fp, "fetch_json", return_value=openalex_record(PRIMARY_URL)),
            patch.object(fp, "external_candidate_records", return_value=[]),
            patch.object(fp, "fetch_response", return_value=fetched(PDF, PRIMARY_URL)) as fetch,
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        expected = self.out / "01-hybrid-recommender-systems-a-survey.pdf"
        self.assertEqual(result.status, "downloaded")
        self.assertEqual(Path(result.path), expected)
        self.assertEqual(expected.read_bytes(), PDF)
        self.assertEqual(fetch.call_args.args[0], PRIMARY_URL)
        self.assertFalse(list(self.out.glob("*.part")))

    def test_failed_candidate_falls_through_to_the_next_pdf(self):
        with (
            patch.object(
                fp, "fetch_json",
                return_value=openalex_record(PRIMARY_URL, SECONDARY_URL),
            ),
            patch.object(fp, "external_candidate_records", return_value=[]),
            patch.object(fp, "fetch_response", side_effect=[
                OSError("blocked"), fetched(PDF, SECONDARY_URL)
            ]) as fetch,
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        self.assertEqual(result.status, "downloaded")
        self.assertEqual(fetch.call_count, 2)
        self.assertIn(SECONDARY_URL, result.detail)
        self.assertTrue(Path(result.path).is_file())

    def test_html_landing_page_resolves_and_saves_nested_pdf_link(self):
        html = b'<html><a href="/files/final.pdf">PDF</a></html>'
        with (
            patch.object(fp, "fetch_json", return_value=openalex_record(PRIMARY_URL)),
            patch.object(fp, "external_candidate_records", return_value=[]),
            patch.object(fp, "fetch_response", side_effect=[
                fetched(html, PRIMARY_URL, "text/html"),
                fetched(PDF, "https://open.example/files/final.pdf"),
            ]) as fetch,
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        self.assertEqual(result.status, "downloaded")
        self.assertEqual(fetch.call_count, 2)
        self.assertIn("https://open.example/files/final.pdf", result.detail)
        self.assertEqual(Path(result.path).read_bytes(), PDF)

    def test_html_error_page_is_not_saved_as_a_pdf(self):
        html = b"<html><body>Access denied</body></html>" + b" " * fp.MIN_PDF_BYTES
        with (
            patch.object(fp, "fetch_json", return_value=openalex_record(PRIMARY_URL)),
            patch.object(fp, "external_candidate_records", return_value=[]),
            patch.object(fp, "fetch_response", return_value=fetched(html, PRIMARY_URL, "text/html")),
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        self.assertEqual(result.status, "no-pdf")
        self.assertEqual(list(self.out.iterdir()), [])

    def test_lookup_failure_is_reported_without_attempting_download(self):
        with (
            patch.object(fp, "fetch_json", side_effect=TimeoutError("provider timeout")),
            patch.object(fp, "fetch_response") as fetch,
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        self.assertEqual(result.status, "lookup-failed")
        self.assertIn("TimeoutError", result.detail)
        fetch.assert_not_called()

    def test_missing_doi_returns_guidance_without_network(self):
        source = fp.Source(title="No identifier", doi="")
        with patch.object(fp, "fetch_json") as lookup:
            result = fp.download_one(1, source, self.out, dry_run=False)
        self.assertEqual(result.status, "no-doi")
        lookup.assert_not_called()

    def test_no_registered_open_copy_returns_paywall_routes(self):
        with (
            patch.object(fp, "fetch_json", return_value=openalex_record()),
            patch.object(fp, "external_candidate_records", return_value=[]),
            patch.object(fp, "fetch_response") as fetch,
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        self.assertEqual(result.status, "paywalled")
        self.assertTrue(result.routes)
        fetch.assert_not_called()

    def test_dry_run_returns_candidates_without_downloading(self):
        with (
            patch.object(fp, "fetch_json", return_value=openalex_record(PRIMARY_URL)),
            patch.object(fp, "external_candidate_records", return_value=[]),
            patch.object(fp, "fetch_response") as fetch,
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=True)

        self.assertEqual(result.status, "candidate")
        self.assertIn(PRIMARY_URL, result.detail)
        fetch.assert_not_called()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_exhausted_bad_candidates_return_no_pdf(self):
        with (
            patch.object(fp, "fetch_json", return_value=openalex_record(PRIMARY_URL)),
            patch.object(
                fp, "external_candidate_records",
                return_value=[("Semantic Scholar", SECONDARY_URL)],
            ),
            patch.object(fp, "fetch_response", side_effect=[
                OSError("offline"), fetched(b"not a pdf", SECONDARY_URL, "text/plain")
            ]),
        ):
            result = fp.download_one(1, self.source, self.out, dry_run=False)

        self.assertEqual(result.status, "no-pdf")
        self.assertIn("2 candidate(s) tried", result.detail)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_save_failure_returns_status_without_creating_partial_file(self):
        missing_dir = self.out / "does-not-exist"
        result = fp.save(1, self.source, missing_dir, PDF, PRIMARY_URL)
        self.assertEqual(result.status, "save-failed")
        self.assertFalse(missing_dir.exists())

    def test_failed_atomic_replace_cleans_up_temporary_file(self):
        with patch.object(Path, "replace", side_effect=OSError("replace denied")):
            result = fp.save(1, self.source, self.out, PDF, PRIMARY_URL)
        self.assertEqual(result.status, "save-failed")
        self.assertEqual(list(self.out.iterdir()), [])


class ProviderFallbackTests(unittest.TestCase):
    def test_external_provider_failure_does_not_stop_other_providers(self):
        with (
            patch.object(fp, "unpaywall_candidates", side_effect=RuntimeError("unavailable")),
            patch.object(fp, "semantic_scholar_candidates", return_value=[SECONDARY_URL]),
            patch.object(fp, "core_candidates", return_value=[]),
            patch.object(fp, "arxiv_title_candidates", return_value=[]),
        ):
            values = fp.external_candidates("10.1234/integration.1", "A paper")
        self.assertEqual(values, [SECONDARY_URL])


if __name__ == "__main__":
    unittest.main()
