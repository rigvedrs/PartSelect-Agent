"""Resolve canonical PartSelect product URLs from a PS number."""

from __future__ import annotations

import re
import time

from app.observability import get_logger
from scrapers.product_utils import clean_product_url

log = get_logger("scrapers.url_resolver")

_PS_RE = re.compile(r"^PS\d+$", re.I)


def resolve_product_url(ps_number: str) -> str | None:
    """Find the slug product URL via PartSelect site search (Selenium)."""
    ps = ps_number.strip().upper()
    if not _PS_RE.match(ps):
        return None

    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from scrapers import browser
    from scrapers.runtime_fetch import headless_driver

    try:
        with headless_driver() as driver:
            browser.navigate(driver, "https://www.partselect.com/")
            inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="search"]')
            if not inputs:
                log.warning("resolve_product_url no search input ps=%s", ps)
                return None
            inp = inputs[0]
            inp.clear()
            inp.send_keys(ps)
            inp.send_keys(Keys.RETURN)
            time.sleep(3)

            current = clean_product_url(driver.current_url)
            if current and ps in current.upper() and "error" not in (driver.title or "").lower():
                return current

            for anchor in driver.find_elements(By.CSS_SELECTOR, f"a[href*='/{ps}']"):
                href = clean_product_url(anchor.get_attribute("href") or "")
                if href and ps in href.upper():
                    return href
    except Exception:
        log.exception("resolve_product_url failed ps=%s", ps)
    return None
