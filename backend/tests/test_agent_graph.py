"""Regression test: tool-using agent queries must return non-empty text."""
import os
import asyncio
import pytest

pytestmark = pytest.mark.skipif(
    not (os.getenv("TEST_DATABASE_URL") and os.getenv("OPENROUTER_API_KEY")),
    reason="requires Postgres + OPENROUTER_API_KEY",
)


def test_tool_using_query_returns_nonempty():
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PASSWORD", "partselect")
    from app.agent.graph import run_agent_streaming

    async def go() -> str:
        out = []
        async for chunk in run_agent_streaming("test-graph", "What is part PS11752778?", None, []):
            out.append(chunk)
        return "".join(out)

    text = asyncio.run(go())
    assert text.strip(), "agent returned empty text for a tool-using query"
