"""Extract structured product fields from PartSelect product detail pages."""
from __future__ import annotations

import json
import re
import time
import traceback
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers import browser, io_utils

PS_URL_RE = re.compile(r"https://www\.partselect\.com/PS\d+")


def _squash(text: str | None) -> str | None:
    if not text:
        return text
    s = re.sub(r"[ \t]+", " ", text)
    s = re.sub(r"\r?\n\s*", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _dt_value(driver: webdriver.Chrome, labels: list[str]) -> str | None:
    for label in labels:
        xp = (
            f"//dt[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
            f"'abcdefghijklmnopqrstuvwxyz'))={repr(label.lower())}]/following-sibling::dd[1]"
        )
        hits = driver.find_elements(By.XPATH, xp)
        if hits and hits[0].text.strip():
            return _squash(hits[0].text.strip())
    return None


def _price(driver: webdriver.Chrome) -> str | None:
    from scrapers.product_utils import normalize_price, parse_product_price

    for css in ("meta[itemprop='price']", "span[itemprop='price']", "span.price", "div.price"):
        for el in driver.find_elements(By.CSS_SELECTOR, css):
            raw = (el.get_attribute("content") or el.text or "").strip()
            if raw:
                parsed = normalize_price(raw)
                if parsed:
                    return parsed
                m = re.search(r"\$?\s*\d[\d,]*\.?\d*", raw)
                if m:
                    return normalize_price(m.group(0))

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        parsed = parse_product_price(body_text)
        if parsed:
            return parsed
    except Exception:
        pass
    return None


def _availability(driver: webdriver.Chrome) -> str | None:
    texts: list[str] = []
    for css in ("div.availability", "span.availability", "div.stock-status", "div#availability"):
        for el in driver.find_elements(By.CSS_SELECTOR, css):
            if el.text.strip():
                texts.append(_squash(el.text.strip()) or "")
    for el in driver.find_elements(
        By.XPATH, "//*[contains(.,'In Stock') or contains(.,'On Order') or contains(.,'Backorder')]"
    ):
        if el.text.strip():
            texts.append(_squash(el.text.strip()) or "")
    return min(texts, key=len) if texts else None


def _partselect_number(driver: webdriver.Chrome) -> str | None:
    for el in driver.find_elements(By.CSS_SELECTOR, "[itemprop='productID']"):
        if el.text.strip():
            return el.text.strip()
    try:
        el = driver.find_element(By.XPATH, "//*[contains(., 'PartSelect Number')]/following::*[1]")
        t = el.text.strip()
        return t if t.upper().startswith("PS") else None
    except Exception:
        return None


def _mpn(driver: webdriver.Chrome) -> str | None:
    for el in driver.find_elements(By.CSS_SELECTOR, "[itemprop='mpn']"):
        if el.text.strip():
            return el.text.strip()
    return _dt_value(driver, ["Manufacturer Part Number", "Mfr Part Number", "MPN"])


def _manufacturer(driver: webdriver.Chrome) -> str | None:
    try:
        return driver.find_element(
            By.CSS_SELECTOR, "[itemprop='brand'] [itemprop='name']"
        ).text.strip()
    except Exception:
        return _dt_value(driver, ["Manufacturer", "Brand"])


def _manufactured_for(driver: webdriver.Chrome) -> str | None:
    try:
        line = driver.find_element(
            By.XPATH,
            "//div[contains(@class,'mb-2')][contains(normalize-space(.), 'Manufactured by')]",
        ).text.strip()
        m = re.search(r"\bfor\s+(.+)$", line, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
        rest = re.sub(r"^Manufactured by\s+\S+\s*", "", line, flags=re.IGNORECASE).strip()
        if "," in rest:
            return rest
    except Exception:
        pass
    return None


def _description(driver: webdriver.Chrome) -> str | None:
    for el in driver.find_elements(By.XPATH, "//*[@itemprop='description' and normalize-space()]"):
        if el.is_displayed() and el.text.strip():
            return _squash(re.split(r"(?i)\bwhy buy\b", el.text.strip())[0])

    trigger = None
    for xp in (
        "//*[@id='ProductDescription']",
        "//*[@data-handle='contentDesc' and @data-collapse-trigger]",
        "//*[contains(@class,'section-title') and contains(normalize-space(.), 'Product Description')]",
    ):
        hits = driver.find_elements(By.XPATH, xp)
        if hits:
            trigger = hits[0]
            break

    container = None
    if trigger:
        try:
            container = trigger.find_element(
                By.XPATH,
                "following-sibling::*[@data-collapse-container or @data-collapsible][1]",
            )
        except Exception:
            container = None
        if container:
            try:
                node = container.find_element(
                    By.XPATH, ".//*[@itemprop='description' and normalize-space()]"
                )
                if node.text.strip():
                    return _squash(re.split(r"(?i)\bwhy buy\b", node.text.strip())[0])
            except Exception:
                pass
            try:
                left = container.find_element(By.CSS_SELECTOR, ".col-lg-8, .col-md-8, .col-8")
                if left.text.strip():
                    return _squash(re.split(r"(?i)\bwhy buy\b", left.text.strip())[0])
            except Exception:
                pass
            if container.text.strip():
                return _squash(re.split(r"(?i)\bwhy buy\b", container.text.strip())[0])

    try:
        block = driver.find_element(
            By.CSS_SELECTOR, ".pd__description, .pd_description, .pd__description__col_wrap"
        )
        if block.text.strip():
            return _squash(re.split(r"(?i)\bwhy buy\b", block.text.strip())[0])
    except Exception:
        pass

    paras = [
        p.text.strip()
        for p in driver.find_elements(By.CSS_SELECTOR, "article p, .pd__description p, .description p")
        if p.text.strip()
    ]
    if paras:
        return _squash(re.split(r"(?i)\bwhy buy\b", max(paras[:6], key=len))[0])
    return None


def _youtube_watch_url(url_or_id: str) -> str | None:
    if not url_or_id:
        return None
    m = re.search(r"/embed/([A-Za-z0-9_-]{6,})", url_or_id)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})", url_or_id)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", url_or_id.strip()):
        return f"https://www.youtube.com/watch?v={url_or_id.strip()}"
    return None


