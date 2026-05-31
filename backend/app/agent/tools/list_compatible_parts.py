"""List parts that are verified compatible with an appliance model (SQL-only)."""

from __future__ import annotations

import re
from sqlalchemy import text

from app.agent.tools.search_parts import _extract_keywords
from app.db.engine import get_engine

_QUERY_STOP = frozenset({
    "compatible", "compatibility", "parts", "part", "model", "fit", "fits",
    "work", "with", "for", "my", "what", "which", "show", "list", "are", "is",
    "the", "a", "an", "how", "do", "can", "you", "tell", "me", "about",
})


def _part_type_keywords(query: str) -> str | None:
    """Keywords describing the part type (not the model or meta words)."""
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
    if not parts:
        hint = f" No parts in our database are listed as compatible with model {model}."
        if part_query:
            hint += f" Try a broader search or check the model number."
        return {
            "model_number": model,
            "parts": [],
            "count": 0,
            "reason": hint.strip(),
        }

    return {
        "model_number": model,
        "parts": parts,
        "count": len(parts),
        "reason": f"Found {len(parts)} part(s) verified compatible with {model}.",
    }
