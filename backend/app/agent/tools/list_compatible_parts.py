"""List parts that are verified compatible with an appliance model (SQL-only)."""

from __future__ import annotations

import re
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


def _part_text(part: dict) -> str:
    return ((part.get("name") or "") + " " + (part.get("description") or "")).lower()


def _filter_by_keywords(parts: list[dict], kws: list[str]) -> list[dict]:
    """Match parts by keywords — try AND first, fall back to OR if nothing matches."""
    if not kws:
        return parts
    and_hits = [p for p in parts if all(k in _part_text(p) for k in kws)]
    if and_hits:
        return and_hits
    return [p for p in parts if any(k in _part_text(p) for k in kws)]


def _part_type_keywords(query: str) -> str | None:
    """Keywords describing the part type (not the model or meta words)."""
    from app.agent.tools.search_parts import _extract_keywords
    terms = [
        t for t in _extract_keywords(query or "").split()
        if t not in _QUERY_STOP and not t.isdigit()
    ]
    return " ".join(terms) if terms else None


def list_compatible_parts(
    model_number: str,
    part_query: str | None = None,
    limit: int = 10,
) -> dict:
    """Return parts with a compatibility row for this model. Optional keyword filter."""
    model = (model_number or "").strip()
    if not model:
        return {
            "model_number": "",
            "parts": [],
            "count": 0,
            "source": "none",
            "reason": "Please provide your appliance model number (e.g. WRS325SDHZ).",
        }

    engine = get_engine()
    with engine.connect() as conn:
        params: dict = {"model": model, "limit": limit}
        keyword_clause = ""
        if part_query and part_query.strip():
            keywords = _part_type_keywords(part_query)
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

    from app.observability import get_logger
    from app.agent.messages import model_referral
    log = get_logger("tools.list_compatible_parts")

    if parts:
        return {
            "model_number": model, "parts": parts, "count": len(parts), "source": "db",
            "reason": f"Found {len(parts)} part(s) verified compatible with {model}.",
        }

    # Live fallback: parse product links from the model page (not blind PS regex)
    from scrapers.model_lookup import scrape_model_parts
    from app.agent.tools.search_parts import get_part_by_ps

    entries = scrape_model_parts(
        model,
        part_query if _part_type_keywords(part_query or "") else None,
    )
    live_parts: list[dict] = []
    from app.agent.tools.part_enrichment import enrich_part_details
    for entry in entries[:limit]:
        row = get_part_by_ps(entry["ps_number"], fallback=entry)
        if row:
            if not row.get("product_url") and entry.get("product_url"):
                row["product_url"] = entry["product_url"]
            live_parts.append(enrich_part_details(row, force_price_refresh=True))
    if live_parts:
        log.info("list_compatible live model=%s parts=%d", model, len(live_parts))
        return {
            "model_number": model, "parts": live_parts, "count": len(live_parts),
            "source": "live",
            "reason": (
                f"Found {len(live_parts)} part(s) for {model} from a live PartSelect "
                "lookup — please confirm fit before ordering."
            ),
        }
    return {
        "model_number": model, "parts": [], "count": 0, "source": "none",
        "reason": model_referral(model),
    }
