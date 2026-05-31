"""Lightweight structured logging for the chat request path."""
import contextvars
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

_logger = logging.getLogger(__name__)
_current_trace: contextvars.ContextVar["RequestTrace | None"] = contextvars.ContextVar(
    "request_trace", default=None
)
_langfuse = None


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class RequestTrace:
    req_id: str
    route: str = ""
    timings: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def activate(self) -> Generator["RequestTrace", None, None]:
        token = _current_trace.set(self)
        try:
            yield self
        finally:
            _current_trace.reset(token)

    def record(self, name: str, elapsed_ms: float) -> None:
        self.timings[name] = elapsed_ms

    def summary(self) -> str:
        parts = [f"req={self.req_id}"]
        if self.route:
            parts.append(f"route={self.route}")
        for name, ms in sorted(self.timings.items()):
            parts.append(f"{name}={ms:.1f}ms")
        return " ".join(parts)


@contextmanager
def span(name: str) -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        trace = _current_trace.get()
        if trace is not None:
            trace.record(name, elapsed_ms)


@contextmanager
def trace_request(req_id: str, route: str = "") -> Generator[RequestTrace, None, None]:
    trace = RequestTrace(req_id=req_id, route=route)
    with trace.activate():
        try:
            yield trace
        finally:
            _logger.info(trace.summary())


def _langfuse_client():
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse()
    except ImportError:
        _langfuse = None
    return _langfuse
