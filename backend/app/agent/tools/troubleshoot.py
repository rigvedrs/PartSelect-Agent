from sqlalchemy import text
from app.db.engine import get_engine
from app.rag.embedder import embed_one
from app.config import load_settings


def troubleshoot_symptom(symptom: str, appliance_type: str, brand: str | None = None) -> dict:
    """Vector search over repair_guides + articles. Returns causes + orderable parts."""
    settings = load_settings()
    engine = get_engine()
    top_k = settings.retrieval.top_k

    vec = embed_one(f"{appliance_type} {symptom}")
    vec_str = str(vec)

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

        causes = []
        for row in repair_rows:
            part_name = row["part_name"] or ""
            ps_row = conn.execute(text(
                "SELECT ps_number, name, price, image_url, product_url "
                "FROM parts WHERE LOWER(name) LIKE :q AND category = :cat LIMIT 1"
            ), {"q": f"%{part_name.lower()[:30]}%", "cat": appliance_type.lower()}).mappings().first()

            causes.append({
                "symptom": row["symptom"],
                "cause": row["content"][:300] if row["content"] else "",
                "part_name": part_name,
                "part": dict(ps_row) if ps_row else None,
            })

        return {
            "appliance_type": appliance_type,
            "symptom": symptom,
            "causes": causes,
        }
