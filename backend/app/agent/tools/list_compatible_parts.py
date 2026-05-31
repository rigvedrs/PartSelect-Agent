"""List parts that are verified compatible with an appliance model (SQL + live model page)."""

from __future__ import annotations

import os
from sqlalchemy import text

from app.db.engine import get_engine

_QUERY_STOP = frozenset({
    "compatible", "compatibility", "parts", "part", "model", "fit", "fits",
    "work", "with", "for", "my", "what", "which", "show", "list", "are", "is",
    "the", "a", "an", "how", "do", "can", "you", "tell", "me", "about",
    "well", "too", "also", "there", "its", "same", "all", "as", "just", "even",
    "one", "some", "any", "other", "else", "then", "when", "that", "this",
    "fridge", "refrigerator", "freezer", "dishwasher", "appliance",
})

# Full model-page listings can exceed stale DB ingest; cap live enrichment batch size.
_FULL_CATALOG_LIMIT = 40


def _part_text(part: dict) -> str:
    return ((part.get("name") or "") + " " + (part.get("description") or "")).lower()


def _part_type_keywords(query: str) -> str | None:
    """Keywords describing the part type (not the model or meta words)."""
    from app.agent.tools.search_parts import _extract_keywords
    terms = [
        t for t in _extract_keywords(query or "").split()
        if t not in _QUERY_STOP and not t.isdigit()
    ]
    return " ".join(terms) if terms else None


def _is_unfiltered_catalog(part_query: str | None) -> bool:
    return not _part_type_keywords(part_query or "")


def _parts_from_db(model: str, part_query: str | None, limit: int) -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        params: dict = {"model": model, "limit": limit}
        keyword_clause = ""
        keywords = _part_type_keywords(part_query or "") if part_query else None
        if keywords:
            terms = keywords.split()[:4]
            clauses = []
            for i, term in enumerate(terms):
                key = f"k{i}"
                params[key] = f"%{term}%"
                clauses.append(
                    f"(LOWER(p.name) LIKE :{key} OR LOWER(p.description) LIKE :{key})"
                )
            keyword_clause = " AND (" + " AND ".join(clauses) + ")"

        rows = conn.execute(
            text(f"""
                SELECT DISTINCT ON (p.ps_number)
                    p.ps_number, p.name, p.price, p.stock_status, p.brand,
                    p.image_url, p.product_url, p.category,
                    c.model_number AS compat_model, c.brand AS compat_brand
                FROM compatibility c
                INNER JOIN parts p ON p.ps_number = c.ps_number
                WHERE UPPER(c.model_number) = UPPER(:model)
                {keyword_clause}
                ORDER BY p.ps_number, p.name
                LIMIT :limit
            """),
            params,
        ).mappings().all()

    parts = []
    for r in rows:
        row = dict(r)
        if row.get("price") is not None:
            row["price"] = float(row["price"])
        parts.append(row)
    return parts


def _parts_from_live_model_page(
    model: str, part_query: str | None, limit: int,
) -> list[dict]:
    from scrapers.model_lookup import scrape_model_parts
    from app.agent.tools.search_parts import get_part_by_ps
    from app.agent.tools.part_enrichment import enrich_part_details

    keywords = _part_type_keywords(part_query or "") if part_query else None
    entries = scrape_model_parts(model, part_query if keywords else None)
    live_parts: list[dict] = []
    for entry in entries[:limit]:
        row = get_part_by_ps(entry["ps_number"], fallback=entry)
        if not row:
            continue
        if not row.get("product_url") and entry.get("product_url"):
            row["product_url"] = entry["product_url"]
        row["compat_model"] = model
        live_parts.append(enrich_part_details(row, force_price_refresh=True))
    return live_parts


def list_compatible_parts(
    model_number: str,
    part_query: str | None = None,
    limit: int = 10,
) -> dict:
    """Return parts for a model from DB and/or live PartSelect model page."""
    from app.observability import get_logger
    from app.agent.messages import model_referral

    log = get_logger("tools.list_compatible_parts")

    model = (model_number or "").strip()
    if not model:
        return {
            "model_number": "",
            "parts": [],
            "count": 0,
            "source": "none",
            "reason": "Please provide your appliance model number (e.g. WRS325SDHZ).",
        }

    effective_limit = max(limit, _FULL_CATALOG_LIMIT) if _is_unfiltered_catalog(part_query) else limit
    has_firecrawl = bool(os.getenv("FIRECRAWL_API_KEY"))

    # Full catalog: model page is authoritative; ingested compatibility is often incomplete.
    if _is_unfiltered_catalog(part_query) and has_firecrawl:
        live_parts = _parts_from_live_model_page(model, part_query, effective_limit)
        if live_parts:
            log.info("list_compatible live catalog model=%s parts=%d", model, len(live_parts))
            return {
                "model_number": model,
                "parts": live_parts,
                "count": len(live_parts),
                "source": "live",
                "reason": (
                    f"Found {len(live_parts)} part(s) listed for {model} on PartSelect "
                    "(live model page — our local catalog may not list every item yet)."
                ),
            }

    parts = _parts_from_db(model, part_query, effective_limit)
    if parts:
        return {
            "model_number": model,
            "parts": parts,
            "count": len(parts),
            "source": "db",
            "reason": f"Found {len(parts)} part(s) verified compatible with {model}.",
        }

    if has_firecrawl:
        live_parts = _parts_from_live_model_page(model, part_query, effective_limit)
        if live_parts:
            log.info("list_compatible live model=%s parts=%d", model, len(live_parts))
            return {
                "model_number": model,
                "parts": live_parts,
                "count": len(live_parts),
                "source": "live",
                "reason": (
                    f"Found {len(live_parts)} part(s) for {model} from a live PartSelect "
                    "lookup — please confirm fit before ordering."
                ),
            }

    return {
        "model_number": model,
        "parts": [],
        "count": 0,
        "source": "none",
        "reason": model_referral(model),
    }
