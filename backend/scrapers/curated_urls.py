"""Build a smaller product_links_deduped.jsonl for smoke tests and incremental scrape."""
from __future__ import annotations

import argparse
import json
import sys

from scrapers import browser, catalog_crawler, io_utils
from scrapers.model_lookup import model_page_url, _parse_model_page_dom

CASE_STUDY_PS = "PS11752778"
CASE_STUDY_MODEL = "WDT780SAEM1"
PER_SUBCAT_LIMIT = 12

REFRIGERATOR_SUBCAT_KEYWORDS = [
    "ice maker", "door", "water filter", "control board",
]
DISHWASHER_SUBCAT_KEYWORDS = [
    "pump", "spray arm", "door latch", "filter",
]


def _ps_product_url(ps: str) -> str:
    return f"https://www.partselect.com/{ps.upper()}-Part.htm"


def _collect_model_parts(driver, model: str) -> list[dict]:
    from scrapers.model_lookup import _expand_model_page

    browser.navigate(driver, model_page_url(model))
    _expand_model_page(driver)
    entries = _parse_model_page_dom(driver)
    return [{
        "product_url": e["product_url"],
        "source": "model_page",
        "model_number": model.upper(),
        "ps_number": e["ps_number"],
    } for e in entries]


def _match_subcategories(tree: list[dict], appliance: str, keywords: list[str]) -> list[dict]:
    hits: list[dict] = []
    for group in tree:
        if group.get("appliance", "").lower() != appliance.lower():
            continue
        for sub in group.get("subcategories") or []:
            name = (sub.get("name") or "").lower()
            if any(kw in name for kw in keywords):
                hits.append({**sub, "appliance": group["appliance"], "brand": group["brand"]})
    return hits


def _collect_subcat_urls(driver, sub: dict, limit: int) -> list[dict]:
    urls = catalog_crawler.harvest_product_urls(driver, sub["url"])[:limit]
    return [{
        "product_url": u,
        "source": "subcategory",
        "subcategory": sub.get("name"),
        "appliance": sub.get("appliance"),
        "brand": sub.get("brand"),
    } for u in urls]


def _build_subcategory_tree(driver) -> list[dict]:
    tree: list[dict] = []
    for app in ("Refrigerator", "Dishwasher"):
        for entry in catalog_crawler.harvest_brands(driver, app)[:2]:
            subs = catalog_crawler.harvest_subcategories(
                driver, entry["brand"], entry["brand_url"], entry["appliance"],
            )
            tree.append({**entry, "subcategories": subs})
    return tree


def build_curated_urls(*, headless: bool = True) -> dict:
    """Write product_links_deduped.jsonl from case-study PS, model page, and sub-categories."""
    io_utils.ensure_dirs()
    out = io_utils.CATALOG_DIR / "product_links_deduped.jsonl"
    seen: set[str] = set()
    rows: list[dict] = []
    model_part_count = 0

    def add(row: dict) -> None:
        url = (row.get("product_url") or "").strip().split("?")[0]
        if not url or url in seen:
            return
        seen.add(url)
        rows.append({**row, "product_url": url})

    driver = browser.build_chrome(headless=headless)
    try:
        add({"product_url": _ps_product_url(CASE_STUDY_PS), "source": "case_study"})
        for row in _collect_model_parts(driver, CASE_STUDY_MODEL):
            model_part_count += 1
            add(row)

        tree = io_utils.read_json(io_utils.SUBCATS_FILE, [])
        if not tree:
            tree = _build_subcategory_tree(driver)

        for sub in _match_subcategories(tree, "Refrigerator", REFRIGERATOR_SUBCAT_KEYWORDS):
            for row in _collect_subcat_urls(driver, sub, PER_SUBCAT_LIMIT):
                add(row)

        for sub in _match_subcategories(tree, "Dishwasher", DISHWASHER_SUBCAT_KEYWORDS):
            for row in _collect_subcat_urls(driver, sub, PER_SUBCAT_LIMIT):
                add(row)
    finally:
        driver.quit()

    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    for path in (
        io_utils.DETAILS_JSONL,
        io_utils.ENRICHED_JSONL,
        io_utils.DETAILS_CHECKPOINT,
        io_utils.DETAILS_FAILED,
    ):
        if path.exists():
            path.unlink()

    return {
        "urls": len(rows),
        "model_parts": model_part_count,
        "output": str(out),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build curated product URL list for smoke scrape")
    parser.add_argument("--no-headless", dest="headless", action="store_false", default=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_curated_urls(headless=args.headless), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
