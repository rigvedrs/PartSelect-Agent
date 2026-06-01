"""Runtime page fetch for chat fallbacks — Selenium (free) with optional Firecrawl."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.observability import get_logger

log = get_logger("scrapers.runtime_fetch")


def live_scrape_backend() -> str:
    """selenium or firecrawl — reads config.toml [live_scrape] with env override."""
    from app.live_scrape import settings as live_settings

    if not live_settings.is_enabled():
        return "selenium"
    return live_settings.resolve_backend()


def live_scrape_available() -> bool:
    """True when live scrape is enabled and the configured backend can run."""
    from app.live_scrape import settings as live_settings

    return live_settings.is_available()


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
