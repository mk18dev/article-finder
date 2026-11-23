"""Vercel HTTP API for the Article Finder web interface.

The established CLI modules remain the source of truth. This file only adapts
bounded JSON requests to their existing public functions.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

# Keep hosted requests bounded without changing the CLI's normal defaults.
if os.environ.get("VERCEL") == "1":
    os.environ.setdefault("ARTICLE_FINDER_HTTP_TIMEOUT", "8")
    os.environ.setdefault("ARTICLE_FINDER_HTTP_RETRIES", "1")

import check_draft  # noqa: E402
import render_table  # noqa: E402
import verify_source  # noqa: E402
import http_util  # noqa: E402

if os.environ.get("VERCEL") == "1":
    http_util.TIMEOUT = int(os.environ.get("ARTICLE_FINDER_HTTP_TIMEOUT", "8"))
    http_util.RETRIES = int(os.environ.get("ARTICLE_FINDER_HTTP_RETRIES", "1"))

_DRAFT_LOCK = RLock()

APP_VERSION = "1.1.0"
MAX_BODY_BYTES = 512 * 1024
MAX_DRAFT_CHARS = 180_000
MAX_SOURCE_ENTRIES = 4
CATEGORIES = {"concept", "challenge", "application", "methodology"}
TIERS = {"A", "B", "C", "D"}
LANGUAGES = {"fa", "en"}
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class RequestError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _string(
    value: Any,
    field: str,
    limit: int,
    required: bool = False,
    allow_newlines: bool = False,
) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise RequestError(f"فیلد «{field}» باید متن باشد.")
    value = value.strip()
    if required and not value:
        raise RequestError(f"فیلد «{field}» الزامی است.")
    control_check = value
    if allow_newlines:
        control_check = control_check.replace("\r", "").replace("\n", "").replace("\t", "")
    if len(value) > limit or CONTROL_RE.search(control_check):
        raise RequestError(f"مقدار «{field}» نامعتبر یا بیش از حد طولانی است.")
    return value


def normalize_doi(value: Any) -> str:
    raw = _string(value, "DOI", 255, required=True)
    lowered = raw.lower()
    matched_prefix = next((prefix for prefix in DOI_PREFIXES if lowered.startswith(prefix)), None)
    if matched_prefix is not None:
        try:
            parsed = urllib.parse.urlsplit(raw)
            port = parsed.port
        except ValueError as exc:
            raise RequestError("نشانی DOI معتبر نیست.") from exc
        if (parsed.scheme != "https"
                or (parsed.hostname or "").lower() not in {"doi.org", "dx.doi.org"}
                or port not in (None, 443)
                or parsed.username is not None or parsed.password is not None):
            raise RequestError("نشانی DOI باید HTTPS و از دامنه رسمی doi.org باشد.")
        if parsed.query or parsed.fragment:
            raise RequestError("نشانی DOI نباید query یا fragment داشته باشد.")
        raw = urllib.parse.unquote(parsed.path.lstrip("/"))
        raw = _string(raw, "DOI", 200, required=True)
    elif lowered.startswith("doi:"):
        raw = raw[4:].strip()
    if "?" in raw or "#" in raw or not DOI_RE.fullmatch(raw) or len(raw) > 200:
        raise RequestError("DOI باید با قالب 10.xxxx/... وارد شود و query یا fragment نداشته باشد.")
    return raw


def _language(payload: dict[str, Any]) -> str:
    value = payload.get("language", "fa")
    if not isinstance(value, str) or value not in LANGUAGES:
        raise RequestError("زبان باید fa یا en باشد.")
    return value


def validate_source_payload(payload: Any) -> tuple[list[dict[str, Any]], str, str, str | None]:
    if not isinstance(payload, dict):
        raise RequestError("بدنه درخواست باید یک شیء JSON باشد.")
    raw_entries = payload.get("entries", payload.get("plan"))
    if isinstance(raw_entries, str):
        try:
            raw_entries = json.loads(raw_entries)
        except json.JSONDecodeError as exc:
            raise RequestError("JSON طرح منابع قابل‌خواندن نیست.") from exc
    if isinstance(raw_entries, dict) and isinstance(raw_entries.get("entries"), list):
        raw_entries = raw_entries["entries"]
    if not isinstance(raw_entries, list) or not 1 <= len(raw_entries) <= MAX_SOURCE_ENTRIES:
        raise RequestError(f"باید بین ۱ تا {MAX_SOURCE_ENTRIES} رکورد منبع ارسال شود.")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries, 1):
        if not isinstance(raw, dict):
            raise RequestError(f"رکورد شماره {index} باید یک شیء JSON باشد.")
        entry = dict(raw)
        doi = normalize_doi(entry.get("doi"))
        doi_key = doi.casefold()
        if doi_key in seen:
            raise RequestError(f"DOI تکراری است: {doi}")
        seen.add(doi_key)
        entry["doi"] = doi

        category = _string(entry.get("category"), "category", 24, required=True).lower()
        if category not in CATEGORIES:
            raise RequestError("دسته باید concept، challenge، application یا methodology باشد.")
        entry["category"] = category

        keyword = _string(entry.get("keyword"), "keyword", 240, required=True)
        if not verify_source.keyword_gate(keyword):
            raise RequestError("کلیدواژه باید قالب «کلیدواژه مجاز + موضوع پژوهش» داشته باشد.")
        entry["keyword"] = keyword

        for field in ("area", "subject"):
            entry[field] = _string(entry.get(field), field, 160)
        entries.append(entry)

    cutoff = _string(payload.get("cutoff", "B"), "cutoff", 1).upper()
    if cutoff not in TIERS:
        raise RequestError("حد نصاب رتبه باید A، B، C یا D باشد.")
    language = _language(payload)
    bibliography = payload.get("bibliography")
    if bibliography not in (None, "apa", "ieee"):
        raise RequestError("سبک منابع باید apa یا ieee باشد.")
    return entries, cutoff, language, bibliography



def run_source_discovery(payload: Any) -> dict[str, Any]:
    """Search Crossref and return real candidates with traceable search records."""
    if not isinstance(payload, dict):
        raise RequestError("بدنه درخواست باید یک شیء JSON باشد.")
    keyword = _string(payload.get("keyword"), "keyword", 240, required=True)
    if not verify_source.keyword_gate(keyword):
        raise RequestError("کلیدواژه باید قالب «کلیدواژه مجاز + موضوع پژوهش» داشته باشد.")
    category = _string(payload.get("category", "concept"), "category", 24).lower()
    if category not in CATEGORIES:
        raise RequestError("دسته باید concept، challenge، application یا methodology باشد.")
    area = _string(payload.get("area", ""), "area", 160)
    subject = _string(payload.get("subject", ""), "subject", 160)
    rows = payload.get("limit", 4)
    if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 4:
        raise RequestError("تعداد نتایج باید عددی بین ۱ تا ۴ باشد.")

    params = urllib.parse.urlencode({
        "query.bibliographic": keyword,
        "rows": rows,
        "select": "DOI,title,author,published-print,published-online,type,publisher,container-title,volume,issue,ISSN,URL",
    })
    search_url = "https://api.crossref.org/works?" + params
    try:
        response = http_util.fetch_json(search_url, headers={"Accept": "application/json"})
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        raise RequestError("جست‌وجو در Crossref انجام نشد؛ سرویس فراداده در دسترس نیست.", 502) from exc
    if not isinstance(response, dict) or not isinstance(response.get("message"), dict):
        raise RequestError("پاسخ Crossref ساختار معتبری ندارد.", 502)
    items = response["message"].get("items") or []
    if not isinstance(items, list):
        raise RequestError("فهرست نتایج Crossref معتبر نیست.", 502)
    searched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    candidates = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            doi = normalize_doi(item.get("DOI"))
        except RequestError:
            continue
        if doi.casefold() in seen:
            continue
        seen.add(doi.casefold())
        title_values = item.get("title") or []
        title = str(title_values[0]).strip() if title_values else ""
        if not title:
            continue
        date_parts = (
            (item.get("published-print") or {}).get("date-parts")
            or (item.get("published-online") or {}).get("date-parts")
            or []
        )
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        authors = []
        for author in item.get("author") or []:
            if not isinstance(author, dict):
                continue
            name = " ".join(part for part in (
                str(author.get("given", "")).strip(),
                str(author.get("family", "")).strip(),
            ) if part)
            if name:
                authors.append(name)
        candidates.append({
            "doi": doi,
            "title": title,
            "authors": authors,
            "year": year if isinstance(year, int) else None,
            "type": str(item.get("type", "")),
            "publisher": str(item.get("publisher", "")),
            "venue": str((item.get("container-title") or [""])[0]),
            "url": f"https://doi.org/{urllib.parse.quote(doi, safe='/')}",
            "search_evidence": {
                "query": keyword,
                "doi": doi,
                "url": search_url,
                "searched_at": searched_at,
            },
        })
        if len(candidates) >= rows:
            break

    return {
        "ok": True,
        "mode": "discovery",
        "version": APP_VERSION,
        "query": keyword,
        "searched_at": searched_at,
        "provider": "Crossref",
        "total_returned": len(candidates),
        "candidates": candidates,
        "plan": [{
            "doi": candidate["doi"],
            "category": category,
            "keyword": keyword,
            "area": area,
            "subject": subject,
            "search_evidence": candidate["search_evidence"],
        } for candidate in candidates],
        "disclaimer": "این‌ها نتایج واقعی جست‌وجوی Crossref هستند، نه منابع تأییدشده. همه دروازه‌های اعتبارسنجی مستقل اجرا می‌شوند و شواهد انسانیِ ثبت‌نشده همچنان Pending می‌مانند.",
    }


def run_source_verification(payload: Any) -> dict[str, Any]:
    entries, cutoff, language, bibliography = validate_source_payload(payload)
    articles: list[dict[str, Any]] = []
    works: list[Any] = []
    errors: list[dict[str, str]] = []

    for entry in entries:
        try:
            article, work = verify_source.build(entry)
            articles.append(article)
            works.append(work)
        except urllib.error.HTTPError as exc:
            errors.append({
                "doi": entry["doi"],
                "message": (
                    "رکورد در Crossref پیدا نشد." if exc.code == 404
                    else f"سرویس فراداده پاسخ HTTP {exc.code} داد."
                ),
            })
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append({
                "doi": entry["doi"],
                "message": f"ارتباط با سرویس فراداده برقرار نشد ({type(exc).__name__}).",
            })
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            errors.append({
                "doi": entry["doi"],
                "message": f"پردازش این رکورد کامل نشد ({type(exc).__name__}).",
            })

    evaluated: list[dict[str, Any]] = []
    counts = {"approved": 0, "pending": 0, "rejected": 0, "errors": len(errors)}
    for article in articles:
        steps, verdict = render_table.evaluate(article, cutoff)
        counts[verdict.lower()] += 1
        evaluated.append({
            "article": article,
            "steps": steps,
            "verdict": verdict.lower(),
            "verified_steps": sum(value is True for value in steps.values()),
            "total_steps": len(steps),
        })

    data = {"cutoff": cutoff, "articles": articles}
    return {
        "ok": True,
        "mode": "sources",
        "version": APP_VERSION,
        "language": language,
        "summary": counts,
        "results": evaluated,
        "errors": errors,
        "table_markdown": render_table.render(data, language, cutoff, True, bibliography),
        "s6_checklist_markdown": verify_source.checklist(articles, works) if articles else "",
        "disclaimer": (
            "این ابزار ساختار و وجود شواهد ثبت‌شده را بررسی می‌کند؛ "
            "درستی ادعای ارزیاب یا نمایه‌بودن را مستقل از صفحه مرجع اثبات نمی‌کند."
        ),
    }


def validate_manual(raw: Any) -> dict[str, tuple[bool | None, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > 100:
        raise RequestError("بخش ارزیابی دستی باید یک شیء JSON با حداکثر ۱۰۰ قاعده باشد.")
    allowed = {rule[0] for rule in check_draft.RULES}
    result: dict[str, tuple[bool | None, str]] = {}
    for rule_id, value in raw.items():
        if rule_id not in allowed:
            raise RequestError(f"شناسه قاعده ناشناخته است: {rule_id}")
        if isinstance(value, bool):
            result[rule_id] = (value, "")
        elif isinstance(value, dict):
            verdict = value.get("ok")
            note = _string(value.get("note", ""), f"{rule_id}.note", 500)
            if verdict is not None and not isinstance(verdict, bool):
                raise RequestError(f"مقدار ok برای {rule_id} باید true، false یا null باشد.")
            result[rule_id] = (verdict, note)
        else:
            raise RequestError(f"قضاوت {rule_id} باید boolean یا شیء دارای ok باشد.")
    return result


def run_draft_check(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RequestError("بدنه درخواست باید یک شیء JSON باشد.")
    draft = _string(
        payload.get("draft"), "draft", MAX_DRAFT_CHARS,
        required=True, allow_newlines=True,
    )
    if len(draft) < 20:
        raise RequestError("پیش‌نویس برای ارزیابی خیلی کوتاه است.")
    language = _language(payload)
    manual = validate_manual(payload.get("manual"))

    with _DRAFT_LOCK:
        check_draft.LANG = language
        sections = check_draft.parse(draft)
        rows = check_draft.evaluate(sections, manual)
        table_markdown = check_draft.render(rows, language)
    section_results: list[dict[str, Any]] = []
    for section in check_draft.SECTIONS:
        items = [row for row in rows if row[1] == section]
        passed = sum(row[2] is True for row in items)
        failed = sum(row[2] is False for row in items)
        pending = sum(row[2] is None for row in items)
        verdict = "approved" if items and passed == len(items) else (
            "rejected" if failed else "pending"
        )
        section_results.append({
            "id": section,
            "title": check_draft.NAMES[language][section],
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "total": len(items),
            "verdict": verdict,
        })

    checks = [{
        "id": row[0],
        "section": row[1],
        "ok": row[2],
        "detail": row[3],
        "label": row[5] if language == "fa" else row[4],
        "step": check_draft.RULE_STEP[row[0]][0],
        "page": check_draft.RULE_STEP[row[0]][1],
    } for row in rows]

    return {
        "ok": True,
        "mode": "draft",
        "version": APP_VERSION,
        "language": language,
        "summary": {
            "approved_sections": sum(item["verdict"] == "approved" for item in section_results),
            "total_sections": len(section_results),
            "passed": sum(item["ok"] is True for item in checks),
            "failed": sum(item["ok"] is False for item in checks),
            "pending": sum(item["ok"] is None for item in checks),
            "total_checks": len(checks),
        },
        "sections": section_results,
        "checks": checks,
        "table_markdown": table_markdown,
        "disclaimer": "قواعد خودکار از متن استخراج می‌شوند؛ موارد دستی فقط با قضاوت ثبت‌شده تغییر وضعیت می‌دهند.",
    }


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    server_version = "ArticleFinderAPI/1.1.0"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid logging DOI payloads, draft contents or credentials.
        super().log_message("Article Finder API request")

    def _request_scheme(self) -> str:
        forwarded = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
        if forwarded in {"https", "http"}:
            return forwarded
        if os.environ.get("VERCEL") == "1":
            return "https"
        return "https" if isinstance(getattr(self, "connection", None), ssl.SSLSocket) else "http"

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urllib.parse.urlsplit(origin)
            host = self.headers.get("Host", "")
            return (
                parsed.scheme.lower() == self._request_scheme()
                and parsed.netloc.lower() == host.lower()
                and parsed.username is None
                and parsed.password is None
                and parsed.path == ""
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            return False

    def _auth_mode(self) -> str:
        if os.environ.get("ARTICLE_FINDER_API_KEY", ""):
            return "key_required"
        if os.environ.get("VERCEL") == "1" and os.environ.get("ARTICLE_FINDER_PUBLIC_MODE") != "1":
            return "misconfigured"
        return "public"

    def _authorized(self) -> bool:
        mode = self._auth_mode()
        if mode == "public":
            return True
        if mode == "misconfigured":
            return False
        required = os.environ["ARTICLE_FINDER_API_KEY"]
        supplied = self.headers.get("Authorization", "")
        prefix = "Bearer "
        return supplied.startswith(prefix) and hmac.compare_digest(
            supplied[len(prefix):], required
        )

    def _send(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/") not in {"", "/", "/index", "/index.py", "/api", "/api/health", "/api/index", "/api/index.py"}:
            self._send(404, {"ok": False, "error": "مسیر API پیدا نشد."})
            return
        self._send(200, {
            "ok": True,
            "service": "article-finder",
            "version": APP_VERSION,
            "capabilities": [
                "source-discovery",
                "source-verification",
                "draft-checking",
                "systematic-review-cli",
                "citation-identity-audit-cli",
                "full-text-retrieval-cli",
            ],
            "modes": [
                {"id": "source-verification", "surface": "web-api"},
                {"id": "draft-checking", "surface": "web-api"},
                {"id": "systematic-review", "surface": "cli-only"},
                {"id": "citation-identity-audit", "surface": "cli-only"},
            ],
            "auth_mode": self._auth_mode(),
            "auth_configured": bool(os.environ.get("ARTICLE_FINDER_API_KEY")),
        })

    def do_OPTIONS(self) -> None:
        # Deliberately send no Access-Control-Allow-* headers.
        status = 405 if self._same_origin() else 403
        self._send(status, {
            "ok": False,
            "error": "درخواست preflight/CORS پشتیبانی نمی‌شود.",
        })

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/") not in {"", "/", "/index", "/index.py", "/api", "/api/index", "/api/index.py"}:
            self._send(404, {"ok": False, "error": "مسیر API پیدا نشد."})
            return
        if not self._same_origin():
            self._send(403, {"ok": False, "error": "درخواست cross-origin مجاز نیست."})
            return
        if self._auth_mode() == "misconfigured":
            self._send(503, {
                "ok": False,
                "error": "کلید API در محیط production تنظیم نشده است؛ ARTICLE_FINDER_API_KEY را تنظیم کن یا public mode را صریحاً فعال کن.",
            })
            return
        if not self._authorized():
            self._send(401, {"ok": False, "error": "کلید دسترسی معتبر نیست."})
            return
        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            self._send(415, {"ok": False, "error": "Content-Type باید application/json باشد."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(400, {"ok": False, "error": "Content-Length نامعتبر است."})
            return
        if length <= 0:
            self._send(400, {"ok": False, "error": "بدنه درخواست خالی است."})
            return
        if length > MAX_BODY_BYTES:
            self._send(413, {"ok": False, "error": "حجم درخواست از سقف مجاز بیشتر است."})
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise RequestError("بدنه درخواست ناقص دریافت شد.", 400)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RequestError("بدنه درخواست باید یک شیء JSON باشد.", 400)
            action = payload.get("action")
            if action == "discover_sources":
                result = run_source_discovery(payload)
            elif action == "verify_sources":
                result = run_source_verification(payload)
            elif action == "check_draft":
                result = run_draft_check(payload)
            else:
                raise RequestError(
                    "action باید discover_sources، verify_sources یا check_draft باشد.",
                    400,
                )
            self._send(200, result)
        except RequestError as exc:
            self._send(exc.status, {"ok": False, "error": str(exc)})
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "JSON درخواست معتبر نیست."})
        except UnicodeDecodeError:
            self._send(400, {"ok": False, "error": "متن درخواست باید UTF-8 باشد."})
        except Exception as exc:
            self.log_error("Unhandled API error: %s", type(exc).__name__)
            self._send(500, {"ok": False, "error": "خطای داخلی هنگام پردازش درخواست."})
