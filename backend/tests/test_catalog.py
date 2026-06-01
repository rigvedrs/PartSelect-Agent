"""Catalog resolver policy tests (no network)."""
from unittest.mock import patch

from app.config import CatalogSettings, LiveScrapeSettings, Settings
from app.agent.catalog import (
    CatalogRequest,
    CatalogScope,
    CatalogSource,
    _resolve_live_catalog,
    resolve_compatible_parts,
)


def _settings(*, live_enabled: bool = False, **catalog_kwargs) -> Settings:
    return Settings(
        database={
            "host": "postgres", "port": 5432, "name": "partselect",
            "user": "partselect", "password": "partselect",
        },
        redis={"host": "redis", "port": 6379, "db": 0},
        llm={
            "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",
            "api_key_env_var": "OPENROUTER_API_KEY", "tool_model": "m",
            "synthesis_model": "m", "tool_temperature": 0.0, "synthesis_temperature": 0.3,
        },
        embeddings={"model": "x", "dim": 384},
        retrieval={"top_k": 7, "hnsw_m": 16, "hnsw_ef_construction": 64},
        agent={"max_tool_iterations": 4},
        cache={
            "product_ttl_seconds": 86400, "compatibility_ttl_seconds": 86400,
            "retrieval_ttl_seconds": 3600,
        },
        scope={"appliance_keywords": ["refrigerator"], "out_of_scope_keywords": ["recipe"]},
        catalog=CatalogSettings(**catalog_kwargs),
        live_scrape=LiveScrapeSettings(enabled=live_enabled, backend="firecrawl"),
    )


def test_full_catalog_db_only_when_empty_and_live_disabled():
    req = CatalogRequest(model_number="UNKNOWN1", scope=CatalogScope.FULL, limit=10)
    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=[]), \
         patch("app.agent.catalog._resolve_live_catalog") as live:
        mock_settings.return_value = _settings(live_enabled=False, full_catalog_primary_source="none")
        out = resolve_compatible_parts(req)
    live.assert_not_called()
    assert out["source"] == CatalogSource.NONE.value
    assert "partselect.com/Models/UNKNOWN1" in out["reason"]


def test_full_catalog_uses_live_when_db_sparse_and_enabled():
    req = CatalogRequest(model_number="UNKNOWN1", scope=CatalogScope.FULL, limit=10)
    live_out = {
        "model_number": "UNKNOWN1",
        "parts": [{"ps_number": "PS1", "name": "Part", "source": "live"}],
        "count": 1,
        "source": CatalogSource.LIVE.value,
        "reason": "live",
    }
    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=[]), \
         patch("app.agent.catalog._resolve_live_catalog", return_value=live_out) as live:
        mock_settings.return_value = _settings(live_enabled=True, full_catalog_primary_source="none")
        out = resolve_compatible_parts(req)
    live.assert_called_once()
    assert out["source"] == CatalogSource.LIVE.value


def test_filtered_catalog_db_miss_uses_live_when_enabled():
    req = CatalogRequest(
        model_number="WRX735SDHZ00",
        scope=CatalogScope.BY_PART_TYPE,
        part_type_filter="wheels",
        limit=5,
    )
    live_out = {
        "model_number": "WRX735SDHZ00",
        "parts": [],
        "count": 0,
        "source": CatalogSource.NONE.value,
        "reason": "none",
    }
    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=[]), \
         patch("app.agent.catalog._resolve_live_catalog", return_value=live_out) as live:
        mock_settings.return_value = _settings(live_enabled=True)
        resolve_compatible_parts(req)
    live.assert_called_once()


def test_filtered_catalog_db_miss_returns_referral_when_live_disabled():
    req = CatalogRequest(
        model_number="WRX735SDHZ00",
        scope=CatalogScope.BY_PART_TYPE,
        part_type_filter="wheels",
        limit=5,
    )
    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=[]), \
         patch("app.agent.catalog._resolve_live_catalog") as live:
        mock_settings.return_value = _settings(live_enabled=False)
        out = resolve_compatible_parts(req)
    live.assert_not_called()
    assert out["count"] == 0
    assert "wheels" in out["reason"].lower()
    assert "partselect.com/Models/WRX735SDHZ00" in out["reason"]


def test_filtered_catalog_prefers_db():
    req = CatalogRequest(
        model_number="10650502990",
        scope=CatalogScope.BY_PART_TYPE,
        part_type_filter="water filter",
        limit=5,
    )
    db_row = [{"ps_number": "PS2", "name": "Water Filter", "compat_model": "10650502990"}]

    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=db_row) as db, \
         patch("app.agent.catalog._resolve_live_catalog") as live:
        mock_settings.return_value = _settings(live_enabled=True)
        out = resolve_compatible_parts(req)

    db.assert_called_once()
    live.assert_not_called()
    assert out["source"] == CatalogSource.DB.value


def test_full_catalog_uses_db_when_complete():
    req = CatalogRequest(model_number="M1", scope=CatalogScope.FULL, limit=10)
    db_rows = [{"ps_number": f"PS{i}", "name": f"P{i}", "compat_model": "M1"} for i in range(6)]

    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=db_rows), \
         patch("app.agent.catalog._resolve_live_catalog") as live:
        mock_settings.return_value = _settings(live_enabled=True, full_catalog_primary_source="none")
        out = resolve_compatible_parts(req)

    live.assert_not_called()
    assert out["source"] == CatalogSource.DB.value
    assert out["count"] == 6


def test_live_catalog_preserves_existing_db_image_when_live_lacks_one():
    class StubGateway:
        def fetch_model_parts(self, model, part_filter):
            from app.live_scrape.gateway import LiveResult
            return LiveResult(
                data=[{"ps_number": "PS1", "name": "Part", "product_url": "/p"}],
                source="live",
                backend="firecrawl",
                complete=True,
            )

        def fetch_part(self, ps, product_url=None):
            from app.live_scrape.gateway import LiveResult
            return LiveResult(
                data={"ps_number": ps, "name": "Part", "image_url": None},
                source="live",
                backend="firecrawl",
                complete=True,
            )

    with patch("app.live_scrape.gateway.get_gateway", return_value=StubGateway()):
        out = _resolve_live_catalog(
            "MODEL1",
            None,
            1,
            full_catalog=True,
            existing_parts=[{"ps_number": "PS1", "image_url": "https://example.test/part.jpg"}],
        )

    assert out["parts"][0]["image_url"] == "https://example.test/part.jpg"
