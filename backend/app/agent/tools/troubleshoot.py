"""RAG retrieval for troubleshooting — repair guides, articles, and related parts."""
from __future__ import annotations

from sqlalchemy import text

from app.db.engine import get_engine
from app.rag.embedder import embed_one
from app.config import load_settings
from app.observability import span


def detect_appliance_type(message: str) -> str:
    lower = message.lower()
    if any(k in lower for k in ("dishwasher", "dish washer")):
        return "dishwasher"
    return "refrigerator"


def retrieve_troubleshoot_context(symptom: str, appliance_type: str) -> dict:
    """Vector search over repair guides and articles."""
    settings = load_settings()
    engine = get_engine()
    top_k = settings.retrieval.top_k
    with span("rag_embed"):
        vec_str = str(embed_one(f"{appliance_type} {symptom}"))

    with engine.connect() as conn:
        repair_rows = conn.execute(text("""
            SELECT r.symptom, r.part_name, r.content,
                   1 - (e.embedding <=> CAST(:vec AS vector)) AS score
            FROM embeddings e
            JOIN repair_guides r ON e.source_id = r.id::text AND e.source_type = 'repair'
            WHERE r.appliance = :appliance
            ORDER BY e.embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """), {"vec": vec_str, "appliance": appliance_type.lower(), "k": top_k}).mappings().all()

        article_rows = conn.execute(text("""
            SELECT a.title, a.url, a.content,
                   1 - (e.embedding <=> CAST(:vec AS vector)) AS score
            FROM embeddings e
            JOIN articles a ON e.source_id = a.id::text AND e.source_type = 'article'
            ORDER BY e.embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """), {"vec": vec_str, "k": top_k}).mappings().all()

        causes = []
        parts: list[dict] = []
        seen_ps: set[str] = set()

        for row in repair_rows:
            part_name = row["part_name"] or ""
            ps_row = conn.execute(text(
                "SELECT ps_number, name, price, image_url, product_url "
                "FROM parts WHERE LOWER(name) LIKE :q AND category = :cat LIMIT 1"
            ), {"q": f"%{part_name.lower()[:40]}%", "cat": appliance_type.lower()}).mappings().first()

            part = dict(ps_row) if ps_row else None
            if part and part["ps_number"] not in seen_ps:
                seen_ps.add(part["ps_number"])
                parts.append(part)

            causes.append({
                "symptom": row["symptom"],
                "cause": (row["content"] or "")[:400],
                "part_name": part_name,
                "part": part,
                "score": float(row["score"] or 0),
            })

        articles = [
            {
                "title": row["title"],
                "url": row["url"],
                "snippet": (row["content"] or "")[:400],
                "score": float(row["score"] or 0),
            }
            for row in article_rows
        ]

    return {
        "appliance_type": appliance_type,
        "symptom": symptom,
        "causes": causes,
        "articles": articles,
        "parts": parts,
    }


def format_context_for_llm(ctx: dict) -> str:
    lines = [f"Appliance: {ctx['appliance_type']}", f"Symptom: {ctx['symptom']}", ""]

    if ctx["causes"]:
        lines.append("Repair guide matches:")
        for i, c in enumerate(ctx["causes"][:5], 1):
            lines.append(f"{i}. Symptom: {c.get('symptom') or 'unknown'}")
            if c.get("cause"):
                lines.append(f"   Details: {c['cause']}")
            if c.get("part_name"):
                lines.append(f"   Related part: {c['part_name']}")
            if c.get("part"):
                p = c["part"]
                lines.append(f"   PS# {p['ps_number']}: {p.get('name')}")

    if ctx["articles"]:
        lines.append("")
        lines.append("Article matches:")
        for i, a in enumerate(ctx["articles"][:3], 1):
            lines.append(f"{i}. {a.get('title') or 'Article'}")
            if a.get("snippet"):
                lines.append(f"   {a['snippet'][:300]}")

    return "\n".join(lines)


# Backward-compatible alias
def troubleshoot_symptom(symptom: str, appliance_type: str, brand: str | None = None) -> dict:
    return retrieve_troubleshoot_context(symptom, appliance_type)
