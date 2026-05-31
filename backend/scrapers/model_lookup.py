"""Best-effort live lookup of parts for an appliance model."""
from __future__ import annotations

import re

from app.observability import get_logger

log = get_logger("scrapers.model_lookup")

_MODEL_URL = "https://www.partselect.com/Models/{model}/"
_PS_IN_HREF = re.compile(r"/(PS\d{5,})", re.IGNORECASE)


def model_page_url(model: str) -> str:
    return _MODEL_URL.format(model=model.strip().upper())


def _query_keywords(part_query: str | None) -> list[str]:
    if not part_query:
        return []
    from app.agent.tools.search_parts import _extract_keywords
    return [w for w in _extract_keywords(part_query).split() if len(w) > 2]


def _filter_entries(entries: list[dict], kws: list[str]) -> list[dict]:
    if not kws:
        return entries
    names = [(e, e["name"].lower()) for e in entries]
    and_hits = [e for e, n in names if all(k in n for k in kws)]
    if and_hits:
        return and_hits
    or_hits = [e for e, n in names if any(k in n for k in kws)]
    return or_hits


def parse_product_links_from_markdown(md: str) -> list[dict]:
    """Extract parts from Firecrawl markdown (legacy)."""
    from scrapers.product_utils import clean_product_url

    _NESTED = re.compile(
        r"\[!\[([^\]]+)\]\([^)]*\)\]\((https?://(?:www\.)?partselect\.com/(PS\d+)[^)]*)\)",
        re.IGNORECASE,
    )
    _PLAIN = re.compile(
        r"(?<!\[)\[([^\]]+)\]\((https?://(?:www\.)?partselect\.com/(PS\d+)[^)]*)\)",
        re.IGNORECASE,
    )
    entries: list[dict] = []
    seen: set[str] = set()

    def _add(name: str, raw_url: str, ps: str) -> None:
        name = name.strip()
        if not name or "base64" in name.lower():
            return
        ps_upper = ps.upper()
        if ps_upper in seen:
            return
        seen.add(ps_upper)
        entries.append({
            "ps_number": ps_upper,
            "name": name,
            "product_url": clean_product_url(raw_url) or raw_url,
        })

    for name, raw_url, ps in _NESTED.findall(md):
        _add(name, raw_url, ps)
    for name, raw_url, ps in _PLAIN.findall(md):
        _add(name, raw_url, ps)
    return entries


def _parse_model_page_dom(driver) -> list[dict]:
    """Parse product links from a loaded PartSelect model page (Selenium DOM)."""
    from selenium.webdriver.common.by import By
    from scrapers.product_utils import clean_product_url

    entries: list[dict] = []
    seen: set[str] = set()

    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href*='/PS']"):
        href = (anchor.get_attribute("href") or "").strip()
        m = _PS_IN_HREF.search(href)
        if not m:
            continue
        ps = m.group(1).upper()
        if ps in seen:
            continue
        name = (
            (anchor.get_attribute("title") or "").strip()
            or (anchor.text or "").strip()
            or (anchor.get_attribute("aria-label") or "").strip()
        )
        if not name or "base64" in name.lower() or len(name) < 3:
            img = anchor.find_elements(By.CSS_SELECTOR, "img[alt]")
            if img:
                name = (img[0].get_attribute("alt") or "").strip()
        if not name or "base64" in name.lower():
            continue
        seen.add(ps)
        entries.append({
            "ps_number": ps,
            "name": name,
            "product_url": clean_product_url(href) or href,
        })
    return entries


def _scrape_model_parts_selenium(model: str) -> list[dict]:
    from scrapers import browser
    from scrapers.runtime_fetch import headless_driver

    with headless_driver() as driver:
        browser.navigate(driver, model_page_url(model))
        return _parse_model_page_dom(driver)


def scrape_model_parts(model: str, part_query: str | None = None) -> list[dict]:
    """Return parts listed on a model page as {ps_number, name, product_url}."""
    from scrapers.runtime_fetch import live_scrape_available, live_scrape_backend, fetch_markdown

    if not live_scrape_available():
        return []

    try:
        if live_scrape_backend() == "selenium":
            entries = _scrape_model_parts_selenium(model)
        else:
            md = fetch_markdown(model_page_url(model))
            if not md:
                return []
            entries = parse_product_links_from_markdown(md)
    except Exception:
        log.exception("model page scrape failed model=%s", model)
        return []

    kws = _query_keywords(part_query)
    if kws:
        filtered = _filter_entries(entries, kws)
        log.info(
            "model_lookup model=%s keyword=%r hits=%d/%d backend=%s",
            model, kws, len(filtered), len(entries), live_scrape_backend(),
        )
        return filtered

    log.info(
        "model_lookup model=%s parts=%d backend=%s",
        model, len(entries), live_scrape_backend(),
    )
    return entries


def scrape_model_part_numbers(model: str, part_query: str | None = None) -> list[str]:
    return [e["ps_number"] for e in scrape_model_parts(model, part_query)]


def model_lists_part(model: str, ps_number: str) -> bool | None:
    found = scrape_model_part_numbers(model)
    if not found:
        return None
    return ps_number.upper() in found
