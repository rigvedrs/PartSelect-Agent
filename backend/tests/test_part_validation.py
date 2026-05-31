"""Tests for part row validation."""
from app.agent.tools.part_validation import is_valid_part


def test_rejects_page_not_found():
    assert not is_valid_part({"ps_number": "PS123", "name": "Page Not Found"})


def test_accepts_normal_part():
    assert is_valid_part({"ps_number": "PS11757021", "name": "Refrigerator Screw"})
