"""Runtime page fetch for chat fallbacks — Selenium (free) with optional Firecrawl."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from app.observability import get_logger

log = get_logger("scrapers.runtime_fetch")

# PartSelect blocks simple HTTP clients (Akamai). Selenium uses a real browser.
_DEFAULT_BACKEND = "selenium"


def live_scrape_backend() -> str:
    """selenium (default, free) or firecrawl when explicitly configured + keyed."""
    backend = os.getenv("LIVE_SCRAPE_BACKEND", _DEFAULT_BACKEND).strip().lower()
    if backend == "firecrawl" and os.getenv("FIRECRAWL_API_KEY"):
        return "firecrawl"
    return "selenium"


def live_scrape_available() -> bool:
    """True when runtime live lookup can run (Selenium is always attempted locally)."""
    return live_scrape_backend() in ("selenium", "firecrawl")


@contextmanager
def headless_driver() -> Iterator:
    from scrapers import browser

    driver = browser.build_chrome(headless=True)
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def fetch_markdown(url: str) -> str:
    """Page text for legacy markdown parsers. Prefer DOM-specific scrapers when possible."""
    if live_scrape_backend() == "firecrawl":
        from scrapers.firecrawl_client import scrape_markdown as fc_md
        return fc_md(url)

    from selenium.webdriver.common.by import By
    from scrapers import browser

    with headless_driver() as driver:
        browser.navigate(driver, url)
        return driver.find_element(By.TAG_NAME, "body").text or ""
