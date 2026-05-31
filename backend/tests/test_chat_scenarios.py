"""Exhaustive chat scenario tests — run with live Postgres (TEST_DATABASE_URL)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SCENARIOS_PATH = Path(__file__).parent / "scenarios" / "chat_scenarios.json"

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires TEST_DATABASE_URL and running Postgres",
)


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PASSWORD", "partselect")
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def scenarios():
    return json.loads(SCENARIOS_PATH.read_text())


def _chat(client, session_id: str, message: str, appliance_model: str | None = None):
    body = {"session_id": session_id, "message": message, "stream": False}
    if appliance_model is not None:
        body["appliance_model"] = appliance_model
    return client.post("/api/chat", json=body)


def _new_session(client):
    return client.post("/api/session").json()["session_id"]


def _assert_expectations(data: dict, expect: dict, session_id: str, client):
    if expect.get("out_of_scope"):
        assert data.get("out_of_scope") is True
    if expect.get("not_out_of_scope"):
        assert not data.get("out_of_scope")
    if expect.get("no_model_assumption"):
        text = (data.get("text") or "").lower()
        assert "wdt780saem1" not in text
        assert "whirlpool dishwasher model" not in text
    if expect.get("has_installation_steps"):
        assert data.get("installation_steps")
        if expect.get("min_steps"):
            assert len(data["installation_steps"]) >= expect["min_steps"]
    if expect.get("compatibility_compatible") is True:
        assert data.get("compatibility", {}).get("compatible") is True
    if expect.get("compatibility_compatible") is False:
        assert data.get("compatibility", {}).get("compatible") is False
    if expect.get("min_parts") is not None:
        parts = data.get("parts") or []
        assert len(parts) >= expect["min_parts"]
        if expect.get("all_parts_have_compat_model"):
            model = expect["all_parts_have_compat_model"].upper()
            for p in parts:
                assert p.get("compat_model", "").upper() == model
    if expect.get("text_contains"):
        assert expect["text_contains"].lower() in (data.get("text") or "").lower()
    if expect.get("has_text"):
        assert (data.get("text") or "").strip()
    if expect.get("cart_min_count") is not None:
        cart = client.get(f"/api/cart/{session_id}").json()
        assert cart["count"] >= expect["cart_min_count"]
    if expect.get("cart_count") is not None:
        cart = client.get(f"/api/cart/{session_id}").json()
        assert cart["count"] == expect["cart_count"]
    if expect.get("source"):
        actual = data.get("source") or data.get("compatibility", {}).get("source")
        assert actual == expect["source"], f"expected source={expect['source']!r} got {actual!r}"


@pytest.mark.parametrize("scenario", json.loads(SCENARIOS_PATH.read_text()), ids=lambda s: s["id"])
def test_chat_scenario(client, scenario):
    if scenario.get("requires_llm") and not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY required for LLM scenarios")

    sid = _new_session(client)

    if scenario.get("setup", {}).get("precart_ps"):
        _chat(client, sid, f"add {scenario['setup']['precart_ps']} to cart")

    if "sequence" in scenario:
        for step in scenario["sequence"]:
            r = _chat(client, sid, step["message"])
            assert r.status_code == 200
            _assert_expectations(r.json(), step["expect"], sid, client)
        return

    r = _chat(client, sid, scenario["message"])
    assert r.status_code == 200
    _assert_expectations(r.json(), scenario["expect"], sid, client)


def test_list_compatible_parts_only_returns_verified_rows():
    from app.agent.tools.list_compatible_parts import list_compatible_parts

    result = list_compatible_parts("10650502990", "water filter", limit=5)
    assert result["count"] >= 1
    for p in result["parts"]:
        assert p.get("compat_model", "").upper() == "10650502990"


def test_routing_query_uses_last_sentence():
    from app.agent.router import routing_query, classify_intent, Intent

    q = routing_query("I was asking about pasta.\nremove PS11752778 from cart")
    assert "remove" in q.lower()
    assert classify_intent("I was asking about pasta.\nremove PS11752778 from cart") == Intent.REMOVE_FROM_CART
