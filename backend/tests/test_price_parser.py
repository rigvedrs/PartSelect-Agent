from scrapers.product_utils import parse_product_price, clean_product_url


SAMPLE_MD = """
# Refrigerator Water Filter EDR4RXD1

$Price Match

$84.45

In Stock

Add to cart
"""


def test_parse_product_price_before_in_stock():
    assert parse_product_price(SAMPLE_MD) == "84.45"


def test_clean_product_url_strips_junk():
    raw = (
        'https://www.partselect.com/PS11743531-Whirlpool-WP67003405-Refrigerator-Pivot-Block.htm'
        '?SourceCode=19 "Refrigerator Pivot Block"'
    )
    assert clean_product_url(raw).endswith(".htm")
    assert " " not in clean_product_url(raw)
