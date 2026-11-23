"""Network-free security regression tests for http_util."""

import io
from unittest.mock import Mock
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import http_util as hu


def answer(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 443))]


class HttpSecurityTests(unittest.TestCase):
    def test_rejects_http(self):
        with self.assertRaises(ValueError):
            hu.validate_remote_url("http://example.org/a.pdf")

    def test_rejects_localhost(self):
        with self.assertRaises(ValueError):
            hu.validate_remote_url("https://localhost/a.pdf")

    def test_rejects_loopback_ip(self):
        with self.assertRaises(ValueError):
            hu.validate_remote_url("https://127.0.0.1/a.pdf")

    def test_rejects_credentials(self):
        with self.assertRaises(ValueError):
            hu.validate_remote_url("https://user:pass@example.org/a.pdf")

    def test_rejects_nonstandard_port(self):
        with self.assertRaises(ValueError):
            hu.validate_remote_url("https://example.org:8443/a.pdf")

    def test_accepts_public_dns_result(self):
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("1.1.1.1")):
            self.assertEqual(hu.validate_remote_url("https://example.org/a.pdf"),
                             "https://example.org/a.pdf")

    def test_blocks_private_dns_result(self):
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("10.0.0.2")):
            with self.assertRaises(ValueError):
                hu.validate_remote_url("https://example.org/a.pdf")

    def test_blocks_mixed_public_and_private_dns_results(self):
        with patch.object(hu.socket, "getaddrinfo",
                   return_value=answer("1.1.1.1") + answer("192.168.1.2")):
            with self.assertRaises(ValueError):
                hu.validate_remote_url("https://example.org/a.pdf")

    def test_blocks_ipv4_mapped_private_ipv6(self):
        record = [(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                   ("::ffff:127.0.0.1", 443, 0, 0))]
        with patch.object(hu.socket, "getaddrinfo", return_value=record):
            with self.assertRaises(ValueError):
                hu.validate_remote_url("https://example.org/a.pdf")

    def test_strips_fragments(self):
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("1.1.1.1")):
            self.assertEqual(hu.validate_remote_url("https://example.org/a.pdf#page=3"),
                             "https://example.org/a.pdf")

    def test_revalidates_redirect_destinations(self):
        handler = hu._SafeRedirectHandler()
        with self.assertRaises(ValueError):
            handler.redirect_request(
                hu._request("https://example.org/start"), None, 302, "Found", {},
                "http://127.0.0.1/private"
            )


    def test_explicit_default_port_is_normalized(self):
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("1.1.1.1")):
            self.assertEqual(hu.validate_remote_url("https://example.org:443/a.pdf"),
                             "https://example.org/a.pdf")


    def test_public_ipv4_mapped_ipv6_is_normalized_before_dial(self):
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("::ffff:8.8.8.8")):
            self.assertEqual(hu._resolve_public_addresses("example.org"), ("8.8.8.8",))

    def test_private_ipv4_mapped_ipv6_is_rejected(self):
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("::ffff:127.0.0.1")):
            with self.assertRaises(ValueError):
                hu._resolve_public_addresses("example.org")

    def test_pinned_connection_uses_validated_ip_and_original_tls_hostname(self):
        sock = Mock()
        context = Mock()
        context.wrap_socket.return_value = sock
        with patch("http_util.socket.create_connection", return_value=sock) as connect:
            connection = hu._PinnedHTTPSConnection(
                "example.org", pinned_addresses=("1.1.1.1",), context=context
            )
            connection.connect()
            connect.assert_called_once_with(("1.1.1.1", 443), connection.timeout, None)
            context.wrap_socket.assert_called_once_with(sock, server_hostname="example.org")
            connection.close()

    def test_pinned_connection_falls_back_only_to_validated_addresses(self):
        second = Mock()
        context = Mock()
        context.wrap_socket.return_value = second
        with patch("http_util.socket.create_connection", side_effect=[OSError("unreachable"), second]) as connect:
            connection = hu._PinnedHTTPSConnection(
                "example.org",
                pinned_addresses=("1.1.1.1", "8.8.8.8"),
                context=context,
            )
            connection.connect()
            self.assertEqual(connect.call_count, 2)
            self.assertEqual(connect.call_args_list[0].args[0], ("1.1.1.1", 443))
            self.assertEqual(connect.call_args_list[1].args[0], ("8.8.8.8", 443))
            connection.close()

    def test_response_size_is_capped(self):
        with patch.object(hu, "MAX_BYTES", 5):
            with self.assertRaises(ValueError):
                hu._read_capped(io.BytesIO(b"123456"))

    def test_dns_rebinding_between_preflight_and_connect_is_blocked(self):
        with patch.object(hu.socket, "getaddrinfo",
                          side_effect=[answer("1.1.1.1"), answer("127.0.0.1")]), \
             patch.object(hu.socket, "create_connection") as connect:
            with self.assertRaises(ValueError):
                hu._open("https://example.org/paper.pdf")
            connect.assert_not_called()

    def test_ambient_proxy_environment_is_not_used(self):
        from urllib.request import ProxyHandler
        with patch.dict("os.environ", {
            "HTTPS_PROXY": "http://127.0.0.1:8080",
            "HTTP_PROXY": "http://127.0.0.1:8080",
        }), patch.object(hu.socket, "getaddrinfo", return_value=answer("1.1.1.1")), \
             patch.object(hu.urllib.request, "build_opener") as build_opener:
            response = Mock()
            response.geturl.return_value = "https://example.org/paper.pdf"
            response.headers.get.return_value = "application/pdf"
            build_opener.return_value.open.return_value = response
            hu._open("https://example.org/paper.pdf")
            handlers = build_opener.call_args.args
            self.assertTrue(any(isinstance(handler, ProxyHandler) and handler.proxies == {}
                                for handler in handlers))

    def test_fetch_response_retries_transient_timeout_and_keeps_metadata(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.side_effect = [b"payload", b""]
        response.geturl.return_value = "https://cdn.example/paper.pdf"
        response.headers.get.return_value = "application/pdf"
        with patch.object(hu, "_open", side_effect=[TimeoutError("timed out"), response]) as opened, \
             patch.object(hu.time, "sleep") as sleep:
            result = hu.fetch_response("https://example.org/paper.pdf")
        self.assertEqual(result.body, b"payload")
        self.assertEqual(result.final_url, "https://cdn.example/paper.pdf")
        self.assertEqual(result.content_type, "application/pdf")
        self.assertEqual(opened.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_timeout_retry_stops_at_configured_attempt_limit(self):
        with patch.object(hu, "_open", side_effect=TimeoutError("timed out")) as opened, \
             patch.object(hu.time, "sleep") as sleep:
            with self.assertRaises(TimeoutError):
                hu.fetch_response("https://example.org/paper.pdf")
        self.assertEqual(opened.call_count, hu.RETRIES)
        self.assertEqual(sleep.call_count, hu.RETRIES - 1)

    def test_https_redirect_to_private_dns_is_blocked(self):
        handler = hu._SafeRedirectHandler()
        with patch.object(hu.socket, "getaddrinfo", return_value=answer("10.0.0.9")):
            with self.assertRaises(ValueError):
                handler.redirect_request(
                    hu._request("https://example.org/start"), None, 302, "Found", {},
                    "https://internal.example/private"
                )

    def test_fetch_response_retries_http_429_and_503(self):
        from urllib.error import HTTPError
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.side_effect = [b"ok", b""]
        response.geturl.return_value = "https://example.org/result"
        response.headers.get.return_value = "application/json"
        errors = [
            HTTPError("https://example.org", 429, "rate limited", {}, None),
            HTTPError("https://example.org", 503, "unavailable", {}, None),
        ]
        with patch.object(hu, "_open", side_effect=errors + [response]) as opened, \
             patch.object(hu.time, "sleep") as sleep:
            result = hu.fetch_response("https://example.org/result")
        self.assertEqual(result.body, b"ok")
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_tls_context_requires_certificate_and_hostname_verification(self):
        context = hu.ssl.create_default_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, hu.ssl.CERT_REQUIRED)


if __name__ == "__main__":
    unittest.main()
