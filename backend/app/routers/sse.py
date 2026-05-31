"""Server-Sent Events helpers for chat streaming."""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.json_util import dumps_json


def sse_line(data: dict[str, Any]) -> bytes:
    return f"data: {dumps_json(data)}\n\n".encode()


def sse_token(token: str) -> bytes:
    return sse_line({"token": token})


def sse_done(payload: dict[str, Any]) -> bytes:
    return sse_line({"done": True, **payload})


async def stream_static_response(payload: dict[str, Any]) -> AsyncIterator[bytes]:
    """Emit a deterministic handler result as a single SSE completion event."""
    yield sse_done(payload)
