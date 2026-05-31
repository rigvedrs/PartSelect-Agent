"""Unit tests for troubleshoot RAG handler."""
import asyncio

import pytest
from langchain_core.messages import AIMessage

from app.agent.messages import TROUBLESHOOT_REDIRECT


def test_troubleshoot_appends_resource_footer(monkeypatch):
    from app.agent import troubleshoot_handler as th

    monkeypatch.setattr(th, "retrieve_troubleshoot_context", lambda msg, app: {
        "appliance_type": app,
        "symptom": msg,
        "causes": [{"symptom": "not draining", "cause": "Check drain pump.", "part_name": "Pump", "part": None, "score": 0.9}],
        "articles": [],
        "parts": [],
    })

    class FakeLLM:
        async def ainvoke(self, messages):
            return AIMessage(content="Try cleaning the drain filter and checking the pump.")

    monkeypatch.setattr(th, "get_llm", lambda role: FakeLLM())

    result = asyncio.run(th.generate_troubleshoot_answer("Dishwasher not draining"))
    assert "drain filter" in result["text"]
    assert TROUBLESHOOT_REDIRECT in result["text"]
    assert "Instant-Repairman" in result["text"]
    assert "partselect.com/Repair" in result["text"]


def test_detect_appliance_type():
    from app.agent.tools.troubleshoot import detect_appliance_type

    assert detect_appliance_type("Dishwasher not draining") == "dishwasher"
    assert detect_appliance_type("Ice maker not working") == "refrigerator"
