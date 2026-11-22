#!/usr/bin/env python3
"""Fail-closed HTTPS helpers for remote metadata and open-access PDFs.

Only public HTTPS destinations on port 443 are accepted. TLS certificate
verification is always enabled. Redirect destinations are checked again.
Every resolved address is checked and the validated public IP is pinned at
connection time while TLS SNI and certificate verification use the original
hostname. Redirect destinations are resolved and pinned independently.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAILTO = os.environ.get("ARTICLE_FINDER_MAILTO", "").strip()
TIMEOUT = 30
RETRIES = 3
MAX_BYTES = 80 * 1024 * 1024
CHUNK = 1 << 16
_UA = f"article-finder/1.1 (mailto:{MAILTO})" if MAILTO else "article-finder/1.1"


def _resolve_public_addresses(host: str) -> tuple[str, ...]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"unable to resolve destination host: {host}") from exc
    raw_addresses = tuple(dict.fromkeys(
        item[4][0].split("%", 1)[0] for item in infos
    ))
    if not raw_addresses:
        raise ValueError("destination host has no addresses")
    validated = []
    for raw_address in raw_addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise ValueError("destination resolved to an invalid IP address") from exc
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            raise ValueError(f"non-public destination IP is blocked: {address}")
        validated.append(str(address))
    return tuple(dict.fromkeys(validated))


def validate_remote_url(url: str) -> str:
    """Return a normalised URL only when every resolved address is public."""
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise ValueError("URL is empty or too long")
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("malformed URL") from exc
    if parsed.scheme.lower() != "https" or not host:
        raise ValueError("only absolute HTTPS URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials in URLs are not allowed")
    if port not in (None, 443):
        raise ValueError("only HTTPS port 443 is allowed")
    try:
        ipaddress.ip_address(host)
        host = host.lower()
    except ValueError:
        host = host.rstrip(".").encode("idna").decode("ascii").lower()
    if not host or host == "localhost" or host.endswith(".localhost"):
        raise ValueError("local hostnames are not allowed")
    _resolve_public_addresses(host)
    netloc = f"[{host}]" if ":" in host else host
    return urllib.parse.urlunsplit(parsed._replace(netloc=netloc, fragment=""))


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that dials only previously validated public IPs."""

    def __init__(self, host: str, *, pinned_addresses: tuple[str, ...], **kwargs: Any) -> None:
        self._pinned_addresses = pinned_addresses
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        if self._tunnel_host:
            raise OSError("HTTPS proxy tunneling is disabled")
        last_error: OSError | None = None
        for address in self._pinned_addresses:
            sock = None
            try:
                sock = socket.create_connection(
                    (address, self.port), self.timeout, self.source_address
                )
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as exc:
                if sock is not None:
                    sock.close()
                last_error = exc
        if last_error:
            raise last_error
        raise OSError("no validated public destination addresses")


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> Any:
        host = urllib.parse.urlsplit(req.full_url).hostname
        if not host:
            raise ValueError("HTTPS request has no hostname")
        addresses = _resolve_public_addresses(host)
        return self.do_open(
            lambda connection_host, **kwargs: _PinnedHTTPSConnection(
                connection_host, pinned_addresses=addresses, **kwargs
            ),
            req,
            context=self._context,
            check_hostname=self._check_hostname,
        )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 5

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request:
        checked = validate_remote_url(newurl)
        redirected = super().redirect_request(req, fp, code, msg, headers, checked)
        if redirected is None:
            raise urllib.error.HTTPError(newurl, code, "redirect rejected", headers, fp)
        return redirected


def _request(url: str, headers: dict[str, str] | None = None) -> urllib.request.Request:
    merged = {"User-Agent": _UA}
    merged.update(headers or {})
    return urllib.request.Request(url, headers=merged)


def _open(url: str, headers: dict[str, str] | None = None) -> Any:
    checked = validate_remote_url(url)
    # Do not inherit proxy environment variables: the proxy would own DNS
    # resolution and could bypass the destination-IP checks above.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _SafeRedirectHandler(),
        _PinnedHTTPSHandler(context=ssl.create_default_context()),
    )
    response = opener.open(_request(checked, headers), timeout=TIMEOUT)
    validate_remote_url(response.geturl())
    return response


def fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    for attempt in range(RETRIES):
        try:
            with _open(url, headers) as response:
                return json.loads(_read_capped(response))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt + 1 < RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"unreachable: {url}")


def fetch_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    for attempt in range(RETRIES):
        try:
            with _open(url, headers) as response:
                return _read_capped(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt + 1 < RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"unreachable: {url}")


def _read_capped(stream: Any) -> bytes:
    buffer = bytearray()
    while True:
        chunk = stream.read(min(CHUNK, MAX_BYTES + 1 - len(buffer)))
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > MAX_BYTES:
            raise ValueError(f"response larger than {MAX_BYTES} bytes")
    return bytes(buffer)
