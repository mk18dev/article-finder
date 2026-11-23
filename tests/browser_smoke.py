#!/usr/bin/env python3
"""Browser E2E for functional, accessibility and performance regression checks."""
from __future__ import annotations

import json
import os
from urllib.parse import urlsplit
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

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
    console_errors: list[str] = []
    api_route_hits: list[dict] = []
    api_requests: list[str] = []
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
        if urlsplit(request.url).path.rstrip("/") == "/api":
            api_route_hits.append({"method": request.method, "url": request.url})
        if urlsplit(request.url).path.rstrip("/") != "/api":
            route.continue_()
            return
        if request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps({
                    "ok": True,
                    "service": "article-finder",
                    "version": "1.1.0",
                    "capabilities": ["source-discovery", "source-verification", "draft-checking"],
                    "auth_mode": "public",
                    "auth_configured": False,
                }),
            )
            return
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
        if browser_name == "chromium":
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on(
            "request",
            lambda request: api_requests.append(request.url)
            if urlsplit(request.url).path.rstrip("/") == "/api" else None,
        )
        page.route("**/*", api_route)
        if browser_name == "chromium":
            axe_bundle = Path("node_modules/axe-core/axe.min.js")
            if not axe_bundle.is_file():
                raise AssertionError("Pinned axe-core bundle is missing")
            axe_source = axe_bundle.read_text(encoding="utf-8")
            page.route(
                "**/axe.min.js",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/javascript; charset=utf-8",
                    body=axe_source,
                ),
            )

        response = page.goto(BASE_URL, wait_until="networkidle", timeout=20_000)
        assert response is not None and response.status == 200

        if browser_name == "chromium":
            page.add_script_tag(url=BASE_URL.rstrip("/") + "/axe.min.js")
            accessibility = page.evaluate("""async () => {
                const result = await axe.run(document, {
                    runOnly: {
                        type: "tag",
                        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
                    }
                });
                return result.violations.map(item => ({
                    id: item.id,
                    impact: item.impact,
                    help: item.help,
                    nodes: item.nodes.map(node => ({
                        target: node.target,
                        summary: node.failureSummary
                    }))
                }));
            }""")
            if accessibility:
                raise AssertionError("WCAG 2.2 AA accessibility violations: " + json.dumps(
                    accessibility, ensure_ascii=False
                ))

        performance = page.evaluate("""() => {
            const navigation = performance.getEntriesByType("navigation")[0];
            const resources = performance.getEntriesByType("resource");
            return {
                dom_content_loaded_ms: navigation.domContentLoadedEventEnd,
                load_ms: navigation.loadEventEnd,
                transfer_bytes: resources.reduce((sum, item) => sum + item.transferSize, 0)
            };
        }""")
        if performance["dom_content_loaded_ms"] > 5000:
            raise AssertionError("DOM content loaded exceeded 5s: " + json.dumps(performance))
        if performance["load_ms"] > 7000:
            raise AssertionError("Page load exceeded 7s: " + json.dumps(performance))
        if performance["transfer_bytes"] > 1_000_000:
            raise AssertionError("Initial resource transfer exceeded 1 MB: " + json.dumps(performance))
        assert page.locator("html").get_attribute("lang") == "fa"
        assert page.locator("html").get_attribute("dir") == "rtl"
        try:
            expect(page.locator("#engine-status span")).to_contain_text(
                "موتور API متصل است", timeout=10_000
            )
        except AssertionError as error:
            raise AssertionError(
                f"{error}; page_errors={page_errors}; console_errors={console_errors}; "
                f"api_route_hits={api_route_hits}; api_requests={api_requests}"
            ) from error
        assert page.locator(".mode-tab").count() == 2
        assert page.locator("#source-form").is_visible()
        assert_no_horizontal_overflow(page)
        advanced_summary_box = page.locator(".advanced-block summary").bounding_box()
        assert advanced_summary_box and advanced_summary_box["height"] >= 24, advanced_summary_box

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
        if browser_name == "chromium":
            result_accessibility = page.evaluate("""async () => {
                const result = await axe.run(document, {
                    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] }
                });
                return result.violations.map(item => ({id: item.id, impact: item.impact, help: item.help}));
            }""")
            if result_accessibility:
                raise AssertionError("Result view accessibility violations: " + json.dumps(
                    result_accessibility, ensure_ascii=False
                ))
        assert any(item["action"] == "verify_sources" for item in calls)
        assert any(item["authorization"] == "Bearer browser-e2e-key" for item in calls)
        assert page.evaluate(
            "() => localStorage.length === 0 && sessionStorage.length === 0"
        )

        page.locator("#copy-output").click()
        expect(page.locator("#copy-output")).to_have_text("کپی شد", timeout=5_000)
        with page.expect_download() as download_info:
            page.locator("#download-output").click()
        download = download_info.value
        assert download.suggested_filename == "article-finder-report.json"

        draft_tab = page.locator('[data-mode="draft"]')
        source_tab = page.locator('[data-mode="sources"]')
        source_tab.focus()
        page.keyboard.press("ArrowLeft")
        assert draft_tab.get_attribute("aria-selected") == "true"
        page.keyboard.press("ArrowRight")
        assert source_tab.get_attribute("aria-selected") == "true"
        draft_tab.focus()
        page.keyboard.press("Enter")
        assert draft_tab.get_attribute("aria-selected") == "true"
        assert page.locator("#draft-form").is_visible()
        if browser_name == "chromium":
            draft_accessibility = page.evaluate("""async () => {
                const result = await axe.run(document, {
                    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] }
                });
                return result.violations.map(item => ({id: item.id, impact: item.impact, help: item.help}));
            }""")
            if draft_accessibility:
                raise AssertionError("Draft view accessibility violations: " + json.dumps(
                    draft_accessibility, ensure_ascii=False
                ))
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
        "draft submission, API error state, copy/download controls, responsive layouts, "
        "WCAG 2.2 AA axe-core audit and performance budgets. "
        + json.dumps(performance, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
