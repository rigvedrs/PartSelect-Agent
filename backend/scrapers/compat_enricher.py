"""Add main_image and model_cross_reference to product detail records."""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers import browser, io_utils


def _hero_image(driver: webdriver.Chrome) -> str | None:
    try:
        anchor = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.ID, "MagicZoom-PartImage-Images"))
        )
        return anchor.get_attribute("href")
    except Exception:
        try:
            anchor = driver.find_element(By.CSS_SELECTOR, ".MagicZoom-PartImage a[href]")
            return anchor.get_attribute("href")
        except Exception:
            return None


def _expand_crossref(driver: webdriver.Chrome) -> bool:
    try:
        title = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.ID, "ModelCrossReference"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title)
        if title.get_attribute("aria-expanded") != "true":
            title.click()
            WebDriverWait(driver, 8).until(
                lambda d: title.get_attribute("aria-expanded") == "true"
            )
        return True
    except TimeoutException:
        return False


def _load_crossref_rows(driver: webdriver.Chrome) -> list[dict]:
    if not _expand_crossref(driver):
        return []
    try:
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".pd__crossref__list.js-dataContainer.js-infiniteScroll")
            )
        )
    except TimeoutException:
        return []

    stalls = 0
    prev = len(container.find_elements(By.CSS_SELECTOR, ":scope > .row"))
    while True:
        try:
            load_more = container.find_element(By.CSS_SELECTOR, ".js-loadNext")
        except NoSuchElementException:
            break
        driver.execute_script("arguments[0].click();", load_more)
        time.sleep(0.25)
        curr = len(container.find_elements(By.CSS_SELECTOR, ":scope > .row"))
        if curr <= prev:
            stalls += 1
            if stalls >= 2:
                break
        else:
            stalls = 0
            prev = curr

    rows: list[dict] = []
    for row in container.find_elements(By.CSS_SELECTOR, ":scope > .row"):
        try:
            brand = ""
            try:
                brand = row.find_element(By.CSS_SELECTOR, ".col-6.col-md-3").text.strip()
            except NoSuchElementException:
                pass
            model_number = ""
            model_url = ""
            try:
                link = row.find_element(By.CSS_SELECTOR, "a[rel='nofollow']")
                model_number = link.text.strip()
                model_url = link.get_attribute("href") or ""
            except NoSuchElementException:
                pass
            description = ""
            try:
                desc_el = row.find_element(By.CSS_SELECTOR, ".col.col-md-6.col-lg-7")
                description = " ".join(desc_el.text.split())
            except NoSuchElementException:
                pass
            if brand or model_number or description:
                rows.append(
                    {
                        "brand": brand,
                        "model_number": model_number,
                        "model_url": model_url,
                        "description": description,
                    }
                )
        except Exception:
            continue
    return rows


def enrich_record(driver: webdriver.Chrome, record: dict) -> dict:
    url = record.get("product_url")
    if not url:
        record["main_image"] = None
        record["model_cross_reference"] = []
        return record
    browser.navigate(driver, url)
    time.sleep(0.35 + random.random() * 0.25)
    record["main_image"] = _hero_image(driver)
    record["model_cross_reference"] = _load_crossref_rows(driver)
    return record


def run_enrichment(
    driver: webdriver.Chrome,
    *,
    input_jsonl: Path | None = None,
    output_jsonl: Path | None = None,
    limit: int | None = None,
    pause_s: float = 0.15,
) -> dict[str, int]:
    io_utils.ensure_dirs()
    input_jsonl = input_jsonl or io_utils.DETAILS_JSONL
    output_jsonl = output_jsonl or io_utils.ENRICHED_JSONL
    done = io_utils.urls_from_jsonl(output_jsonl)
    stats = {"written": 0, "skipped": 0, "failed": 0}

    with output_jsonl.open("a", encoding="utf-8") as out_f:
        for row in io_utils.iter_jsonl(input_jsonl):
            url = (row.get("product_url") or "").strip()
            if not url or url in done:
                stats["skipped"] += 1
                continue
            if limit is not None and stats["written"] >= limit:
                break
            try:
                enriched = enrich_record(driver, dict(row))
                out_f.write(json.dumps(enriched, ensure_ascii=False) + "\n")
                out_f.flush()
                done.add(url)
                stats["written"] += 1
            except Exception:
                stats["failed"] += 1
            if pause_s:
                time.sleep(pause_s)
    return stats
