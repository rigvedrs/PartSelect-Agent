import os
import re
from sqlalchemy import text
from app.db.engine import get_engine

_PS_RE = re.compile(r"PS\d+", re.IGNORECASE)


def _firecrawl_fallback(ps_number: str) -> list[dict]:
    """Scrape PartSelect for an unknown PS number and ingest it on-the-fly.
    Returns the newly ingested part row, or empty list if scrape fails or key absent.
    """
    api_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not api_key:
        return []
    try:
        from scrapers.parts_scraper import scrape_and_parse
        from app.ingest_models import reshape_part
        from app.rag.ingest import _insert_part

        raw = scrape_and_parse(ps_number)
        if not raw:
            return []

        p = reshape_part(raw)
        p.setdefault("video_url", None)

        engine = get_engine()
        with engine.begin() as conn:
            _insert_part(conn, p)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM parts WHERE ps_number = :ps"),
                {"ps": ps_number.upper()}
            ).mappings().first()
        return [dict(row)] if row else []
    except Exception:
        return []


def search_parts(query: str, category: str | None = None) -> list[dict]:
    """Return up to 5 parts matching the query. Exact PS# match first,
    then text search, then Firecrawl live fallback for unknown PS numbers."""
    engine = get_engine()
    with engine.connect() as conn:
        ps_match = _PS_RE.search(query)
        if ps_match:
            ps = ps_match.group(0).upper()
            row = conn.execute(
                text("SELECT * FROM parts WHERE ps_number = :ps"),
                {"ps": ps}
            ).mappings().first()
            if row:
                return [dict(row)]
            return _firecrawl_fallback(ps)

        params: dict = {"q": f"%{query.lower()}%"}
        category_clause = ""
        if category:
            category_clause = "AND category = :category"
            params["category"] = category.lower()
        rows = conn.execute(text(f"""
            SELECT * FROM parts
            WHERE (LOWER(name) LIKE :q OR LOWER(description) LIKE :q)
            {category_clause}
            LIMIT 5
        """), params).mappings().all()
        return [dict(r) for r in rows]
