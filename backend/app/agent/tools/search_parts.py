import os
import re
from sqlalchemy import text
from app.db.engine import get_engine

_PS_RE = re.compile(r"PS\d+", re.IGNORECASE)

_STOP_WORDS = frozenset({
    "find", "search", "look", "up", "show", "me", "get", "a", "an", "the",
    "for", "my", "i", "need", "want", "have", "is", "what", "where", "how",
    "do", "can", "will", "please", "help", "some", "any", "in", "on", "of",
    "with", "and", "or", "it", "this", "that", "buy", "order",
})


def _extract_keywords(query: str) -> str:
    """Strip common question/command words and return the meaningful search term."""
    words = re.sub(r"[^\w\s]", " ", query.lower()).split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords) if keywords else query.lower()


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

        keywords = _extract_keywords(query).split()
        if not keywords:
            keywords = [query.lower()]

        # AND each keyword so "water filter fridge" finds parts containing all terms
        params: dict = {}
        keyword_clauses = []
        for i, kw in enumerate(keywords[:4]):  # cap at 4 terms
            key = f"k{i}"
            params[key] = f"%{kw}%"
            keyword_clauses.append(f"(LOWER(name) LIKE :{key} OR LOWER(description) LIKE :{key})")

        where = " AND ".join(keyword_clauses)
        category_clause = ""
        if category:
            category_clause = "AND category = :category"
            params["category"] = category.lower()

        rows = conn.execute(text(f"""
            SELECT * FROM parts
            WHERE {where}
            {category_clause}
            LIMIT 5
        """), params).mappings().all()

        # If AND search returns nothing, fall back to OR on just the first keyword
        if not rows and keywords:
            params2 = {"k0": f"%{keywords[0]}%"}
            if category:
                params2["category"] = category.lower()
            rows = conn.execute(text(f"""
                SELECT * FROM parts
                WHERE (LOWER(name) LIKE :k0 OR LOWER(description) LIKE :k0)
                {category_clause}
                LIMIT 5
            """), params2).mappings().all()

        return [dict(r) for r in rows]
