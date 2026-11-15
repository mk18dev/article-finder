"""Tests for scripts/fetch_pdf.py: candidate selection and the PDF check, no network."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_pdf as fp


def record(**overrides) -> dict:
    base = {
        "best_oa_location": {"pdf_url": "https://example.org/a.pdf", "landing_page_url": "https://example.org/a"},
        "locations": [{"pdf_url": None, "landing_page_url": "https://example.org/b.pdf"}],
        "open_access": {"oa_url": "https://example.org/c"},
        "ids": {},
    }
    base.update(overrides)
    return base


class CandidateTests(unittest.TestCase):
    def test_best_oa_pdf_comes_first(self) -> None:
        self.assertEqual(fp.candidates(record())[0], "https://example.org/a.pdf")

    def test_landing_page_pdf_is_included(self) -> None:
        self.assertIn("https://example.org/b.pdf", fp.candidates(record()))

    def test_plain_landing_page_is_not_a_candidate(self) -> None:
        urls = fp.candidates(record())
        self.assertNotIn("https://example.org/a", urls)

    def test_arxiv_id_becomes_pdf_url(self) -> None:
        urls = fp.candidates(record(ids={"arxiv": "https://arxiv.org/abs/2301.12345"}))
        self.assertIn("https://arxiv.org/pdf/2301.12345", urls)

    def test_duplicates_removed(self) -> None:
        urls = fp.candidates(record(locations=[{"pdf_url": "https://example.org/a.pdf"}]))
        self.assertEqual(urls.count("https://example.org/a.pdf"), 1)

    def test_empty_record_has_no_candidates(self) -> None:
        self.assertEqual(fp.candidates({"best_oa_location": {}, "locations": [], "open_access": {}}), [])

    def test_non_http_urls_are_dropped(self) -> None:
        urls = fp.candidates({"best_oa_location": {"pdf_url": "ftp://x/a.pdf"}, "locations": []})
        self.assertEqual(urls, [])


class PdfCheckTests(unittest.TestCase):
    def test_real_pdf_header_accepted(self) -> None:
        payload = b"%PDF-1.7\n" + b"0" * fp.MIN_PDF_BYTES
        self.assertTrue(fp.looks_like_pdf(payload))

    def test_html_error_page_rejected(self) -> None:
        self.assertFalse(fp.looks_like_pdf(b"<!doctype html>" + b"0" * fp.MIN_PDF_BYTES))

    def test_tiny_pdf_rejected(self) -> None:
        self.assertFalse(fp.looks_like_pdf(b"%PDF-1.7\nshort"))

    def test_empty_body_rejected(self) -> None:
        self.assertFalse(fp.looks_like_pdf(b""))


class NamingTests(unittest.TestCase):
    def test_slug_is_numbered_and_ascii(self) -> None:
        self.assertEqual(fp.slug(3, "Hybrid Recommender Systems: Survey"), "03-hybrid-recommender-systems-survey")

    def test_persian_title_still_yields_a_name(self) -> None:
        self.assertTrue(fp.slug(1, "کاربرد یادگیری عمیق").startswith("01-"))

    def test_slug_is_capped(self) -> None:
        self.assertLessEqual(len(fp.slug(1, "x" * 200)), 63)


class SourceTests(unittest.TestCase):
    def test_doi_recovered_from_url(self) -> None:
        sources = fp.load_sources_text('[{"title": "A", "url": "https://doi.org/10.1000/XYZ"}]')
        self.assertEqual(sources[0].doi, "10.1000/xyz")

    def test_wrapped_payload_supported(self) -> None:
        sources = fp.load_sources_text('{"cutoff": "B", "articles": [{"title": "A", "doi": "10.1000/a"}]}')
        self.assertEqual(sources[0].title, "A")


class ReportTests(unittest.TestCase):
    def test_summary_counts(self) -> None:
        source = fp.Source(title="A", doi="10.1000/a", year=2024)
        results = [
            fp.Result(source, "downloaded", "100 KB", "pdfs/01-a.pdf"),
            fp.Result(source, "paywalled", "", routes=list(fp.ROUTES)),
        ]
        text = fp.report(results, Path("pdfs"))
        self.assertIn("**1/2 downloaded", text)
        self.assertIn("1 need a licensed route", text)

    def test_never_offers_sci_hub_as_a_route(self) -> None:
        source = fp.Source(title="A", doi="10.1000/a")
        text = fp.report([fp.Result(source, "paywalled", "", routes=list(fp.ROUTES))], Path("pdfs"))
        rows = [line for line in text.splitlines() if line.startswith("| 1 |")]
        self.assertTrue(rows)
        self.assertNotIn("sci-hub", rows[0].lower())
        self.assertIn("never used", text)


if __name__ == "__main__":
    unittest.main()

class TitleMatchTests(unittest.TestCase):
    def test_exact_title_matches(self) -> None:
        self.assertTrue(fp.title_matches("A deep model", "A Deep Model."))

    def test_partial_title_rejected(self) -> None:
        self.assertFalse(fp.title_matches("A deep model for cold start", "A shallow survey"))

    def test_punctuation_and_case_ignored(self) -> None:
        self.assertTrue(fp.title_matches("Cold-Start Item Recommendation",
                                         "cold start item recommendation"))

    def test_empty_title_rejected(self) -> None:
        self.assertFalse(fp.title_matches("", "anything"))


class IrandocTests(unittest.TestCase):
    def test_route_is_url_encoded(self) -> None:
        route = fp.irandoc_route("یادگیری عمیق")
        self.assertTrue(route.startswith("https://ganj.irandoc.ac.ir"))
        self.assertNotIn(" ", route)

    def test_no_open_copy_offers_irandoc(self) -> None:
        source = fp.Source(title="عنوان", doi="10.1000/a")
        text = fp.report([fp.Result(source, "paywalled", "", routes=list(fp.ROUTES) + [fp.irandoc_route(source.title)])],
                         Path("pdfs"))
        self.assertIn("ganj.irandoc.ac.ir", text)


class EmailDraftTests(unittest.TestCase):
    def test_draft_contains_doi_and_salutation(self) -> None:
        source = fp.Source(title="A paper", doi="10.1000/a", year=2024)
        text = fp.email_drafts([fp.Result(source, "paywalled")], contact=lambda doi: ("Family", "Journal"))
        self.assertIn("DOI 10.1000/a", text)
        self.assertIn("Dear", text)

    def test_downloaded_source_is_skipped(self) -> None:
        source = fp.Source(title="A paper", doi="10.1000/a")
        text = fp.email_drafts([fp.Result(source, "downloaded", "ok", "pdfs/a.pdf")])
        self.assertNotIn("A paper", text)

    def test_no_doi_is_stated(self) -> None:
        source = fp.Source(title="A paper", doi="")
        self.assertIn("(none)", fp.email_drafts([fp.Result(source, "paywalled")], contact=lambda doi: ("", "")))


class ResolverChainTests(unittest.TestCase):
    def test_relative_pdf_link_is_resolved(self) -> None:
        html = b'<html><a href="/files/paper.pdf">pdf</a></html>'
        self.assertEqual(fp.pdf_links(html, "https://repo.example/a/1"), ["https://repo.example/files/paper.pdf"])

    def test_absolute_pdf_link_kept(self) -> None:
        html = b'<html><a href="https://cdn.example/x.pdf">x</a></html>'
        self.assertEqual(fp.pdf_links(html, "https://repo.example/"), ["https://cdn.example/x.pdf"])

    def test_non_html_has_no_links(self) -> None:
        self.assertEqual(fp.pdf_links(b"%PDF-1.7 binary", "https://repo.example/"), [])

    def test_links_are_capped(self) -> None:
        html = b"<html>" + b"".join(b'<a href="/%d.pdf">p</a>' % i for i in range(10)) + b"</html>"
        self.assertLessEqual(len(fp.pdf_links(html, "https://repo.example/")), 3)

    def test_duplicate_links_removed(self) -> None:
        html = b'<html><a href="/a.pdf">1</a><a href="/a.pdf">2</a></html>'
        self.assertEqual(len(fp.pdf_links(html, "https://repo.example/")), 1)
