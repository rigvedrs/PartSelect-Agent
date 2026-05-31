"""Original Firecrawl-based parts scraper.

Scrapes a small sample of PartSelect product pages and writes records in the
same schema consumed by app.rag.ingest. Run:
  python -m scrapers.parts_scraper PS11752778 PS12745538
"""
import json
import re
import sys
from pathlib import Path

from scrapers.firecrawl_client import scrape_markdown
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


def scrape_parts(ps_numbers: list[str]) -> list[dict]:
    results = []
    for ps in ps_numbers:
        md = scrape_markdown(URL_TMPL.format(ps=ps))
        record = parse_product(ps, md)
        results.append(record)
        print(f"scraped {ps} ({len(md)} chars)")
    return results


def main(ps_numbers: list[str]):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = scrape_parts(ps_numbers)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(records)} records -> {OUT}")


def scrape_and_parse(ps_number: str, product_url: str | None = None) -> dict | None:
    """Scrape PartSelect product page for a PS number and return parsed raw dict."""
    ps = ps_number.upper()
    if not ps.startswith("PS"):
        ps = f"PS{ps}"
    url = clean_product_url(product_url) or URL_TMPL.format(ps=ps)
    try:
        md = scrape_markdown(url)
        if not md or "page not found" in md.lower()[:800]:
            return None
        record = parse_product(ps, md)
        record["product_url"] = url
        name = (record.get("name") or "").lower()
        if "page not found" in name:
            return None
        return record
    except Exception:
        return None


if __name__ == "__main__":
    main(sys.argv[1:] or ["PS11752778"])
