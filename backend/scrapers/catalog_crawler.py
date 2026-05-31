"""Discover product URLs from PartSelect brand/subcategory pages (Dishwasher + Refrigerator)."""
from __future__ import annotations

import re
import time
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By

from scrapers import browser, io_utils

APPLIANCES = ("Dishwasher", "Refrigerator")
SITE = "https://www.partselect.com"


def _appliance_title(name: str) -> str:
    return name.strip().title()


def harvest_brands(driver: webdriver.Chrome, appliance: str) -> list[dict[str, str]]:
    slug = _appliance_title(appliance)
    entry = f"{SITE}/{slug}-Parts.htm"
    browser.navigate(driver, entry)
    pattern = f"-{slug}-Parts.htm"
    rows: dict[str, dict[str, str]] = {}
    for anchor in driver.find_elements(By.XPATH, f"//a[contains(@href,'{pattern}')]"):
        href = (anchor.get_attribute("href") or "").strip()
        label = (anchor.text or "").strip()
        if not href or not label:
            continue
        if not href.lower().endswith(f"-{slug.lower()}-parts.htm"):
            continue
        brand = re.sub(rf"\s*{slug}\s+Parts\s*$", "", label, flags=re.IGNORECASE).strip()
        if brand:
            rows[href] = {"appliance": slug, "brand": brand, "brand_url": href}
    return list(rows.values())


def harvest_subcategories(
    driver: webdriver.Chrome, brand: str, brand_url: str, appliance: str
) -> list[dict[str, str]]:
    slug = _appliance_title(appliance)
    browser.navigate(driver, brand_url)
    browser.brief_pause()
    href_fragment = f"/{brand.replace(' ', '-')}-{slug}-"
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in driver.find_elements(By.XPATH, f"//a[contains(@href, {repr(href_fragment)})]"):
        name = (anchor.text or "").strip()
        href = (anchor.get_attribute("href") or "").strip()
        if not name or not href:
            continue
        if any(skip in name or skip in href for skip in ("Models", "View More", "View more")):
            continue
        key = (name, href)
        if key in seen:
            continue
        seen.add(key)
        found.append({"name": name, "url": href})
    return found


def harvest_product_urls(driver: webdriver.Chrome, subcategory_url: str) -> list[str]:
    urls: set[str] = set()
    ps_re = re.compile(r"/PS\d+-.+\.htm")

    def collect() -> None:
        for anchor in driver.find_elements(
            By.XPATH,
            "//a[starts-with(@href,'/PS') or starts-with(@href,'https://www.partselect.com/PS')]",
        ):
            href = anchor.get_attribute("href") or ""
            if ps_re.search(href):
                urls.add(href.split("?")[0])

    browser.navigate(driver, subcategory_url)
    browser.brief_pause()
    collect()
    for _ in range(40):
        next_links = driver.find_elements(
            By.XPATH, "//a[normalize-space()='Next' and not(@aria-disabled='true')]"
        )
        if not next_links:
            break
        try:
            driver.execute_script("arguments[0].click();", next_links[0])
        except Exception:
            try:
                next_links[0].click()
            except Exception:
                break
        time.sleep(0.5)
        collect()
    return sorted(urls)


def run_catalog(
    driver: webdriver.Chrome,
    *,
    do_brands: bool = True,
    do_subcats: bool = True,
    do_products: bool = True,
) -> dict[str, Any]:
    io_utils.ensure_dirs()
    stats: dict[str, Any] = {}

    if do_brands:
        brands: list[dict] = []
        for app in APPLIANCES:
            batch = harvest_brands(driver, app)
            stats[f"brands_{app}"] = len(batch)
            brands.extend(batch)
        io_utils.write_json(io_utils.BRANDS_FILE, brands)
        stats["brands_total"] = len(brands)

    if do_subcats:
        brands = io_utils.read_json(io_utils.BRANDS_FILE, [])
        tree: list[dict] = []
        for idx, entry in enumerate(brands, 1):
            subs = harvest_subcategories(
                driver, entry["brand"], entry["brand_url"], entry["appliance"]
            )
            tree.append({**entry, "subcategories": subs})
            time.sleep(0.25)
        io_utils.write_json(io_utils.SUBCATS_FILE, tree)
        stats["subcategory_groups"] = len(tree)

    if do_products:
        tree = io_utils.read_json(io_utils.SUBCATS_FILE, [])
        done = io_utils.load_checkpoint(io_utils.SUBCAT_CHECKPOINT)
        total = sum(len(g.get("subcategories") or []) for g in tree)
        processed = 0
        for group in tree:
            app = group["appliance"]
            brand = group["brand"]
            for sub in group.get("subcategories") or []:
                processed += 1
                url = sub["url"]
                if url in done:
                    continue
                try:
                    links = harvest_product_urls(driver, url)
                    for product_url in links:
                        io_utils.append_jsonl(
                            io_utils.PRODUCT_LINKS,
                            {
                                "appliance": app,
                                "brand": brand,
                                "subcategory_name": sub["name"],
                                "subcategory_url": url,
                                "product_url": product_url,
                            },
                        )
                    io_utils.mark_checkpoint(io_utils.SUBCAT_CHECKPOINT, url)
                    done.add(url)
                    time.sleep(0.25)
                except Exception as exc:
                    stats.setdefault("subcat_errors", []).append({url: str(exc)})
        stats["subcategories_total"] = total
        stats["product_link_rows"] = sum(1 for _ in io_utils.iter_jsonl(io_utils.PRODUCT_LINKS))

    return stats
