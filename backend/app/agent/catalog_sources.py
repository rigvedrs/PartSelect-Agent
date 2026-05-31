"""Data access for compatible-parts catalog (DB + live model page)."""

from __future__ import annotations

from dataclasses import dataclass

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


def part_type_keywords(query: str) -> str | None:
    from app.agent.tools.search_parts import _extract_keywords
    terms = [
        t for t in _extract_keywords(query or "").split()
        if t not in _QUERY_STOP and not t.isdigit()
    ]
    return " ".join(terms) if terms else None


def fetch_from_db(model: str, part_type_filter: str | None, limit: int) -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        params: dict = {"model": model, "limit": limit}
        keyword_clause = ""
        keywords = part_type_keywords(part_type_filter or "") if part_type_filter else None
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


@dataclass(frozen=True)
class LiveFetchResult:
    parts: list[dict]
    total_on_page: int
    page_part_names: list[str]


def _dominant_appliance(names: list[str]) -> str | None:
    """Best-effort hint from scraped part titles (e.g. refrigerator vs dishwasher)."""
    text = " ".join(names).lower()
    fridge = text.count("refrigerator") + text.count(" fridge")
    dishwasher = text.count("dishwasher")
    if fridge == 0 and dishwasher == 0:
        return None
    if fridge >= dishwasher:
        return "refrigerator"
    return "dishwasher"


def fetch_from_live(model: str, part_type_filter: str | None, limit: int) -> LiveFetchResult:
    from scrapers.model_lookup import scrape_model_parts
    from app.agent.tools.search_parts import get_part_by_ps
    from app.agent.tools.part_enrichment import enrich_part_details

    keywords = part_type_keywords(part_type_filter or "") if part_type_filter else None
    page = scrape_model_parts(model, part_type_filter if keywords else None)
    live_parts: list[dict] = []
    for entry in page.parts[:limit]:
        row = get_part_by_ps(entry["ps_number"], fallback=entry)
        if not row:
            continue
        if not row.get("product_url") and entry.get("product_url"):
            row["product_url"] = entry["product_url"]
        row["compat_model"] = model
        live_parts.append(enrich_part_details(row, force_price_refresh=True))
    return LiveFetchResult(
        parts=live_parts,
        total_on_page=page.total_on_page,
        page_part_names=page.page_names,
    )


def infer_appliance_hint(names: list[str]) -> str | None:
    return _dominant_appliance(names)
