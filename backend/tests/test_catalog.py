"""Catalog resolver policy tests (no network)."""
from unittest.mock import patch

from app.agent.catalog import CatalogRequest, CatalogScope, CatalogSource, resolve_compatible_parts
from app.config import CatalogSettings


def _settings(**kwargs) -> CatalogSettings:
    return CatalogSettings(**kwargs)


def test_full_catalog_prefers_live_when_configured():
    req = CatalogRequest(model_number="10650502990", scope=CatalogScope.FULL, limit=10)
    live_row = [{"ps_number": "PS1", "name": "Filter", "compat_model": "10650502990"}]

    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog._live_enabled", return_value=True), \
         patch("app.agent.catalog.sources.fetch_from_live", return_value=live_row) as live, \
         patch("app.agent.catalog.sources.fetch_from_db") as db:
        mock_settings.return_value.catalog = _settings(full_catalog_primary_source="live")
        out = resolve_compatible_parts(req)

    live.assert_called_once()
    db.assert_not_called()
    assert out["source"] == CatalogSource.LIVE.value
    assert out["count"] == 1


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


def test_full_catalog_uses_db_when_primary_db_and_coverage_sufficient():
    req = CatalogRequest(model_number="M1", scope=CatalogScope.FULL, limit=10)
    db_rows = [{"ps_number": f"PS{i}", "name": f"P{i}", "compat_model": "M1"} for i in range(6)]

    with patch("app.agent.catalog.load_settings") as mock_settings, \
         patch("app.agent.catalog._live_enabled", return_value=True), \
         patch("app.agent.catalog.sources.fetch_from_db", return_value=db_rows) as db, \
         patch("app.agent.catalog.sources.fetch_from_live") as live:
        mock_settings.return_value.catalog = _settings(
            full_catalog_primary_source="db",
            db_completeness_min_parts=5,
        )
        out = resolve_compatible_parts(req)

    live.assert_not_called()
    assert out["source"] == CatalogSource.DB.value
    assert out["count"] == 6
