"""Unit tests for part_query / ps_number normalization (no LLM)."""
from app.agent.router import normalize_part_query, normalize_ps_number


def test_placeholder_part_query_is_none():
    assert normalize_part_query("null") is None
    assert normalize_part_query("NULL") is None
    assert normalize_part_query("none") is None
    assert normalize_part_query("") is None


def test_list_all_parts_clears_filter():
    assert normalize_part_query("null", "List all its parts") is None
    assert normalize_part_query("door hinge", "List all its parts") is None
    assert normalize_part_query("water filter", "find a water filter") == "water filter"


def test_normalize_ps_number():
    assert normalize_ps_number("NULL") is None
    assert normalize_ps_number("PS11752778") == "PS11752778"
