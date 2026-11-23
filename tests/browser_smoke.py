#!/usr/bin/env python3
"""Browser E2E for Article Finder's discovery, verification, draft and output flows."""
from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("ARTICLE_FINDER_BASE_URL", "http://127.0.0.1:8000")
INJECTED_TITLE = '<img src=x onerror=alert(1)> Evidence Record'


def assert_no_horizontal_overflow(page) -> None:
    dimensions = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth})"
    )
    if dimensions["scroll"] > dimensions["client"]:
        raise AssertionError(f"horizontal overflow: {dimensions}")


def main() -> int:
    page_errors: list[str] = []
    calls: list[dict] = []
    draft_requests = 0

    candidate = {
        "doi": "10.1234/e2e",
        "title": INJECTED_TITLE,
        "authors": ["A. Writer"],
        "year": 2024,
        "type": "journal-article",
        "publisher": "Example Press",
        "venue": "Example Journal",
        "url": "https://doi.org/10.1234/e2e",
    }
    discovery = {
        "ok": True,
        "mode": "discovery",
        "version": "1.1.0",
        "provider": "Crossref",
        "total_returned": 1,
        "candidates": [candidate],
        "plan": [{
            "doi": candidate["doi"],
            "category": "concept",
            "keyword": "Survey + recommender systems",
            "area": "",
            "subject": "",
            "search_evidence": {
                "query": "Survey + recommender systems",
                "doi": candidate["doi"],
                "url": "https://api.crossref.org/works?query=e2e",
                "searched_at": "2026-11-23T00:00:00Z",
            },
        }],
    }
    verification = {
        "ok": True,
        "mode": "sources",
        "version": "1.1.0",
        "language": "fa",
        "summary": {"approved": 0, "pending": 1, "rejected": 0, "errors": 0},
        "results": [{
            "article": {
                "title": INJECTED_TITLE,
                "doi": candidate["doi"],
                "url": candidate["url"],
                "type": "journal",
                "year": 2024,
                "tier": "B",
                "notes": {"fa": "", "en": ""},
            },
            "steps": {"S1": True},
            "verdict": "pending",
            "verified_steps": 1,
            "total_steps": 11,
        }],
        "errors": [],
        "table_markdown": "# E2E verification report",
        "disclaimer": "Test response; not a real verification.",
    }
    draft_result = {
        "ok": True,
        "mode": "draft",
        "version": "1.1.0",
        "language": "fa",
        "summary": {
            "approved_sections": 1,
            "total_sections": 1,
            "passed": 1,
            "failed": 0,
            "pending": 0,
            "total_checks": 1,
        },
        "sections": [{
            "id": "abstract",
            "title": "چکیده",
            "passed": 1,
            "failed": 0,
            "pending": 0,
            "total": 1,
            "verdict": "approved",
        }],
        "checks": [{
            "id": "T1",
            "section": "abstract",
            "ok": True,
            "detail": "E2E test check",
            "label": "وجود چکیده",
            "step": "S1",
            "page": 1,
        }],
        "table_markdown": "# E2E draft report",
        "disclaimer": "Test response; not a real assessment.",
    }

    def api_route(route):
        nonlocal draft_requests
        request = route.request
        if request.method != "POST":
            route.continue_()
            return
        payload = request.post_data_json
        calls.append({
            "action": payload.get("action"),
            "authorization": request.headers.get("authorization"),
        })
        action = payload.get("action")
        if action == "discover_sources":
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(discovery, ensure_ascii=False),
            )
        elif action == "verify_sources":
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(verification, ensure_ascii=False),
            )
        elif action == "check_draft":
            draft_requests += 1
            if draft_requests == 1:
                route.fulfill(
                    status=200,
                    content_type="application/json; charset=utf-8",
                    body=json.dumps(draft_result, ensure_ascii=False),
                )
            else:
                route.fulfill(
                    status=401,
                    content_type="application/json; charset=utf-8",
                    body=json.dumps({"ok": False, "error": "کلید دسترسی معتبر نیست."}, ensure_ascii=False),
                )
        else:
            route.fulfill(
                status=400,
                content_type="application/json; charset=utf-8",
                body=json.dumps({"ok": False, "error": "Unknown E2E action"}),
            )

    with sync_playwright() as playwright:
        browser_name = os.environ.get("ARTICLE_FINDER_BROWSER", "chromium")
        if browser_name not in {"chromium", "firefox", "webkit"}:
            raise ValueError(f"Unsupported browser engine: {browser_name}")
        browser = getattr(playwright, browser_name).launch()
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
            accept_downloads=True,
        )
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.route("**/api", api_route)

        response = page.goto(BASE_URL, wait_until="networkidle", timeout=20_000)
        assert response is not None and response.status == 200
        assert page.locator("html").get_attribute("lang") == "fa"
        assert page.locator("html").get_attribute("dir") == "rtl"
        page.wait_for_function(
            "document.querySelector('#engine-status span')?.textContent.includes('موتور API متصل است')",
            timeout=10_000,
        )
        assert page.locator(".mode-tab").count() == 2
        assert page.locator("#source-form").is_visible()
        assert_no_horizontal_overflow(page)

        page.locator("#access-key").fill("browser-e2e-key")
        page.locator("#discovery-keyword").fill("Survey + recommender systems")
        page.locator("#discover-submit").click()
        page.locator(".discovery-result input[type=checkbox]").wait_for(state="visible")
        assert INJECTED_TITLE in page.locator("#discovery-results").inner_text()
        assert page.locator("#discovery-results img").count() == 0
        page.locator(".discovery-result input[type=checkbox]").check()
        page.get_by_role("button", name="افزودن انتخاب‌ها به طرح شواهد").click()
        plan_value = page.locator("#source-plan").input_value()
        assert candidate["doi"] in plan_value
        page.locator("#source-submit").click()
        page.locator(".source-result").wait_for(state="visible")
        assert page.locator(".source-title").inner_text() == INJECTED_TITLE
        assert page.locator("#result-items img").count() == 0
        assert page.locator("#results-view").is_visible()
        assert any(item["action"] == "verify_sources" for item in calls)
        assert any(item["authorization"] == "Bearer browser-e2e-key" for item in calls)
        assert page.evaluate(
            "() => localStorage.length === 0 && sessionStorage.length === 0"
        )

        page.locator("#copy-output").click()
        page.wait_for_function(
            "document.querySelector('#copy-output').textContent.includes('کپی')",
            timeout=5_000,
        )
        with page.expect_download() as download_info:
            page.locator("#download-output").click()
        download = download_info.value
        assert download.suggested_filename == "article-finder-report.json"

        draft_tab = page.locator('[data-mode="draft"]')
        draft_tab.focus()
        page.keyboard.press("Enter")
        assert draft_tab.get_attribute("aria-selected") == "true"
        assert page.locator("#draft-form").is_visible()
        page.locator("#draft-text").fill(
            "# عنوان\nاین متن برای اجرای آزمون مرورگر و بررسی رابط نوشته شده است.\n\n"
            "## چکیده\nمتن آزمایشی چکیده مقاله."
        )
        page.locator("#draft-access-key").fill("browser-e2e-key")
        page.locator("#draft-submit").click()
        page.locator(".draft-sections").wait_for(state="visible")
        assert page.locator("#results-title").inner_text() == "نتیجهٔ بررسی پیش‌نویس"
        assert any(item["action"] == "check_draft" for item in calls)

        page.locator("#draft-submit").click()
        page.locator("#error-state").wait_for(state="visible")
        assert "کلید دسترسی" in page.locator("#error-message").inner_text()

        for width, height in ((320, 700), (390, 844), (768, 1024), (844, 390), (1440, 900)):
            page.set_viewport_size({"width": width, "height": height})
            assert_no_horizontal_overflow(page)

        if page_errors:
            raise AssertionError("browser page errors: " + "; ".join(page_errors))
        context.close()
        browser.close()

    print(
        "Browser E2E passed: discovery, source submission, safe text rendering, API-key handling, "
        "draft submission, API error state, copy/download controls and responsive layouts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
