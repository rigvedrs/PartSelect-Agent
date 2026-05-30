import json
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.engine import get_engine, apply_schema
from app.ingest_models import reshape_part, extract_compat_rows
from app.rag.embedder import embed
from app.data.seeds import SEED_PARTS, SEED_COMPAT

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def _read_jsonl(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _insert_part(conn, p: dict):
    conn.execute(text("""
        INSERT INTO parts (ps_number, manufacturer_part_number, name, price, stock_status,
            brand, manufactured_for, description, category, product_url, image_url,
            video_url, symptoms, replaces, installation_steps)
        VALUES (:ps_number, :manufacturer_part_number, :name, :price, :stock_status,
            :brand, :manufactured_for, :description, :category, :product_url, :image_url,
            :video_url, :symptoms, :replaces, :installation_steps)
        ON CONFLICT (ps_number) DO UPDATE SET
            name = EXCLUDED.name,
            price = EXCLUDED.price,
            stock_status = EXCLUDED.stock_status,
            category = EXCLUDED.category,
            image_url = EXCLUDED.image_url,
            installation_steps = EXCLUDED.installation_steps
    """), p)


def _insert_compat(conn, row: dict):
    conn.execute(text("""
        INSERT INTO compatibility (ps_number, model_number, brand, appliance)
        VALUES (:ps_number, :model_number, :brand, :appliance)
        ON CONFLICT (ps_number, model_number) DO NOTHING
    """), row)


def ingest_parts(conn) -> int:
    count = 0
    for raw in _read_jsonl(RAW_DIR / "parts.jsonl"):
        p = reshape_part(raw)
        if not p["ps_number"] or p["category"] is None:
            continue
        _insert_part(conn, p)
        for row in extract_compat_rows(raw):
            _insert_compat(conn, row)
        count += 1
    return count


def ingest_seeds(conn):
    for p in SEED_PARTS:
        full = {"video_url": None, **p}
        _insert_part(conn, full)
    for ps, pairs in SEED_COMPAT.items():
        for model, brand in pairs:
            _insert_compat(conn, {
                "ps_number": ps,
                "model_number": model,
                "brand": brand,
                "appliance": "refrigerator",
            })


def ingest_repairs(conn) -> int:
    count = 0
    for raw in _read_jsonl(RAW_DIR / "repairs.jsonl"):
        appliance = (raw.get("item") or "").lower()
        if appliance not in ("refrigerator", "dishwasher"):
            continue
        res = conn.execute(text("""
            INSERT INTO repair_guides (appliance, symptom, part_name, content)
            VALUES (:appliance, :symptom, :part_name, :content) RETURNING id
        """), {
            "appliance": appliance,
            "symptom": raw.get("symptom"),
            "part_name": raw.get("part"),
            "content": raw.get("text"),
        })
        rid = res.scalar()
        content = f"{raw.get('symptom')}. {raw.get('text')}"
        vec = embed([content])[0]
        conn.execute(text("""
            INSERT INTO embeddings (source_type, source_id, content, embedding)
            VALUES ('repair', :sid, :content, :embedding)
        """), {"sid": str(rid), "content": content, "embedding": str(vec)})
        count += 1
    return count


def ingest_articles(conn) -> int:
    count = 0
    for raw in _read_jsonl(RAW_DIR / "articles.jsonl"):
        sections = raw.get("sections") or []
        body = "\n".join(s.get("text", "") for s in sections)
        content = f"{raw.get('title')}\n{body}"[:4000]
        res = conn.execute(text("""
            INSERT INTO articles (url, title, content, category)
            VALUES (:url, :title, :content, :category) RETURNING id
        """), {
            "url": raw.get("url"),
            "title": raw.get("title"),
            "content": content,
            "category": raw.get("category"),
        })
        aid = res.scalar()
        vec = embed([content])[0]
        conn.execute(text("""
            INSERT INTO embeddings (source_type, source_id, content, embedding)
            VALUES ('article', :sid, :content, :embedding)
        """), {"sid": str(aid), "content": content[:2000], "embedding": str(vec)})
        count += 1
    return count


def run_ingestion(engine: Engine | None = None) -> dict:
    engine = engine or get_engine()
    apply_schema(engine)
    with engine.begin() as conn:
        already = conn.execute(text("SELECT COUNT(*) FROM parts")).scalar()
        if already and already > 0:
            return {"skipped": True, "parts": already}
        parts = ingest_parts(conn)
        ingest_seeds(conn)
        repairs = ingest_repairs(conn)
        articles = ingest_articles(conn)
    return {"skipped": False, "parts": parts, "repairs": repairs, "articles": articles}


if __name__ == "__main__":
    print(run_ingestion())
