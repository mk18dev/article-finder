"""Vercel route entry point for Article Finder."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.web_api import handler as _ArticleFinderHandler  # noqa: E402


class handler(_ArticleFinderHandler):
    """Explicit Vercel-discoverable WSGI-style HTTP handler entrypoint."""

    pass
