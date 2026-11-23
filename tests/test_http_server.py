from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from scripts.serve import ArticleFinderHandler, bind_host
from scripts.web_api import handler as VercelAPIHandler
from scripts import http_util


class ArticleFinderHTTPServerTests(unittest.TestCase):
    def test_importing_server_does_not_mutate_cli_transport_defaults(self):
        self.assertEqual(http_util.TIMEOUT, 30)
        self.assertEqual(http_util.RETRIES, 3)

    def test_local_server_binds_loopback_unless_overridden(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(bind_host(), "127.0.0.1")
        with patch.dict("os.environ", {"HOST": "0.0.0.0"}, clear=True):
            self.assertEqual(bind_host(), "0.0.0.0")

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ArticleFinderHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, data=None, headers=None, method=None):
        request = urllib.request.Request(
            self.base + path,
            data=data,
            headers=headers or {},
            method=method,
        )
        try:
            return urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            return error

    def test_root_serves_real_ui_with_security_headers(self):
        response = self.request("/")
        body = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("text/html", response.headers["Content-Type"])
        self.assertIn("ARTICLE FINDER", body)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_static_assets_are_served(self):
        for path, content_type in (
            ("/styles.css", "text/css"),
            ("/app.js", "text/javascript"),
        ):
            with self.subTest(path=path):
                response = self.request(path)
                self.assertEqual(response.status, 200)
                self.assertIn(content_type, response.headers["Content-Type"])
                self.assertGreater(len(response.read()), 100)

    def test_health_endpoint_is_live(self):
        response = self.request("/api")
        payload = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "article-finder")
        self.assertEqual(payload["version"], "1.1.0")
        self.assertIn("source-discovery", payload["capabilities"])

    def test_draft_api_executes_existing_engine(self):
        payload = json.dumps({
            "action": "check_draft",
            "language": "fa",
            "draft": "# عنوان\nاین متن برای آزمون یکپارچه سرور نوشته شده است.\n\n## چکیده\nمتن آزمایشی مقاله.",
        }).encode("utf-8")
        response = self.request(
            "/api",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        result = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "draft")
        self.assertGreater(result["summary"]["total_checks"], 0)


    def test_crossref_discovery_is_exposed_through_http_api(self):
        crossref_result = {"message": {"items": [{
            "DOI": "10.1234/http-discovery",
            "title": ["HTTP Discovery Candidate"],
            "published-online": {"date-parts": [[2024]]},
            "type": "journal-article",
            "publisher": "Example Publisher",
            "container-title": ["Example Journal"],
        }]}}
        payload = json.dumps({
            "action": "discover_sources",
            "keyword": "Survey + recommender systems",
            "category": "concept",
        }).encode("utf-8")
        with patch("scripts.web_api.http_util.fetch_json", return_value=crossref_result):
            response = self.request(
                "/api",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
        result = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "discovery")
        self.assertEqual(result["candidates"][0]["doi"], "10.1234/http-discovery")
        self.assertEqual(result["plan"][0]["search_evidence"]["query"], "Survey + recommender systems")

    def test_unknown_paths_do_not_expose_files(self):
        response = self.request("/../../README.md")
        self.assertEqual(response.status, 404)
        self.assertEqual(json.loads(response.read())["ok"], False)

    def test_head_serves_headers_without_body(self):
        response = self.request("/", method="HEAD")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.read(), b"")

    def test_api_key_is_enforced_when_configured(self):
        with patch.dict("os.environ", {"ARTICLE_FINDER_API_KEY": "railway-test-secret"}):
            denied = self.request("/api", data=b'{"action":"invalid"}',
                                  headers={"Content-Type": "application/json"})
            allowed = self.request("/api", data=b'{"action":"invalid"}',
                                   headers={"Content-Type": "application/json",
                                            "Authorization": "Bearer railway-test-secret"})
        self.assertEqual(denied.status, 401)
        self.assertEqual(allowed.status, 400)


class VercelFunctionRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), VercelAPIHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_vercel_function_paths_are_health_endpoints(self):
        for path in ("/", "/index", "/index.py", "/api", "/api/index", "/api/index.py"):
            with self.subTest(path=path):
                response = urllib.request.urlopen(self.base + path, timeout=3)
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(payload["ok"])
                self.assertIn("source-discovery", payload["capabilities"])

    def test_vercel_function_root_accepts_api_post(self):
        body = json.dumps({
            "action": "check_draft",
            "language": "fa",
            "draft": "# عنوان\\nاین یک متن آزمایشی برای مسیر ریشه تابع است.\\n\\n## چکیده\\nمتن آزمایشی.",
        }).encode("utf-8")
        request = urllib.request.Request(
            self.base + "/",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = urllib.request.urlopen(request, timeout=3)
        payload = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["mode"], "draft")



if __name__ == "__main__":
    unittest.main()
