import re
from sqlalchemy import text
from app.db.engine import get_engine


def search_parts(query: str, category: str | None = None) -> list[dict]:
    """Return up to 5 parts matching the query. Exact PS# match first, then text search."""
    engine = get_engine()
    with engine.connect() as conn:
        ps_match = re.search(r"PS\d+", query, re.IGNORECASE)
        if ps_match:
            ps = ps_match.group(0).upper()
            row = conn.execute(
                text("SELECT * FROM parts WHERE ps_number = :ps"),
                {"ps": ps}
            ).mappings().first()
            if row:
                return [dict(row)]

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
