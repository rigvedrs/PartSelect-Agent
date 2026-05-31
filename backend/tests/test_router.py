from app.agent.router import classify_intent, routing_query, Intent


def test_part_number_lookup():
    assert classify_intent("how do I install PS11752778?") == Intent.INSTALL


def test_compatibility_check():
    assert classify_intent("is PS11752778 compatible with WDT780SAEM1?") == Intent.COMPATIBILITY


def test_parts_for_model():
    assert classify_intent("what parts are compatible with WRS325SDHZ?") == Intent.PARTS_FOR_MODEL


def test_troubleshoot():
    assert classify_intent("my ice maker is not working") == Intent.TROUBLESHOOT


def test_search():
    assert classify_intent("find a water filter for my fridge") == Intent.SEARCH


def test_add_to_cart():
    assert classify_intent("add PS11752778 to cart") == Intent.ADD_TO_CART


def test_remove_from_cart():
    assert classify_intent("remove PS11752778 from cart") == Intent.REMOVE_FROM_CART


def test_complex_multi_step():
    assert classify_intent("my dishwasher is leaking, fix it and order the part") == Intent.COMPLEX


def test_unknown_falls_to_complex():
    assert classify_intent("tell me about door bins") == Intent.COMPLEX


def test_routing_last_line():
    assert routing_query("hello\nremove PS11752778 from cart") == "remove PS11752778 from cart"
