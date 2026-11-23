"""Standard-library HTTP server for the Article Finder web workspace.

The CLI modules and verification engine remain unchanged. This adapter serves
the existing static UI and delegates /api requests to scripts.web_api.handler.
"""
from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from scripts.web_api import handler as APIHandler, http_util

ROOT = Path(__file__).resolve().parents[1]
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class RequestTimeoutHTTPServer(ThreadingHTTPServer):
    """Bound idle client sockets so slow/incomplete requests cannot pin threads."""

    request_timeout = 10.0

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True, *, request_timeout=None):
        if request_timeout is not None:
            self.request_timeout = float(request_timeout)
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, client_address


class ArticleFinderHandler(APIHandler):
    server_version = "ArticleFinder/1.1.0"
    sys_version = ""

    def _serve_static(self, head_only: bool = False) -> None:
        path = urlsplit(self.path).path
        entry = STATIC_FILES.get(path)
        if entry is None:
            self._send(404, {"ok": False, "error": "مسیر پیدا نشد."})
            return

        filename, content_type = entry
        target = (ROOT / filename).resolve()
        if target.parent != ROOT or not target.is_file():
            self._send(404, {"ok": False, "error": "فایل پیدا نشد."})
            return

        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache" if filename == "index.html" else "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api" or path.startswith("/api/"):
            super().do_GET()
            return
        self._serve_static()

    def do_HEAD(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api" or path.startswith("/api/"):
            self._send(405, {"ok": False, "error": "HEAD برای API پشتیبانی نمی‌شود."})
            return
        self._serve_static(head_only=True)


def bind_host() -> str:
    """Bind locally by default; exposing the dev server requires explicit opt-in."""
    return os.environ.get("HOST", "127.0.0.1")


def main() -> None:
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError as exc:
        raise SystemExit("PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")

    # Apply server-only budgets at startup; importing this module must not
    # mutate the CLI retrieval policy.
    http_util.TIMEOUT = int(os.environ.get("ARTICLE_FINDER_HTTP_TIMEOUT", "8"))
    http_util.RETRIES = int(os.environ.get("ARTICLE_FINDER_HTTP_RETRIES", "1"))
    if http_util.TIMEOUT < 1 or http_util.RETRIES < 1:
        raise SystemExit("ARTICLE_FINDER_HTTP_TIMEOUT and ARTICLE_FINDER_HTTP_RETRIES must be positive")

    host = bind_host()
    server = RequestTimeoutHTTPServer((host, port), ArticleFinderHandler)
    server.daemon_threads = True
    server.request_queue_size = 64
    print(f"Article Finder listening on {host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
