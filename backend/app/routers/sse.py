"""Server-Sent Events helpers for chat streaming."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator


def sse_line(data: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


def sse_token(token: str) -> bytes:
    return sse_line({"token": token})


def sse_done(payload: dict[str, Any]) -> bytes:
    return sse_line({"done": True, **payload})


async def stream_static_response(payload: dict[str, Any]) -> AsyncIterator[bytes]:
    """Emit a deterministic handler result as a single SSE completion event."""
    yield sse_done(payload)
