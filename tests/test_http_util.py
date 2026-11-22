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
        with patch("http_util.socket.getaddrinfo", return_value=answer("1.1.1.1")):
            self.assertEqual(hu.validate_remote_url("https://example.org/a.pdf"),
                             "https://example.org/a.pdf")

    def test_blocks_private_dns_result(self):
        with patch("http_util.socket.getaddrinfo", return_value=answer("10.0.0.2")):
            with self.assertRaises(ValueError):
                hu.validate_remote_url("https://example.org/a.pdf")

    def test_blocks_mixed_public_and_private_dns_results(self):
        with patch("http_util.socket.getaddrinfo",
                   return_value=answer("1.1.1.1") + answer("192.168.1.2")):
            with self.assertRaises(ValueError):
                hu.validate_remote_url("https://example.org/a.pdf")

    def test_blocks_ipv4_mapped_private_ipv6(self):
        record = [(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                   ("::ffff:127.0.0.1", 443, 0, 0))]
        with patch("http_util.socket.getaddrinfo", return_value=record):
            with self.assertRaises(ValueError):
                hu.validate_remote_url("https://example.org/a.pdf")

    def test_strips_fragments(self):
        with patch("http_util.socket.getaddrinfo", return_value=answer("1.1.1.1")):
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
        with patch("http_util.socket.getaddrinfo", return_value=answer("1.1.1.1")):
            self.assertEqual(hu.validate_remote_url("https://example.org:443/a.pdf"),
                             "https://example.org/a.pdf")

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
        first = Mock()
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


if __name__ == "__main__":
    unittest.main()