def _youtube_link_from_page(driver: webdriver.Chrome) -> str | None:
    """Extract a YouTube watch URL from page HTML — link only, no video download or UI expand."""
    html = driver.page_source or ""

    for pattern in (
        r"https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})",
        r"https?://(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{6,})",
        r"https?://youtu\.be/([A-Za-z0-9_-]{6,})",
        r"img\.youtube\.com/vi/([A-Za-z0-9_-]{6,})/",
        r'data-yt-init="([A-Za-z0-9_-]{6,})"',
        r"data-yt=\"([A-Za-z0-9_-]{6,})\"",
    ):
        m = re.search(pattern, html)
        if m:
            watch = _youtube_watch_url(m.group(1))
            if watch:
                return watch

    # Fallback: collapsed PartVideos section (no long wait / no click)
    try:
        for fr in driver.find_elements(By.CSS_SELECTOR, "iframe[src*='youtube'], iframe[src*='youtu.be']"):
            watch = _youtube_watch_url(fr.get_attribute("src") or "")
            if watch:
                return watch
    except Exception:
        pass
    return None


def _symptoms_and_replaces(driver: webdriver.Chrome) -> dict[str, list[str] | None]:
    out: dict[str, list[str] | None] = {"symptoms": None, "replaces": None}

    def norm(s: str) -> str:
        return re.sub(r"[ \t]+", " ", (s or "").replace("\xa0", " ")).strip()

    container = None
    try:
        trig = driver.find_element(By.XPATH, "//*[@id='Troubleshooting' and @data-collapse-trigger]")
        container = trig.find_element(By.XPATH, "following-sibling::*[@data-collapsible][1]")
    except Exception:
        try:
            container = driver.find_element(
                By.XPATH,
                "//div[contains(@class,'pd__wrap') and contains(@class,'row') and @data-collapsible]",
            )
        except Exception:
            return out

    try:
        ul = container.find_element(
            By.XPATH,
            ".//div[contains(@class,'bold') and contains(normalize-space(.), "
            "'fixes the following symptoms')]/following-sibling::ul[1]",
        )
        items = [norm(li.text) for li in ul.find_elements(By.TAG_NAME, "li") if norm(li.text)]
        out["symptoms"] = items or None
    except Exception:
        pass

    try:
        rep = container.find_element(
            By.XPATH,
            ".//div[contains(@class,'bold') and contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'replaces these')]"
            "/following-sibling::*[1]",
        )
        txt = norm(rep.text) or norm(rep.get_attribute("textContent") or "")
        if txt:
            tokens = [t.strip(" ,") for t in re.split(r"[,\s]+", txt) if t.strip()]
            parts = [t for t in tokens if re.search(r"[A-Za-z]\d", t)]
            seen: set[str] = set()
            uniq = []
            for p in parts:
                if p not in seen:
                    seen.add(p)
                    uniq.append(p)
            out["replaces"] = uniq or None
    except Exception:
        pass
    return out


def _installation_meta(driver: webdriver.Chrome) -> dict[str, str | None]:
    result = {"installation_complexity": None, "installation_time": None}
    try:
        box = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.pd__repair-rating__container"))
        )
    except TimeoutException:
        return result
    vals = [
        re.sub(r"[ \t]+", " ", (p.text or "").replace("\xa0", " ").replace("–", "-").replace("—", "-")).strip()
        for p in box.find_elements(By.CSS_SELECTOR, "p.bold")
        if p.text.strip()
    ]
    if vals:
        result["installation_complexity"] = vals[0]
    if len(vals) > 1:
        result["installation_time"] = vals[1]
    return result


