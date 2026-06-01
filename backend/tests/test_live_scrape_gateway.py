"""Unit tests for live scrape gateway (no network)."""
from unittest.mock import MagicMock, patch

import pytest

from app.live_scrape.gateway import LiveScrapeGateway, LiveResult


@pytest.fixture
def gateway():
    return LiveScrapeGateway()


def test_fetch_part_disabled_returns_empty(gateway):
    with patch("app.live_scrape.settings.is_available", return_value=False):
        result = gateway.fetch_part("PS11752778")
    assert result.data is None
    assert result.complete is False


def test_fetch_part_rejects_junk_page(gateway):
    raw = {"partselect_number": "PS999", "name": "Page Not Found", "price": None}
    with patch("app.live_scrape.settings.is_available", return_value=True), \
         patch("app.live_scrape.settings.resolve_backend", return_value="firecrawl"), \
         patch("scrapers.parts_scraper.scrape_and_parse", return_value=raw), \
         patch("app.ingest_models.reshape_part", return_value={
             "ps_number": "PS999", "name": "Page Not Found", "price": None,
         }):
        result = gateway.fetch_part("PS999")
    assert result.data is None


@pytest.mark.parametrize("backend", ["firecrawl", "selenium"])
def test_fetch_part_success(backend, gateway):
    shaped = {
        "ps_number": "PS11752778",
        "name": "Refrigerator Door Shelf Bin",
        "price": 47.40,
        "stock_status": "In Stock",
        "brand": "Whirlpool",
        "product_url": "https://www.partselect.com/PS11752778.htm",
        "image_url": None,
        "description": "Genuine OEM part.",
        "category": "refrigerator",
        "installation_steps": [],
        "video_url": None,
        "symptoms": [],
        "replaces": [],
    }
    raw = {"partselect_number": "PS11752778", "name": shaped["name"], "price": "47.40"}
    with patch("app.live_scrape.settings.is_available", return_value=True), \
         patch("app.live_scrape.settings.resolve_backend", return_value=backend), \
         patch("scrapers.parts_scraper.scrape_and_parse", return_value=raw), \
         patch("app.ingest_models.reshape_part", return_value=shaped):
        result = gateway.fetch_part("PS11752778")
    assert result.data is not None
    assert result.data["ps_number"] == "PS11752778"
    assert result.source == "live"
    assert result.backend == backend
    assert result.complete is True


def test_fetch_installation_missing_steps(gateway):
    raw = {
        "name": "Water Filter",
        "installation_steps": [],
        "product_url": "https://www.partselect.com/PS1.htm",
    }
    with patch("app.live_scrape.settings.is_available", return_value=True), \
         patch("app.live_scrape.settings.resolve_backend", return_value="firecrawl"), \
         patch("scrapers.parts_scraper.scrape_installation_record", return_value=raw):
        result = gateway.fetch_installation("PS1")
    assert result.data is not None
    assert result.data["steps"] == []
    assert result.complete is False
    assert result.missing_fields == ("installation_steps",)


def test_check_compat_on_model_page_found(gateway):
    stubs = [{"ps_number": "PS11752778", "name": "Shelf Bin", "product_url": "http://x"}]
    page_result = LiveResult(
        data=stubs, source="live", backend="firecrawl", complete=True,
    )
    with patch("app.live_scrape.settings.is_available", return_value=True), \
         patch("app.live_scrape.settings.resolve_backend", return_value="firecrawl"), \
         patch.object(gateway, "fetch_model_parts", return_value=page_result):
        result = gateway.check_compat_on_model_page("WDT780SAEM1", "PS11752778")
    assert result.data["compatible"] is True


def test_check_compat_on_model_page_not_found(gateway):
    stubs = [{"ps_number": "PS99999999", "name": "Other", "product_url": "http://x"}]
    page_result = LiveResult(
        data=stubs, source="live", backend="firecrawl", complete=True,
    )
    with patch("app.live_scrape.settings.is_available", return_value=True), \
         patch("app.live_scrape.settings.resolve_backend", return_value="firecrawl"), \
         patch.object(gateway, "fetch_model_parts", return_value=page_result):
        result = gateway.check_compat_on_model_page("WDT780SAEM1", "PS11752778")
    assert result.data["compatible"] is False
