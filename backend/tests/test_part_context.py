from app.agent.part_context import (
    match_parts_by_query,
    pick_best_part_match,
    resolve_ps_for_cart,
)


PARTS = [
    {"ps_number": "PS11722130", "name": "Refrigerator Water Filter EDR4RXD1"},
    {"ps_number": "PS12731165", "name": "Refrigerator Water Filter Bypass W11395888"},
    {"ps_number": "PS11743531", "name": "Refrigerator Pivot Block – Part Number: WP67003405"},
]


def test_match_water_filter_excludes_pivot():
    matches = match_parts_by_query(PARTS, "water filter")
    assert len(matches) == 2
    assert all("water filter" in m["name"].lower() for m in matches)


def test_pick_best_prefers_non_bypass():
    matches = match_parts_by_query(PARTS, "water filter")
    best = pick_best_part_match(matches, "also add the water filter to the cart")
    assert best["ps_number"] == "PS11722130"


def test_add_it_ignores_classifier_wrong_ps():
    ps = resolve_ps_for_cart(
        "add it to cart", "PS11722130", "water filter",
        last_parts=[PARTS[2]],
        recent_parts=PARTS,
    )
    assert ps == "PS11743531"


def test_named_part_in_message_matches_history():
    ps = resolve_ps_for_cart(
        "I mean add the pivot block to cart",
        None, None,
        last_parts=[PARTS[2]],
        recent_parts=PARTS,
    )
    assert ps == "PS11743531"


def test_add_it_uses_latest_single_part():
    ps = resolve_ps_for_cart(
        "add it to cart", None, None,
        last_parts=[PARTS[2]],
        recent_parts=PARTS,
    )
    assert ps == "PS11743531"


def test_add_named_part_from_history_not_latest():
    ps = resolve_ps_for_cart(
        "also add the water filter to the cart",
        None,
        "water filter",
        last_parts=[PARTS[2]],
        recent_parts=PARTS,
    )
    assert ps == "PS11722130"


def test_explicit_ps_wins():
    ps = resolve_ps_for_cart(
        "add PS12731165 to cart",
        None,
        "water filter",
        last_parts=[PARTS[2]],
        recent_parts=PARTS,
    )
    assert ps == "PS12731165"
