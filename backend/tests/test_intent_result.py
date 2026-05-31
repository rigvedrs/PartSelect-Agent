"""IntentResult schema validation — LLM boundary, no network."""
import pytest

from app.agent.router import Intent, IntentResult


def test_coerces_llm_null_string_part_query():
    r = IntentResult.model_validate({
        "intent": "parts_for_model",
        "part_query": "null",
        "browse_all_parts": False,
    })
    assert r.part_query is None
    assert r.catalog_filter_query("10650502990") is None


def test_browse_all_parts_skips_keyword_filter():
    r = IntentResult(
        intent=Intent.PARTS_FOR_MODEL,
        browse_all_parts=True,
        part_query="door hinge",
    )
    assert r.catalog_filter_query("10650502990") is None


def test_model_number_not_used_as_part_filter():
    r = IntentResult(
        intent=Intent.PARTS_FOR_MODEL,
        part_query="10650502990",
        browse_all_parts=False,
    )
    assert r.catalog_filter_query("10650502990") is None


def test_part_type_filter_preserved():
    r = IntentResult(
        intent=Intent.PARTS_FOR_MODEL,
        part_query="water filter",
        browse_all_parts=False,
    )
    assert r.catalog_filter_query("10650502990") == "water filter"


def test_coerces_invalid_ps_number():
    r = IntentResult.model_validate({
        "intent": "install",
        "ps_number": "NULL",
    })
    assert r.ps_number is None
