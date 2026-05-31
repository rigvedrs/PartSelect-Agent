import json
import os
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.engine import get_engine, apply_schema
from app.ingest_models import reshape_part, extract_compat_rows
from app.rag.embedder import embed

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
DEMO_MODEL_PARTS = RAW_DIR.parent / "scrape_work" / "demo" / "wdt780saem1_parts.json"


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


def prune_legacy_seed_compat(conn) -> None:
    """Remove hardcoded demo compatibility rows from earlier builds."""
    conn.execute(text("""
        DELETE FROM compatibility
        WHERE ps_number = 'PS11752778' AND model_number = 'WDT780SAEM1'
    """))


def prune_mismatched_compat(conn) -> None:
    """Drop rows where tagged appliance type conflicts with part category."""
    conn.execute(text("""
        DELETE FROM compatibility c
        USING parts p
        WHERE c.ps_number = p.ps_number
          AND c.appliance IS NOT NULL
          AND p.category IS NOT NULL
          AND c.appliance <> p.category
    """))


def ingest_parts(conn) -> int:
    count = 0
    for raw in _read_jsonl(RAW_DIR / "parts.jsonl"):
        try:
            p = reshape_part(raw)
        except ValueError:
            continue
        if p["category"] is None:
            continue
        _insert_part(conn, p)
        for row in extract_compat_rows(raw):
            _insert_compat(conn, row)
        count += 1
    return count


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
            ON CONFLICT (source_type, source_id) DO UPDATE SET
                content = EXCLUDED.content, embedding = EXCLUDED.embedding
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
            ON CONFLICT (source_type, source_id) DO UPDATE SET
                content = EXCLUDED.content, embedding = EXCLUDED.embedding
        """), {"sid": str(aid), "content": content[:2000], "embedding": str(vec)})
        count += 1
    return count


def _seed_demo_model_compat(conn) -> int:
    """Ensure WDT780SAEM1 compatibility for all parts from demo model-page scrape."""
    if not DEMO_MODEL_PARTS.exists():
        return 0
    data = json.loads(DEMO_MODEL_PARTS.read_text(encoding="utf-8"))
    count = 0
    for ps in data.get("ps_numbers", []):
        _insert_compat(conn, {
            "ps_number": ps.upper(),
            "model_number": data.get("model_number", "WDT780SAEM1").upper(),
            "brand": "Whirlpool",
            "appliance": "dishwasher",
        })
        count += 1
    return count


def run_ingestion(engine: Engine | None = None) -> dict:
    engine = engine or get_engine()
    apply_schema(engine)
    with engine.begin() as conn:
        prune_legacy_seed_compat(conn)
        prune_mismatched_compat(conn)
        force = os.environ.get("FORCE_REINGEST", "").strip().lower() in ("1", "true", "yes")
        already = conn.execute(text("SELECT COUNT(*) FROM parts")).scalar()
        if already and already > 0 and not force:
            return {"skipped": True, "parts": already}
        if force:
            conn.execute(text("DELETE FROM embeddings WHERE source_type IN ('repair', 'article')"))
            conn.execute(text("DELETE FROM compatibility"))
            conn.execute(text("DELETE FROM parts"))
            conn.execute(text("DELETE FROM repair_guides"))
            conn.execute(text("DELETE FROM articles"))
        parts = ingest_parts(conn)
        demo_compat = _seed_demo_model_compat(conn)
        repairs = ingest_repairs(conn)
        articles = ingest_articles(conn)
    return {"skipped": False, "parts": parts, "demo_compat": demo_compat, "repairs": repairs, "articles": articles}


if __name__ == "__main__":
    print(run_ingestion())
