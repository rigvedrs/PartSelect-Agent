import pytest

from app.agent.guardrails import (
    is_in_scope,
    detect_cart_action,
    reconcile_cart_intent,
    assert_tool_allowed,
    IntentToolMismatchError,
    filter_graph_tools,
)
from app.agent.router import Intent


def test_appliance_query_passes():
    assert is_in_scope("my ice maker is not working") is True


def test_part_number_passes():
    assert is_in_scope("install PS11752778") is True


def test_pasta_recipe_blocked():
    assert is_in_scope("what is a good pasta recipe?") is False


def test_weather_blocked():
    assert is_in_scope("what is the weather today?") is False


def test_borderline_with_appliance_word_passes():
    assert is_in_scope("refrigerator not cooling, need a part") is True


def test_empty_string_passes():
    assert is_in_scope("") is True


def test_detect_cart_action_add():
    assert detect_cart_action("add it to cart") == "add"
    assert detect_cart_action("Add PS11752778 to cart") == "add"


def test_detect_cart_action_remove():
    assert detect_cart_action("remove it from cart") == "remove"
    assert detect_cart_action("delete PS11752778 from cart") == "remove"


def test_detect_cart_action_none_for_search():
    assert detect_cart_action("find a water filter") is None


def test_reconcile_cart_intent_overrides_wrong_classification():
    assert reconcile_cart_intent(Intent.REMOVE_FROM_CART, "add it to cart") == Intent.ADD_TO_CART
    assert reconcile_cart_intent(Intent.GENERAL, "add it to cart") == Intent.ADD_TO_CART
    assert reconcile_cart_intent(Intent.ADD_TO_CART, "remove it from cart") == Intent.REMOVE_FROM_CART


def test_assert_tool_allowed_blocks_mismatch():
    with pytest.raises(IntentToolMismatchError):
        assert_tool_allowed(Intent.ADD_TO_CART, "remove_from_cart")


def test_assert_tool_allowed_permits_match():
    assert_tool_allowed(Intent.ADD_TO_CART, "add_to_cart")
    assert_tool_allowed(Intent.REMOVE_FROM_CART, "remove_from_cart")


def test_filter_graph_tools_excludes_cart():
    names = filter_graph_tools([
        "search_parts_tool", "add_to_cart_tool", "remove_from_cart_tool",
    ])
    assert "add_to_cart_tool" not in names
    assert "remove_from_cart_tool" not in names
    assert "search_parts_tool" in names
