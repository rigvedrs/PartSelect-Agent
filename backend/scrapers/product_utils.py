"""Shared PartSelect product URL and price parsing for all scrapers."""
from __future__ import annotations

import re


def clean_product_url(url: str | None) -> str | None:
    """Normalize PartSelect product URLs from markdown / model-page links."""
    if not url:
        return None
    url = url.strip().split()[0].strip("\"'")
    m = re.match(r"(https?://(?:www\.)?partselect\.com/[^\s\"']+\.htm)", url, re.I)
    if m:
        return m.group(1)
    return url.split("?")[0] if ".htm" in url else url


def parse_product_price(md: str) -> str | None:
    """Extract the primary product price from PartSelect product-page content."""
    if not md:
        return None

    m = re.search(
        r'itemprop=["\']price["\'][^>]*content=["\']([\d.]+)',
        md,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    lines = [ln.strip() for ln in md.splitlines()]
    for i, line in enumerate(lines):
        if line.lower() != "in stock":
            continue
        for j in range(i - 1, max(i - 5, -1), -1):
            pm = re.search(r"\$([\d,]+\.\d{2})", lines[j])
            if pm:
                return pm.group(1).replace(",", "")

    for i, line in enumerate(lines):
        if line.startswith("# ") and i + 1 < len(lines):
            window = "\n".join(lines[i : i + 20])
            pm = re.search(r"\$([\d,]+\.\d{2})", window)
            if pm:
                return pm.group(1).replace(",", "")
            break

    pm = re.search(r"\$([\d,]+\.\d{2})", md)
    return pm.group(1).replace(",", "") if pm else None


def normalize_price(value: str | None) -> str | None:
    """Strip currency formatting; return decimal string or None."""
    if not value:
        return None
    m = re.search(r"([\d,]+\.\d{2})", str(value).replace("$", ""))
    return m.group(1).replace(",", "") if m else None
