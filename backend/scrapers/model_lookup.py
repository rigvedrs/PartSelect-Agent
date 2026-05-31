"""Best-effort live lookup of parts for an appliance model via the Firecrawl client."""
from __future__ import annotations
import os
import re

from app.observability import get_logger

log = get_logger("scrapers.model_lookup")

_PS_RE = re.compile(r"PS\d{5,}", re.IGNORECASE)
_MODEL_URL = "https://www.partselect.com/Models/{model}/"
_URL_PS_RE = re.compile(
    r"\((https?://(?:www\.)?partselect\.com/(PS\d+)[^)]*)\)",
    re.IGNORECASE,
)


def model_page_url(model: str) -> str:
    return _MODEL_URL.format(model=model.strip().upper())


def _query_keywords(part_query: str | None) -> list[str]:
    if not part_query:
        return []
    from app.agent.tools.search_parts import _extract_keywords
    return [w for w in _extract_keywords(part_query).split() if len(w) > 2]


def _filter_entries(entries: list[dict], kws: list[str]) -> list[dict]:
    if not kws:
        return entries
    names = [(e, e["name"].lower()) for e in entries]
    and_hits = [e for e, n in names if all(k in n for k in kws)]
    if and_hits:
        return and_hits
    or_hits = [e for e, n in names if any(k in n for k in kws)]
    return or_hits


def scrape_model_parts(model: str, part_query: str | None = None) -> list[dict]:
    """Return parts listed on a model page as {ps_number, name, product_url}.

    Parses markdown product links only — avoids stray PS numbers from page chrome.
    """
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

    entries: list[dict] = []
    seen: set[str] = set()
    for line in md.splitlines():
        url_m = _URL_PS_RE.search(line)
        if not url_m:
            continue
        name_m = re.search(r"!\[([^\]]+)\]", line)
        if not name_m:
            continue
        name = name_m.group(1).strip()
        if not name or "base64" in name.lower():
            continue
        ps = url_m.group(2).upper()
        if ps in seen:
            continue
        seen.add(ps)
        entries.append({
            "ps_number": ps,
            "name": name,
            "product_url": url_m.group(1),
        })

    kws = _query_keywords(part_query)
    if kws:
        filtered = _filter_entries(entries, kws)
        log.info(
            "model_lookup model=%s keyword=%r hits=%d/%d",
            model, kws, len(filtered), len(entries),
        )
        return filtered

    log.info("model_lookup model=%s parts=%d", model, len(entries))
    return entries


def scrape_model_part_numbers(model: str, part_query: str | None = None) -> list[str]:
    """PS numbers from model page product links (legacy helper)."""
    return [e["ps_number"] for e in scrape_model_parts(model, part_query)]


def model_lists_part(model: str, ps_number: str) -> bool | None:
    """True/False if the model page lists the PS number; None if lookup unavailable."""
    found = scrape_model_part_numbers(model)
    if not found:
        return None
    return ps_number.upper() in found
