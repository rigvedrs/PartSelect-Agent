from pathlib import Path
from app.config import load_settings

CONFIG = Path(__file__).resolve().parents[2] / "config.toml"

def test_loads_database_and_models():
    s = load_settings(CONFIG)
    assert s.database.name == "partselect"
    assert s.database.port == 5432
    assert s.embeddings.dim == 384
    assert s.llm.tool_temperature == 0.0
    assert "refrigerator" in s.scope.appliance_keywords

def test_database_url_is_psycopg():
    s = load_settings(CONFIG)
    assert s.database.url().startswith("postgresql+psycopg://")
