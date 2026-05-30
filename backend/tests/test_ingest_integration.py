import json
import os
import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires TEST_DATABASE_URL pointing at a pgvector Postgres",
)


def test_ingestion_loads_seed_and_compat(tmp_path, monkeypatch):
    from app.rag import ingest

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "parts.jsonl").write_text(json.dumps({
        "partselect_number": "PS999",
        "name": "Test Bin",
        "price": "10.00",
        "availability": "In Stock",
        "manufacturer": "Whirlpool",
        "model_cross_reference": [
            {"brand": "Whirlpool", "model_number": "M1", "description": "Refrigerator"}
        ],
    }) + "\n")
    (raw_dir / "repairs.jsonl").write_text("")
    (raw_dir / "articles.jsonl").write_text("")
    monkeypatch.setattr(ingest, "RAW_DIR", raw_dir)

    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(
            "DROP TABLE IF EXISTS cart_items, carts, sessions, embeddings, "
            "articles, repair_guides, compatibility, parts CASCADE"
        ))

    result = ingest.run_ingestion(engine)
    assert result["parts"] == 1

    with engine.connect() as conn:
        seed = conn.execute(
            text("SELECT category FROM parts WHERE ps_number='PS11752778'")
        ).scalar()
        assert seed == "refrigerator"

        compat = conn.execute(text(
            "SELECT COUNT(*) FROM compatibility "
            "WHERE ps_number='PS11752778' AND model_number='WDT780SAEM1'"
        )).scalar()
        assert compat == 1
