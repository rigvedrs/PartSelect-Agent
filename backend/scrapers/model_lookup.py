"""Best-effort live lookup of parts for an appliance model via the Firecrawl client."""
from __future__ import annotations
import os
import re

from app.observability import get_logger

log = get_logger("scrapers.model_lookup")

_PS_RE = re.compile(r"PS\d{5,}", re.IGNORECASE)
_MODEL_URL = "https://www.partselect.com/Models/{model}/"


def model_page_url(model: str) -> str:
    return _MODEL_URL.format(model=model.strip().upper())


def scrape_model_part_numbers(model: str) -> list[str]:
    """Return distinct PS numbers found on a model page. Empty list on any failure."""
    if not os.getenv("FIRECRAWL_API_KEY"):
        return []
    try:
        from scrapers.firecrawl_client import scrape_markdown
        md = scrape_markdown(model_page_url(model))
    except Exception:
        log.exception("model page scrape failed model=%s", model)
        return []
    if not md:
        return []
    seen, out = set(), []
    for m in _PS_RE.finditer(md):
        ps = m.group(0).upper()
        if ps not in seen:
            seen.add(ps)
            out.append(ps)
    log.info("model_lookup model=%s found_ps=%d", model, len(out))
    return out


def model_lists_part(model: str, ps_number: str) -> bool | None:
    """True/False if the model page lists the PS number; None if lookup unavailable/failed."""
    found = scrape_model_part_numbers(model)
    if not found:
        return None
    return ps_number.upper() in found
