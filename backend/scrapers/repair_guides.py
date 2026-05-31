"""Scrape PartSelect repair symptom guides for dishwasher and refrigerator."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers import browser, io_utils

BASE = "https://www.partselect.com"
REPAIR_ROOTS = {
    "Dishwasher": f"{BASE}/Repair/Dishwasher/",
    "Refrigerator": f"{BASE}/Repair/Refrigerator/",
}
SKIP_HEADINGS = (
    "how to fix a",
    "start your repair",
    "need help finding",
    "symptom list",
    "related",
    "other symptoms",
)


def _normalize_text(text: str) -> str:
    t = re.sub(r"\r?\n\s*", "\n", text)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _symptom_links(driver: webdriver.Chrome, root_url: str) -> list[str]:
    browser.navigate(driver, root_url)
    root_path = urlparse(root_url).path
    if not root_path.endswith("/"):
        root_path += "/"
    links: set[str] = set()
    for anchor in driver.find_elements(By.CSS_SELECTOR, f"a[href*='{root_path}']"):
        href = anchor.get_attribute("href") or ""
        if not href:
            continue
        path = urlparse(href).path.rstrip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "Repair" and path.startswith(root_path.rstrip("/")):
            links.add(urljoin(BASE, path + "/"))
    return sorted(links)


def _gather_block_text(element) -> str:
    chunks: list[str] = []
    for p in element.find_elements(By.CSS_SELECTOR, "p"):
        if p.text.strip():
            chunks.append(p.text.strip())
    for li in element.find_elements(By.CSS_SELECTOR, "li"):
        if li.text.strip():
            chunks.append(li.text.strip())
    if not chunks:
        block = element.text.strip()
        if block:
            chunks.append(block)
    return _normalize_text("\n".join(chunks))


def _parse_symptom_page(driver: webdriver.Chrome, url: str, item_name: str) -> list[dict]:
    browser.navigate(driver, url)
    try:
        browser.wait_for_body(driver, 20)
    except TimeoutException:
        return []
    driver.execute_script("window.scrollTo(0, 150)")
    time.sleep(0.5)
    symptom = url.rstrip("/").split("/")[-1].replace("-", " ").title()
    records: list[dict] = []
    for desc in driver.find_elements(By.CSS_SELECTOR, "div.symptom-list__desc"):
        part = None
        try:
            heading = desc.find_element(
                By.XPATH, "preceding-sibling::h2[1] | preceding-sibling::h3[1]"
            )
            part = heading.text.strip()
        except NoSuchElementException:
            try:
                heading = desc.find_element(
                    By.XPATH, "ancestor::*/*[self::h2 or self::h3][1]"
                )
                part = heading.text.strip()
            except NoSuchElementException:
                continue
        if not part or any(k in part.lower() for k in SKIP_HEADINGS):
            continue
        text = _gather_block_text(desc)
        if text:
            records.append({"item": item_name, "symptom": symptom, "part": part, "text": text})
    return records


def scrape_appliance(driver: webdriver.Chrome, item_name: str, root_url: str) -> list[dict]:
    out: list[dict] = []
    for link in _symptom_links(driver, root_url):
        try:
            out.extend(_parse_symptom_page(driver, link, item_name))
            time.sleep(0.7)
        except Exception:
            continue
    return out


def run_repairs(driver: webdriver.Chrome, out_path: Path | None = None) -> int:
    io_utils.ensure_dirs()
    out_path = out_path or io_utils.REPAIR_WORK / "repairs_merged.jsonl"
    all_rows: list[dict] = []
    for item, root in REPAIR_ROOTS.items():
        all_rows.extend(scrape_appliance(driver, item, root))

    seen: set[tuple] = set()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            key = (row["symptom"].lower(), row["part"].lower(), row["text"][:80])
            if key in seen:
                continue
            seen.add(key)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(seen)