def _reviews(driver: webdriver.Chrome) -> dict[str, float | int | None]:
    rating_value = None
    try:
        el = driver.find_element(By.CSS_SELECTOR, ".pd__cust-review__header__rating__chart--border")
        raw = (el.text or el.get_attribute("textContent") or "").strip()
        m = re.search(r"\d+(\.\d+)?", raw)
        if m:
            rating_value = float(m.group(0))
    except Exception:
        pass
    if rating_value is None:
        try:
            upper = driver.find_element(By.CSS_SELECTOR, ".rating__stars__upper[style*='width']")
            m = re.search(r"width\s*:\s*([\d.]+)\s*%", upper.get_attribute("style") or "")
            if m:
                rating_value = round(float(m.group(1)) / 100.0 * 5.0, 1)
        except Exception:
            pass
    rating_count = None
    try:
        span = driver.find_element(By.CSS_SELECTOR, ".pd__cust-review__header__rating .rating__count")
        m = re.search(r"\d[\d,]*", span.text.strip())
        if m:
            rating_count = int(m.group(0).replace(",", ""))
    except Exception:
        pass
    return {"rating_value": rating_value, "rating_count": rating_count}


def extract_product_record(driver: webdriver.Chrome, url: str) -> dict[str, Any]:
    from scrapers.product_utils import clean_product_url

    url = clean_product_url(url) or url
    browser.navigate(driver, url)
    title = None
    for css in ("h1.product-title", "h1#page-title", "h1[itemprop='name']", "h1"):
        hits = driver.find_elements(By.CSS_SELECTOR, css)
        if hits:
            title = _squash(hits[0].text)
            break
    sym = _symptoms_and_replaces(driver)
    reviews = _reviews(driver)
    install = _installation_meta(driver)
    return {
        "product_url": url,
        "name": title,
        "price": _price(driver),
        "availability": _availability(driver),
        "partselect_number": _partselect_number(driver),
        "manufacturer_part_number": _mpn(driver),
        "manufacturer": _manufacturer(driver),
        "manufactured_for": _manufactured_for(driver),
        "description": _description(driver),
        "replaces": sym["replaces"],
        "video_url": _youtube_link_from_page(driver),
        "installation_complexity": install["installation_complexity"],
        "installation_time": install["installation_time"],
        "symptoms": sym["symptoms"],
        "rating_value": reviews["rating_value"],
        "rating_count": reviews["rating_count"],
    }


def ps_url_from_number(ps_number: str) -> str:
    ps = ps_number.upper()
    if not ps.startswith("PS"):
        ps = f"PS{ps}"
    return f"https://www.partselect.com/{ps}.htm"


def run_details_batch(
    driver: webdriver.Chrome,
    *,
    input_jsonl: Path | None = None,
    output_jsonl: Path | None = None,
    limit: int | None = None,
    rotate_every: int = 40,
    pause_s: float = 0.05,
) -> dict[str, int]:
    io_utils.ensure_dirs()
    input_jsonl = input_jsonl or io_utils.PRODUCT_LINKS
    output_jsonl = output_jsonl or io_utils.DETAILS_JSONL
    done = io_utils.load_checkpoint(io_utils.DETAILS_CHECKPOINT) | io_utils.urls_from_jsonl(
        output_jsonl
    )
    stats = {"processed": 0, "skipped": 0, "failed": 0, "written": 0}
    seen_in = 0

    with output_jsonl.open("a", encoding="utf-8") as out_f, io_utils.DETAILS_CHECKPOINT.open(
        "a", encoding="utf-8"
    ) as idx_f, io_utils.DETAILS_FAILED.open("a", encoding="utf-8") as fail_f:
        for row in io_utils.iter_jsonl(input_jsonl):
            from scrapers.product_utils import clean_product_url

            url = clean_product_url((row.get("product_url") or "").strip()) or ""
            if not url:
                continue
            seen_in += 1
            if limit is not None and stats["processed"] + stats["skipped"] >= limit:
                break
            if url in done:
                stats["skipped"] += 1
                continue
            stats["processed"] += 1
            if rotate_every and stats["written"] and stats["written"] % rotate_every == 0:
                driver.quit()
                driver = browser.build_chrome(headless=True)
            try:
                record = extract_product_record(driver, url)
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                idx_f.write(url + "\n")
                idx_f.flush()
                done.add(url)
                stats["written"] += 1
            except Exception:
                fail_f.write(url + "\n")
                fail_f.flush()
                stats["failed"] += 1
                traceback.print_exc()
            if pause_s:
                time.sleep(pause_s)
    stats["input_seen"] = seen_in
    return stats
