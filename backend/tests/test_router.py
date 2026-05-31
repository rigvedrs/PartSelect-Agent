import asyncio
import os

import pytest

from app.agent.router import classify_intent, extract_model_number, Intent

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="requires OPENROUTER_API_KEY for LLM intent classification",
)


def _classify(message: str, session_model: str | None = None):
    return asyncio.run(classify_intent(message, session_model=session_model))


def test_extract_model_number_ignores_ps():
    assert extract_model_number("WRX735SDHZ00") == "WRX735SDHZ00"
    assert extract_model_number("check PS11752778 for WDT780SAEM1") == "WDT780SAEM1"


def test_part_number_lookup():
    assert _classify("how do I install PS11752778?").intent == Intent.INSTALL


def test_compatibility_check():
    assert _classify("is PS11752778 compatible with WDT780SAEM1?").intent == Intent.COMPATIBILITY


def test_parts_for_model():
    assert _classify("what parts are compatible with WRS325SDHZ?").intent == Intent.PARTS_FOR_MODEL


def test_troubleshoot():
    assert _classify("my ice maker is not working").intent == Intent.TROUBLESHOOT


def test_search():
    assert _classify("find a water filter for my fridge").intent == Intent.SEARCH


def test_add_to_cart():
    assert _classify("add PS11752778 to cart").intent == Intent.ADD_TO_CART


def test_remove_from_cart():
    assert _classify("remove PS11752778 from cart").intent == Intent.REMOVE_FROM_CART


def test_multiline_remove_from_cart():
    r = _classify("I was asking about pasta.\nremove PS11752778 from cart")
    assert r.intent == Intent.REMOVE_FROM_CART


def test_general_multi_step():
    r = _classify("my dishwasher is leaking, fix it and order the part")
    assert r.intent in (Intent.GENERAL, Intent.TROUBLESHOOT)


def test_session_context_parts_for_model():
    r = _classify("list all its parts", session_model="WRX735SDHZ00")
    assert r.intent == Intent.PARTS_FOR_MODEL
