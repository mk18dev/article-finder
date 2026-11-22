#!/usr/bin/env python3
"""Real-browser responsive and interaction smoke test for the local workspace."""
from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("ARTICLE_FINDER_BASE_URL", "http://127.0.0.1:8000")


def assert_no_horizontal_overflow(page) -> None:
    dimensions = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth})"
    )
    if dimensions["scroll"] > dimensions["client"]:
        raise AssertionError(f"horizontal overflow: {dimensions}")


def main() -> int:
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = page.goto(BASE_URL, wait_until="networkidle", timeout=20_000)
        assert response is not None and response.status == 200
        assert page.locator("html").get_attribute("lang") == "fa"
        assert page.locator("html").get_attribute("dir") == "rtl"
        page.wait_for_function("document.querySelector('#engine-status span')?.textContent.includes('موتور API متصل است')", timeout=10_000)
        assert page.locator(".mode-tab").count() == 2
        assert page.locator("#source-form").is_visible()
        assert_no_horizontal_overflow(page)

        page.locator('[data-mode="draft"]').click()
        assert page.locator("#draft-form").is_visible()
        assert not page.locator("#source-form").is_visible()
        assert page.locator("#draft-text").is_visible()
        assert_no_horizontal_overflow(page)

        page.set_viewport_size({"width": 320, "height": 700})
        assert_no_horizontal_overflow(page)
        page.locator('[data-mode="sources"]').click()
        assert page.locator("#source-form").is_visible()
        assert_no_horizontal_overflow(page)

        page.set_viewport_size({"width": 1440, "height": 900})
        assert_no_horizontal_overflow(page)
        if page_errors:
            raise AssertionError("browser page errors: " + "; ".join(page_errors))
        browser.close()
    print("Browser smoke passed: RTL, source/draft mode switching, 320px mobile, 390px mobile and desktop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
