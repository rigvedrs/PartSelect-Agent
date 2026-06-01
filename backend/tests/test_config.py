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
    assert s.live_scrape.enabled is True
    assert s.live_scrape.backend == "firecrawl"

def test_database_url_is_psycopg():
    s = load_settings(CONFIG)
    assert s.database.url().startswith("postgresql+psycopg://")


def test_database_url_full():
    s = load_settings(CONFIG)
    assert s.database.url() == "postgresql+psycopg://partselect:partselect@postgres:5432/partselect"


def test_database_url_uses_env_password(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "supersecret")
    s = load_settings(CONFIG)
    assert ":supersecret@" in s.database.url()


def test_llm_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    s = load_settings(CONFIG)
    assert s.llm.api_key == "test-key-123"


def test_llm_api_key_none_when_absent(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    s = load_settings(CONFIG)
    assert s.llm.api_key is None
