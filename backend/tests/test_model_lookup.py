"""Unit tests for model page link parsing (no network)."""
from scrapers.model_lookup import _filter_entries, parse_product_links_from_markdown


SAMPLE_MD = """
[![Refrigerator Water Filter – Part Number: EDR4RXD1](img)](https://www.partselect.com/PS11722130-Whirlpool-EDR4RXD1-Water-Filter.htm)
[![Refrigerator Screw WPW10661886](img)](https://www.partselect.com/PS11757021-Screw.htm)
[![Refrigerator Pivot Block](img)](https://www.partselect.com/PS11743531-Pivot.htm)
[![BULB-LIGHT W11338583](img)](https://www.partselect.com/PS12717432-Bulb.htm)
[Refrigerator Crisper Drawer with Humidity Control](https://www.partselect.com/PS11739119-Whirlpool-WP2188656-Refrigerator-Crisper-Drawer.htm)
"""


def test_parse_model_page_links():
    entries = parse_product_links_from_markdown(SAMPLE_MD)
    assert len(entries) == 5
    ps_map = {e["ps_number"]: e["name"] for e in entries}
    assert "Screw" in ps_map["PS11757021"]
    assert "Pivot" in ps_map["PS11743531"]
    assert "Crisper" in ps_map["PS11739119"]


def test_filter_screw_keyword():
    entries = parse_product_links_from_markdown(SAMPLE_MD)
    hits = _filter_entries(entries, ["screw"])
    assert len(hits) == 1
    assert hits[0]["ps_number"] == "PS11757021"


def test_filter_pivot_block_keywords():
    entries = parse_product_links_from_markdown(SAMPLE_MD)
    hits = _filter_entries(entries, ["pivot", "block"])
    assert len(hits) == 1
    assert hits[0]["ps_number"] == "PS11743531"


def test_filter_no_match_returns_empty():
    entries = parse_product_links_from_markdown(SAMPLE_MD)
    assert _filter_entries(entries, ["compressor"]) == []
