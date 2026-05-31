import asyncio

import pytest


def test_sse_line_format():
    from app.routers.sse import sse_line, sse_token, sse_done, sse_stage
    assert sse_line({"token": "hi"}) == b'data: {"token": "hi"}\n\n'
    assert b"token" in sse_token("x")
    assert b'"done": true' in sse_done({"session_id": "s1", "text": "ok"})
    assert sse_stage("Understanding your request...") == (
        b'data: {"stage": "Understanding your request..."}\n\n'
    )


def test_stream_static_response():
    from app.routers.sse import stream_static_response

    async def _collect():
        return [c async for c in stream_static_response({"session_id": "s1", "text": "hi"})]

    chunks = asyncio.run(_collect())
    assert len(chunks) == 1
    assert b'"done": true' in chunks[0]
    assert b'"text": "hi"' in chunks[0]
