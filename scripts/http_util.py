#!/usr/bin/env python3
"""Shared HTTP helpers for the article-finder scripts.

Crossref and OpenAlex both ask for a contact address in the User-Agent, and
both rate-limit scripted clients, so the retry and TLS handling lives here
instead of being copied into every script.
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any

MAILTO = "article-finder@example.org"
TIMEOUT = 30
RETRIES = 3
MAX_BYTES = 80 * 1024 * 1024
CHUNK = 1 << 16

_UNVERIFIED_TLS = False
_UA = f"article-finder/1.2 (mailto:{MAILTO})"


def _request(url: str, headers: dict[str, str] | None = None) -> urllib.request.Request:
    merged = {"User-Agent": _UA}
    merged.update(headers or {})
    return urllib.request.Request(url, headers=merged)


def _open(url: str, headers: dict[str, str] | None = None) -> Any:
    global _UNVERIFIED_TLS
    context = ssl._create_unverified_context() if _UNVERIFIED_TLS else ssl.create_default_context()
    try:
        return urllib.request.urlopen(_request(url, headers), timeout=TIMEOUT, context=context)
    except ssl.SSLError:
        if _UNVERIFIED_TLS:
            raise
        _UNVERIFIED_TLS = True
        print("warning: local CA store is incomplete, continuing with an unverified TLS context",
              file=sys.stderr)
        return _open(url, headers)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError) and not _UNVERIFIED_TLS:
            _UNVERIFIED_TLS = True
            print("warning: local CA store is incomplete, continuing with an unverified TLS context",
                  file=sys.stderr)
            return _open(url, headers)
        raise


def fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    for attempt in range(RETRIES):
        try:
            with _open(url, headers) as response:
                return json.load(response)
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
    while chunk := stream.read(CHUNK):
        buffer.extend(chunk)
        if len(buffer) > MAX_BYTES:
            raise ValueError(f"response larger than {MAX_BYTES} bytes")
    return bytes(buffer)
