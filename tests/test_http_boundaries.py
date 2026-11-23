"""Real HTTP-boundary tests for the Article Finder API adapter."""
from __future__ import annotations

import json
import os
import socket
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from scripts.serve import ArticleFinderHandler
from scripts.web_api import MAX_BODY_BYTES


class HTTPAPIBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ArticleFinderHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.server.server_address
        cls.authority = f"{cls.host}:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def raw_request(
        self,
        body: bytes = b"",
        *,
        path: str = "/api",
        content_type: str | None = "application/json",
        content_length: str | None = "auto",
        origin: str | None = None,
        authorization: str | None = None,
        method: str = "POST",
    ) -> tuple[int, dict]:
        headers = [
            f"Host: {self.authority}",
            "Connection: close",
        ]
        if content_type is not None:
            headers.append(f"Content-Type: {content_type}")
        if content_length == "auto":
            headers.append(f"Content-Length: {len(body)}")
        elif content_length is not None:
            headers.append(f"Content-Length: {content_length}")
        if origin is not None:
            headers.append(f"Origin: {origin}")
        if authorization is not None:
            headers.append(f"Authorization: {authorization}")
        wire = (
            f"{method} {path} HTTP/1.1\r\n"
            + "\r\n".join(headers)
            + "\r\n\r\n"
        ).encode("ascii") + body
        chunks = []
        with socket.create_connection((self.host, self.port), timeout=3) as client:
            client.settimeout(3)
            client.sendall(wire)
            client.shutdown(socket.SHUT_WR)
            while True:
                try:
                    chunk = client.recv(65536)
                except socket.timeout:
                    self.fail("HTTP server did not finish the request")
                if not chunk:
                    break
                chunks.append(chunk)
        response = b"".join(chunks)
        header, _, payload = response.partition(b"\r\n\r\n")
        status = int(header.split(b"\r\n", 1)[0].split()[1])
        return status, json.loads(payload.decode("utf-8"))

    def test_malformed_json_is_rejected_at_http_boundary(self):
        status, body = self.raw_request(b"{")
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_invalid_utf8_is_rejected_at_http_boundary(self):
        status, body = self.raw_request(b"\xff")
        self.assertEqual(status, 400)
        self.assertIn("UTF-8", body["error"])

    def test_non_object_json_is_rejected(self):
        status, body = self.raw_request(b"[]")
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_content_type_must_be_exact_json_media_type(self):
        for value in ("text/plain", "xapplication/json", "application/jsonx"):
            with self.subTest(content_type=value):
                status, _ = self.raw_request(b"{}", content_type=value)
                self.assertEqual(status, 415)

    def test_json_content_type_with_charset_is_accepted(self):
        status, _ = self.raw_request(
            b'{"action":"not-a-supported-action"}',
            content_type="application/json; charset=utf-8",
        )
        self.assertEqual(status, 400)

    def test_missing_invalid_zero_and_negative_content_length_are_rejected(self):
        cases = (
            (None, b"{}"),
            ("not-a-number", b"{}"),
            ("0", b"{}"),
            ("-1", b"{}"),
        )
        for length, payload in cases:
            with self.subTest(content_length=length):
                status, body = self.raw_request(payload, content_length=length)
                self.assertEqual(status, 400)
                self.assertFalse(body["ok"])

    def test_oversized_content_length_is_rejected_before_reading_body(self):
        status, body = self.raw_request(
            b"",
            content_length=str(MAX_BODY_BYTES + 1),
        )
        self.assertEqual(status, 413)
        self.assertFalse(body["ok"])

    def test_truncated_body_is_rejected(self):
        status, body = self.raw_request(b"{}", content_length="10")
        self.assertEqual(status, 400)
        self.assertIn("ناقص", body["error"])

    def test_semantic_validation_uses_422_and_unknown_action_uses_400(self):
        status, body = self.raw_request(
            b'{"action":"discover_sources","keyword":"Survey + recommender systems","category":"unknown"}'
        )
        self.assertEqual(status, 422)
        self.assertFalse(body["ok"])

        status, body = self.raw_request(b'{"action":"unknown"}')
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_preflight_never_grants_cross_origin_access(self):
        status, body = self.raw_request(
            path="/api",
            method="OPTIONS",
            origin="https://attacker.invalid",
        )
        self.assertEqual(status, 403)
        self.assertFalse(body["ok"])

        status, body = self.raw_request(
            path="/api",
            method="OPTIONS",
            origin=f"http://{self.authority}",
        )
        self.assertEqual(status, 405)
        self.assertFalse(body["ok"])

    def test_origin_scheme_must_match_request_scheme(self):
        status, body = self.raw_request(
            b'{"action":"unknown"}',
            origin=f"https://{self.authority}",
        )
        self.assertEqual(status, 403)
        self.assertFalse(body["ok"])

    def test_unknown_action_and_path_are_rejected(self):
        status, body = self.raw_request(b'{"action":"unknown"}')
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        status, body = self.raw_request(b"{}", path="/private/config")
        self.assertEqual(status, 404)
        self.assertFalse(body["ok"])

    def test_actual_http_auth_and_origin_guards(self):
        with patch.dict(os.environ, {"ARTICLE_FINDER_API_KEY": "http-boundary-secret"}, clear=True):
            status, _ = self.raw_request(b'{"action":"unknown"}')
            self.assertEqual(status, 401)

            status, _ = self.raw_request(
                b'{"action":"unknown"}',
                authorization="Bearer http-boundary-secret",
            )
            self.assertEqual(status, 400)

            status, _ = self.raw_request(
                b'{"action":"unknown"}',
                authorization="Bearer http-boundary-secret",
                origin="https://attacker.invalid",
            )
            self.assertEqual(status, 403)

    def test_matching_same_origin_is_allowed_through_to_action_validation(self):
        status, _ = self.raw_request(
            b'{"action":"unknown"}',
            origin=f"http://{self.authority}",
        )
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
