"""Unit tests for tool functions using mocked DB connections."""
import pytest
from unittest.mock import MagicMock, patch


def make_mock_conn(rows=None, scalar=None):
    conn = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = rows[0] if rows else None
    result.mappings.return_value.all.return_value = rows or []
    result.scalar.return_value = scalar
    conn.execute.return_value = result
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)
    return conn


def test_search_parts_finds_by_ps_number():
    from app.agent.tools.search_parts import search_parts
    mock_part = {"ps_number": "PS11752778", "name": "Refrigerator Door Shelf Bin",
                 "price": 47.40, "category": "refrigerator"}
    mock_engine = MagicMock()
    mock_engine.connect.return_value = make_mock_conn(rows=[mock_part])
    with patch("app.agent.tools.search_parts.get_engine", return_value=mock_engine):
        results = search_parts("PS11752778")
    assert len(results) == 1
    assert results[0]["ps_number"] == "PS11752778"


def test_check_compatibility_compatible():
    from app.agent.tools.check_compatibility import check_compatibility
    mock_engine = MagicMock()
    compat_row = {"model_number": "WDT780SAEM1", "brand": "Whirlpool", "appliance": "refrigerator"}
    part_row = {"name": "Refrigerator Door Shelf Bin", "price": 47.40, "image_url": None, "product_url": None}

    conn = MagicMock()
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)
    call_count = [0]

    def side_effect(query, params=None):
        result = MagicMock()
        # First call: compat query; second call: part lookup
        result.mappings.return_value.first.return_value = (
            compat_row if call_count[0] == 0 else part_row
        )
        call_count[0] += 1
        return result

    conn.execute.side_effect = side_effect
    mock_engine.connect.return_value = conn
    with patch("app.agent.tools.check_compatibility.get_engine", return_value=mock_engine):
        result = check_compatibility("WDT780SAEM1", "PS11752778")
    assert result["compatible"] is True


def test_check_compatibility_not_found():
    from app.agent.tools.check_compatibility import check_compatibility
    mock_engine = MagicMock()
    conn = make_mock_conn(rows=None)
    mock_engine.connect.return_value = conn
    with patch("app.agent.tools.check_compatibility.get_engine", return_value=mock_engine):
        result = check_compatibility("MODEL123", "UNKNOWN")
    assert result["compatible"] is False


def test_get_installation_guide_with_steps():
    from app.agent.tools.get_installation import get_installation_guide
    mock_engine = MagicMock()
    part_row = {
        "name": "Refrigerator Door Shelf Bin",
        "description": "Genuine OEM part.",
        "installation_steps": ["Step 1", "Step 2"],
        "image_url": None,
        "product_url": None,
    }
    mock_engine.connect.return_value = make_mock_conn(rows=[part_row])
    with patch("app.agent.tools.get_installation.get_engine", return_value=mock_engine):
        result = get_installation_guide("PS11752778")
    assert result["found"] is True
    assert result["steps"] == ["Step 1", "Step 2"]


def test_add_to_cart_success():
    from app.agent.tools.add_to_cart import add_to_cart
    mock_engine = MagicMock()
    part_row = {"ps_number": "PS11752778", "name": "Refrigerator Door Shelf Bin",
                "price": 47.40, "image_url": None}
    item_rows = [{"ps_number": "PS11752778", "quantity": 1, "name": "Refrigerator Door Shelf Bin",
                  "price": 47.40}]

    conn = MagicMock()
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)
    call_count = [0]

    def side_effect(query, params=None):
        result = MagicMock()
        result.mappings.return_value.first.return_value = part_row
        result.mappings.return_value.all.return_value = item_rows
        call_count[0] += 1
        return result

    conn.execute.side_effect = side_effect
    mock_engine.connect.return_value = conn
    mock_engine.begin.return_value = conn
    with patch("app.agent.tools.add_to_cart.get_engine", return_value=mock_engine):
        result = add_to_cart("session-1", "PS11752778")
    assert result["success"] is True
    assert result["cart_total"] == 47.40


