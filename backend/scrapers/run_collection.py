"""CLI orchestrator for the PartSelect scraping pipeline."""
from __future__ import annotations

import argparse
import json
import sys

from scrapers import browser, io_utils
from scrapers import article_collector, catalog_crawler, compat_enricher, detail_extractor, repair_guides


def _export_raw() -> None:
    import shutil

    io_utils.ensure_dirs()
    if io_utils.ENRICHED_JSONL.exists():
        io_utils.dedupe_jsonl_by_url(io_utils.ENRICHED_JSONL, io_utils.PARTS_OUT)
    repair_src = io_utils.REPAIR_WORK / "repairs_merged.jsonl"
    if repair_src.exists():
        shutil.copy2(repair_src, io_utils.REPAIRS_OUT)
    article_src = io_utils.ARTICLE_WORK / "articles_raw.jsonl"
    if article_src.exists():
        shutil.copy2(article_src, io_utils.ARTICLES_OUT)


def _dedupe_product_links() -> int:
    deduped = io_utils.CATALOG_DIR / "product_links_deduped.jsonl"
    return io_utils.dedupe_jsonl_by_url(io_utils.PRODUCT_LINKS, deduped)


def _seed_links_from_parts_backup() -> int:
    """Build deduped product URL list from backed-up parts.jsonl (skips catalog crawl)."""
    src = io_utils.BACKUP_DIR / "parts.jsonl"
    if not src.exists():
        src = io_utils.PARTS_OUT
    deduped = io_utils.CATALOG_DIR / "product_links_deduped.jsonl"
    count = 0
    seen: set[str] = set()
    with deduped.open("w", encoding="utf-8") as out:
        for row in io_utils.iter_jsonl(src):
            url = (row.get("product_url") or "").strip().split("?")[0]
            if not url or url in seen:
                continue
            seen.add(url)
            out.write(json.dumps({"product_url": url}, ensure_ascii=False) + "\n")
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PartSelect data collection pipeline")
    parser.add_argument(
        "--stage",
        choices=(
            "catalog",
            "details",
            "enrich",
            "repairs",
            "articles",
            "export",
            "merge",
            "refresh-db",
            "seed-urls",
            "all",
        ),
        default="all",
    )
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max new records to scrape this run (already-done URLs are skipped, not counted)",
    )
    parser.add_argument("--backup", action="store_true", help="Backup existing raw JSONL first")
    args = parser.parse_args(argv)

    io_utils.ensure_dirs()
    if args.backup or args.stage in ("all", "export"):
        io_utils.backup_raw_files()

    driver = None
    needs_browser = args.stage in (
        "catalog",
        "details",
        "enrich",
        "repairs",
        "articles",
        "all",
    )

    try:
        if needs_browser:
            driver = browser.build_chrome(headless=args.headless)

        if args.stage == "seed-urls":
            print("== seed-urls from backup parts.jsonl ==")
            print(f"urls: {_seed_links_from_parts_backup()}")

        if args.stage in ("catalog", "all"):
            print("== catalog ==")
            print(catalog_crawler.run_catalog(driver))

        if args.stage in ("details", "all"):
            print("== details ==")
            input_path = io_utils.CATALOG_DIR / "product_links_deduped.jsonl"
            if not input_path.exists():
                if args.stage == "all":
                    n = _dedupe_product_links()
                    print(f"deduped product links: {n}")
                else:
                    input_path = io_utils.PRODUCT_LINKS
            print(
                detail_extractor.run_details_batch(
                    driver,
                    input_jsonl=input_path,
                    limit=args.limit,
                )
            )

        if args.stage in ("enrich", "all"):
            print("== enrich ==")
            print(compat_enricher.run_enrichment(driver, limit=args.limit))

        if args.stage in ("repairs", "all"):
            print("== repairs ==")
            print(f"repair records: {repair_guides.run_repairs(driver)}")

        if args.stage in ("articles", "all"):
            print("== articles ==")
            print(f"article records: {article_collector.run_articles(driver, limit=args.limit)}")

        if args.stage in ("export", "all"):
            print("== export ==")
            _export_raw()
            for path in (io_utils.PARTS_OUT, io_utils.REPAIRS_OUT, io_utils.ARTICLES_OUT):
                if path.exists():
                    lines = sum(1 for _ in io_utils.iter_jsonl(path))
                    print(f"{path.name}: {lines} lines")

        if args.stage == "merge":
            from scrapers.merge_catalog import merge_parts_catalog
            print("== merge fresh scrape into parts.jsonl ==")
            print(json.dumps(merge_parts_catalog(backup=True), indent=2))

        if args.stage == "refresh-db":
            from scrapers.merge_catalog import run_refresh_db
            print("== refresh-db (merge + re-ingest) ==")
            print(json.dumps(run_refresh_db(), indent=2))
    finally:
        if driver:
            driver.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
