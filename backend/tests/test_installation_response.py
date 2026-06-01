"""Tests for installation response formatting."""
from app.agent.tools.get_installation import format_installation_response


def test_format_not_found():
    text = format_installation_response({"found": False, "steps": []}, "PS12731165")
    assert "couldn't find" in text.lower()
    assert "PS12731165" in text


def test_format_with_steps():
    guide = {
        "found": True,
        "part_name": "Water Filter Bypass",
        "steps": ["Snap out the old part.", "Connect the water line."],
        "source": "live",
        "product_url": "https://www.partselect.com/PS12731165.htm",
    }
    text = format_installation_response(guide, "PS12731165")
    assert "Water Filter Bypass" in text
    assert "1. Snap out" in text
    assert "2. Connect" in text
    assert "live from PartSelect" in text
