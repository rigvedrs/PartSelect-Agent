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


def _query_keywords(part_query: str | None) -> list[str]:
    if not part_query:
        return []
    from app.agent.tools.search_parts import _extract_keywords
    return [w for w in _extract_keywords(part_query).split() if len(w) > 2]


def scrape_model_part_numbers(model: str, part_query: str | None = None) -> list[str]:
    """Return distinct PS numbers found on a model page. Empty list on any failure.

    When part_query is given, PS numbers on lines matching those keywords are returned first.
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
    seen: set[str] = set()
    all_ps: list[str] = []
    for m in _PS_RE.finditer(md):
        ps = m.group(0).upper()
        if ps not in seen:
            seen.add(ps)
            all_ps.append(ps)

    kws = _query_keywords(part_query)
    if not kws:
        log.info("model_lookup model=%s found_ps=%d", model, len(all_ps))
        return all_ps

    prioritized: list[str] = []
    prio_seen: set[str] = set()
    for line in md.splitlines():
        ll = line.lower()
        if not any(k in ll for k in kws):
            continue
        for m in _PS_RE.finditer(line):
            ps = m.group(0).upper()
            if ps not in prio_seen:
                prio_seen.add(ps)
                prioritized.append(ps)

    if prioritized:
        combined = prioritized + [ps for ps in all_ps if ps not in prio_seen]
        log.info("model_lookup model=%s keyword_hits=%d total=%d", model, len(prioritized), len(combined))
        return combined

    log.info("model_lookup model=%s found_ps=%d (no keyword lines)", model, len(all_ps))
    return all_ps


def model_lists_part(model: str, ps_number: str) -> bool | None:
    """True/False if the model page lists the PS number; None if lookup unavailable/failed."""
    found = scrape_model_part_numbers(model)
    if not found:
        return None
    return ps_number.upper() in found
