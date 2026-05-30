from scrapers.parts_scraper import parse_product


def test_parse_product_extracts_price():
    md = "# Refrigerator Door Shelf Bin\nIn Stock\nPrice: $47.40\n"
    result = parse_product("PS11752778", md)
    assert result["partselect_number"] == "PS11752778"
    assert result["price"] == "47.40"
    assert result["availability"] == "In Stock"
    assert result["name"] == "Refrigerator Door Shelf Bin"


def test_parse_product_no_price():
    md = "# Some Part\nOut of stock.\n"
    result = parse_product("PS99999", md)
    assert result["price"] is None
    assert result["availability"] is None
    assert result["name"] == "Some Part"


def test_parse_product_description_truncated():
    md = "# Part\n" + "x" * 1000
    result = parse_product("PS1", md)
    assert len(result["description"]) == 600


def test_parse_product_fallback_name():
    md = "no heading here"
    result = parse_product("PS123", md)
    assert result["name"] == "PS123"
