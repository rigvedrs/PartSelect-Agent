import os
import pytest
from langchain_core.messages import AIMessage, HumanMessage

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires TEST_DATABASE_URL",
)


@pytest.fixture
def session_id():
    from app.services.session_service import create_session
    return create_session()


def test_to_langchain_messages():
    from app.services.chat_history_service import to_langchain_messages
    rows = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    msgs = to_langchain_messages(rows)
    assert len(msgs) == 2
    assert isinstance(msgs[0], HumanMessage)
    assert isinstance(msgs[1], AIMessage)


def test_metadata_json_serializes_decimal_prices():
    from decimal import Decimal
    from app.services.chat_history_service import _metadata_json

    raw = _metadata_json({
        "parts": [{"ps_number": "PS1", "name": "Filter", "price": Decimal("42.8300")}],
    })
    assert raw is not None
    parsed = __import__("json").loads(raw)
    assert parsed["parts"][0]["price"] == 42.83


def test_load_and_record_exchange(session_id):
    from app.services.chat_history_service import (
        load_langchain_history,
        record_exchange,
        load_messages,
        load_ui_messages,
        record_assistant_response,
    )
    record_exchange(session_id, "first question", "first answer")
    record_assistant_response(session_id, "part search", {
        "text": "Found 2 parts",
        "parts": [{"ps_number": "PS1", "name": "Filter"}],
    })

    rows = load_messages(session_id)
    assert len(rows) == 4
    assert rows[-1]["content"] == "Found 2 parts"
    assert rows[-1]["metadata"] is not None

    ui = load_ui_messages(session_id)
    assert ui[-1]["parts"][0]["ps_number"] == "PS1"

    lc = load_langchain_history(session_id)
    assert len(lc) == 4
    assert lc[0].content == "first question"
    assert lc[-1].content == "Found 2 parts"


def test_agent_chat_passes_history_to_graph(session_id, monkeypatch):
    """Follow-up troubleshoot request should include prior turns in history."""
    from fastapi.testclient import TestClient
    from app.main import app

    captured_history = []

    async def fake_streaming(sid, message, appliance_model, history):
        captured_history.append(list(history))
        yield "follow-up response"

    monkeypatch.setattr("app.routers.chat.run_agent_streaming", fake_streaming)

    client = TestClient(app)
    # Deterministic turn (stored in DB)
    client.post("/api/chat", json={
        "session_id": session_id,
        "message": "find a water filter for my fridge",
        "stream": False,
    })
    # Agent turn
    client.post("/api/chat", json={
        "session_id": session_id,
        "message": "tell me more about the first one",
        "stream": False,
    })

    assert len(captured_history) == 1
    hist = captured_history[0]
    assert len(hist) >= 2
    assert any(isinstance(m, HumanMessage) for m in hist)
    assert any(isinstance(m, AIMessage) for m in hist)
