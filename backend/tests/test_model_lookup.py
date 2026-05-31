"""Unit tests for model page link parsing (no network)."""
from scrapers.model_lookup import _filter_entries, _URL_PS_RE
import re


SAMPLE_MD = """
[![Refrigerator Water Filter – Part Number: EDR4RXD1](img)](https://www.partselect.com/PS11722130-Whirlpool-EDR4RXD1-Water-Filter.htm)
[![Refrigerator Screw WPW10661886](img)](https://www.partselect.com/PS11757021-Screw.htm)
[![Refrigerator Pivot Block](img)](https://www.partselect.com/PS11743531-Pivot.htm)
[![BULB-LIGHT W11338583](img)](https://www.partselect.com/PS12717432-Bulb.htm)
"""


def _parse_sample() -> list[dict]:
    entries = []
    seen: set[str] = set()
    for line in SAMPLE_MD.splitlines():
        url_m = _URL_PS_RE.search(line)
        if not url_m:
            continue
        name_m = re.search(r"!\[([^\]]+)\]", line)
        if not name_m:
            continue
        ps = url_m.group(2).upper()
        if ps in seen:
            continue
        seen.add(ps)
        entries.append({
            "ps_number": ps,
            "name": name_m.group(1).strip(),
            "product_url": url_m.group(1),
        })
    return entries


def test_parse_model_page_links():
    entries = _parse_sample()
    assert len(entries) == 4
    ps_map = {e["ps_number"]: e["name"] for e in entries}
    assert "Screw" in ps_map["PS11757021"]
    assert "Pivot" in ps_map["PS11743531"]


def test_filter_screw_keyword():
    entries = _parse_sample()
    hits = _filter_entries(entries, ["screw"])
    assert len(hits) == 1
    assert hits[0]["ps_number"] == "PS11757021"


def test_filter_pivot_block_keywords():
    entries = _parse_sample()
    hits = _filter_entries(entries, ["pivot", "block"])
    assert len(hits) == 1
    assert hits[0]["ps_number"] == "PS11743531"


def test_filter_no_match_returns_empty():
    entries = _parse_sample()
    assert _filter_entries(entries, ["compressor"]) == []