def test_add_to_cart_does_not_enrich_complete_db_part():
    from app.agent.tools.add_to_cart import add_to_cart
    from app.observability import RequestTrace
    mock_engine = MagicMock()
    part_row = {
        "ps_number": "PS11752778",
        "name": "Refrigerator Door Shelf Bin",
        "price": 47.40,
        "stock_status": "In Stock",
        "brand": "Whirlpool",
        "product_url": "https://www.partselect.com/PS11752778-Part.htm",
        "image_url": "https://example.test/bin.jpg",
    }
    item_rows = [{
        "ps_number": "PS11752778",
        "quantity": 1,
        "name": "Refrigerator Door Shelf Bin",
        "price": 47.40,
        "image_url": "https://example.test/bin.jpg",
        "product_url": "https://www.partselect.com/PS11752778-Part.htm",
    }]

    conn = MagicMock()
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)

    def side_effect(query, params=None):
        result = MagicMock()
        result.mappings.return_value.first.return_value = part_row
        result.mappings.return_value.all.return_value = item_rows
        return result

    conn.execute.side_effect = side_effect
    mock_engine.connect.return_value = conn
    mock_engine.begin.return_value = conn
    trace = RequestTrace(req_id="unit")
    with trace.activate(), \
         patch("app.agent.tools.add_to_cart.get_engine", return_value=mock_engine), \
         patch("app.agent.tools.add_to_cart.enrich_part_details") as enrich:
        result = add_to_cart("session-1", "PS11752778")

    enrich.assert_not_called()
    assert "tool_add_to_cart" in trace.timings
    assert result["success"] is True
    assert result["cart_total"] == 47.40


def test_enrich_part_details_preserves_existing_image_when_live_has_none():
    from app.agent.tools.part_enrichment import enrich_part_details

    part = {
        "ps_number": "PS11752778",
        "name": "Refrigerator Door Shelf Bin",
        "price": None,
        "product_url": "https://www.partselect.com/PS11752778-Part.htm",
        "image_url": "https://example.test/existing.jpg",
    }
    raw = {
        "partselect_number": "PS11752778",
        "name": "Refrigerator Door Shelf Bin",
        "price": "$49.99",
        "main_image": None,
    }

    with patch("app.live_scrape.gateway.get_gateway") as gateway, \
         patch("scrapers.parts_scraper.scrape_and_parse", return_value=raw), \
         patch("scrapers.product_utils.clean_product_url", return_value=part["product_url"]):
        gateway.return_value.is_enabled.return_value = True
        result = enrich_part_details(part)

    assert result["price"] == 49.99
    assert result["image_url"] == "https://example.test/existing.jpg"


def test_search_parts_fallback_not_called_when_db_has_result():
    """When the DB has the part, live scrape should never be called."""
    from app.agent.tools.search_parts import search_parts
    mock_part = {"ps_number": "PS11752778", "name": "Refrigerator Door Shelf Bin",
                 "price": 47.40, "category": "refrigerator"}
    mock_engine = MagicMock()
    mock_engine.connect.return_value = make_mock_conn(rows=[mock_part])
    with patch("app.agent.tools.search_parts.get_engine", return_value=mock_engine), \
         patch("app.agent.tools.search_parts._live_scrape_fallback") as mock_live:
        results = search_parts("PS11752778")
    mock_live.assert_not_called()
    assert len(results) == 1


def test_search_parts_fallback_returns_empty_when_scrape_unavailable():
    """Fallback returns [] when live scrape is disabled or scrape fails."""
    with patch("app.live_scrape.gateway.get_gateway") as mock_gw:
        mock_gw.return_value.is_enabled.return_value = False
        from app.agent.tools.search_parts import _live_scrape_fallback
        result = _live_scrape_fallback("PS99999999")
    assert result == []
