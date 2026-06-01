"""Runtime PartSelect product scrape — Selenium (free) with optional Firecrawl markdown fallback."""
import json
import re
import sys
from pathlib import Path

from scrapers.product_utils import clean_product_url, parse_product_price

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "parts_sample.jsonl"
URL_TMPL = "https://www.partselect.com/{ps}.htm"


def parse_product(ps_number: str, md: str) -> dict:
    name_match = re.search(r"^#\s*(.+)", md, re.MULTILINE)
    return {
        "partselect_number": ps_number,
        "name": name_match.group(1).strip() if name_match else ps_number,
        "price": parse_product_price(md),
        "availability": "In Stock" if "in stock" in md.lower() else None,
        "description": md[:600],
        "model_cross_reference": [],
        "product_url": URL_TMPL.format(ps=ps_number.upper()),
        "main_image": None,
    }


def _scrape_via_selenium(ps: str, url: str) -> dict | None:
    from scrapers.detail_extractor import extract_product_record
    from scrapers.runtime_fetch import headless_driver

    with headless_driver() as driver:
        record = extract_product_record(driver, url)
    if not record.get("partselect_number"):
        record["partselect_number"] = ps
    name = (record.get("name") or "").lower()
    if "page not found" in name:
        return None
    return record


def _resolve_url(ps: str, product_url: str | None) -> str:
    from scrapers.url_resolver import resolve_product_url

    url = clean_product_url(product_url) or URL_TMPL.format(ps=ps)
    if product_url:
        return url
    resolved = resolve_product_url(ps)
    return resolved or url


def scrape_installation_record(ps_number: str, product_url: str | None = None) -> dict | None:
    """Scrape product page for installation steps — always uses Selenium DOM extraction."""
    ps = ps_number.upper()
    if not ps.startswith("PS"):
        ps = f"PS{ps}"
    url = _resolve_url(ps, product_url)
    record = _scrape_via_selenium(ps, url)
    if record:
        return record
    if not product_url:
        return None
    resolved = _resolve_url(ps, None)
    if resolved != url:
        return _scrape_via_selenium(ps, resolved)
    return None


def scrape_and_parse(ps_number: str, product_url: str | None = None) -> dict | None:
    """Scrape PartSelect product page and return parsed raw dict."""
    from scrapers.runtime_fetch import live_scrape_available, live_scrape_backend, fetch_markdown

    if not live_scrape_available():
        return None

    ps = ps_number.upper()
    if not ps.startswith("PS"):
        ps = f"PS{ps}"
    url = clean_product_url(product_url) or URL_TMPL.format(ps=ps)

    try:
        if live_scrape_backend() == "selenium":
            record = _scrape_via_selenium(ps, url)
            if not record and not product_url:
                resolved = _resolve_url(ps, None)
                if resolved != url:
                    record = _scrape_via_selenium(ps, resolved)
        else:
            md = fetch_markdown(url)
            if not md or "page not found" in md.lower()[:800]:
                resolved = _resolve_url(ps, None)
                if resolved != url:
                    url = resolved
                    md = fetch_markdown(url)
            if not md or "page not found" in md.lower()[:800]:
                return None
            record = parse_product(ps, md)
            record["product_url"] = url
            name = (record.get("name") or "").lower()
            if "page not found" in name:
                return None
        if record:
            record["product_url"] = clean_product_url(record.get("product_url")) or url
        return record
    except Exception:
        return None


def scrape_parts(ps_numbers: list[str]) -> list[dict]:
    results = []
    for ps in ps_numbers:
        record = scrape_and_parse(ps)
        if record:
            results.append(record)
            print(f"scraped {ps}")
    return results


def main(ps_numbers: list[str]):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = scrape_parts(ps_numbers)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} records -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["PS11752778"])
