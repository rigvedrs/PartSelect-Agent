"""Tests for catalog merge (no network/DB)."""
from pathlib import Path

from scrapers.merge_catalog import merge_parts_catalog


def test_merge_updates_price_preserves_crossref(tmp_path):
    base = tmp_path / "parts.jsonl"
    fresh = tmp_path / "fresh.jsonl"
    out = tmp_path / "merged.jsonl"

    base.write_text(
        '{"partselect_number":"PS1","price":"10.00","model_cross_reference":[{"model_number":"M1"}]}\n'
        '{"partselect_number":"PS2","price":"20.00","model_cross_reference":[]}\n'
    )
    fresh.write_text(
        '{"partselect_number":"PS1","price":"12.50","name":"Updated Filter"}\n'
    )

    stats = merge_parts_catalog(base_path=base, fresh_paths=[fresh], out_path=out, backup=False)
    assert stats["updated_from_fresh"] == 1
    assert stats["total_parts"] == 2

    rows = {r["partselect_number"]: r for r in __import__("scrapers.io_utils", fromlist=["iter_jsonl"]).iter_jsonl(out)}
    assert rows["PS1"]["price"] == "12.50"
    assert rows["PS1"]["model_cross_reference"] == [{"model_number": "M1"}]
