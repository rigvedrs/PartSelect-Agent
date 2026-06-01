"""Fill missing part fields (price, stock, image) via live PartSelect scrape."""
from __future__ import annotations

from app.agent.tools.part_validation import is_valid_part
from app.observability import get_logger

log = get_logger("tools.part_enrichment")


def needs_enrichment(part: dict) -> bool:
    if not is_valid_part(part):
        return True
    if part.get("price") is None:
        return True
    try:
        if float(part.get("price") or 0) <= 0:
            return True
    except (TypeError, ValueError):
        return True
    return False


def enrich_part_details(part: dict, *, force_price_refresh: bool = False) -> dict:
    """Scrape product page for price/details. Uses full product_url when available."""
    if not part.get("ps_number"):
        return part

    from app.live_scrape.gateway import get_gateway
    if not get_gateway().is_enabled():
        return part

    product_url = part.get("product_url")
    if not needs_enrichment(part) and not (force_price_refresh and product_url):
        return part

    ps = part["ps_number"].upper()
    try:
        from scrapers.parts_scraper import scrape_and_parse
        from scrapers.product_utils import clean_product_url
        from app.ingest_models import reshape_part

        url = clean_product_url(product_url)
        raw = scrape_and_parse(ps, product_url=url)
        if not raw:
            return part
        shaped = reshape_part(raw)
    except Exception:
        log.exception("enrich failed ps=%s", ps)
        return part

    merged = dict(part)
    for key in ("name", "price", "stock_status", "brand", "product_url", "image_url", "description"):
        val = shaped.get(key)
        if val is None or val == "":
            continue
        if key == "name":
            if is_valid_part({"ps_number": ps, "name": val}):
                merged["name"] = val
        else:
            merged[key] = val
    if shaped.get("price") is not None:
        merged["price"] = shaped["price"]
    log.info("enriched ps=%s price=%r url=%r", ps, merged.get("price"), url)
    return merged
