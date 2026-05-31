"""Catalog resolver policy tests (no network)."""
from unittest.mock import patch

from app.agent.catalog import CatalogRequest, CatalogScope, CatalogSource, resolve_compatible_parts
from app.config import CatalogSettings


def _settings(**kwargs) -> CatalogSettings:
    return CatalogSettings(**kwargs)


def test_full_catalog_db_only_when_empty_returns_referral():
    req = CatalogRequest(model_number="UNKNOWN1", scope=CatalogScope.FULL, limit=10)
    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=[]), \
         patch("app.agent.catalog.sources.fetch_from_live") as live:
        mock_settings.return_value.catalog = _settings(full_catalog_primary_source="none")
        out = resolve_compatible_parts(req)
    live.assert_not_called()
    assert out["source"] == CatalogSource.NONE.value
    assert "partselect.com/Models/UNKNOWN1" in out["reason"]


def test_filtered_catalog_db_miss_returns_referral_without_live():
    req = CatalogRequest(
        model_number="WRX735SDHZ00",
        scope=CatalogScope.BY_PART_TYPE,
        part_type_filter="wheels",
        limit=5,
    )
    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=[]), \
         patch("app.agent.catalog.sources.fetch_from_live") as live:
        mock_settings.return_value.catalog = _settings()
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
         patch("app.agent.catalog.sources.fetch_from_live") as live:
        mock_settings.return_value.catalog = _settings()
        out = resolve_compatible_parts(req)

    db.assert_called_once()
    live.assert_not_called()
    assert out["source"] == CatalogSource.DB.value


def test_full_catalog_uses_db():
    req = CatalogRequest(model_number="M1", scope=CatalogScope.FULL, limit=10)
    db_rows = [{"ps_number": f"PS{i}", "name": f"P{i}", "compat_model": "M1"} for i in range(6)]

    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=db_rows), \
         patch("app.agent.catalog.sources.fetch_from_live") as live:
        mock_settings.return_value.catalog = _settings(full_catalog_primary_source="none")
        out = resolve_compatible_parts(req)

    live.assert_not_called()
    assert out["source"] == CatalogSource.DB.value
    assert out["count"] == 6
