"""Structured, safe logging for the chat request path."""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from loguru import logger as _loguru_logger

_SECRET_KEY_PARTS = ("api_key", "token", "secret", "password", "authorization")
_current_trace: contextvars.ContextVar["RequestTrace | None"] = contextvars.ContextVar(
    "request_trace", default=None
)
_langfuse = None


@dataclass(frozen=True)
class LogSettings:
    level: str = "INFO"
    format: str = "pretty"
    color: bool = True


class _PropagateHandler(logging.Handler):
    """Forward Loguru messages into stdlib logging so pytest caplog can inspect them."""

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


def get_log_settings() -> LogSettings:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = os.getenv("LOG_FORMAT", "pretty").strip().lower()
    if fmt not in {"pretty", "json"}:
        fmt = "pretty"
    color_raw = os.getenv("LOG_COLOR")
    color = fmt == "pretty" if color_raw is None else color_raw.strip().lower() not in {
        "0", "false", "no", "off",
    }
    return LogSettings(level=level, format=fmt, color=color)


def _json_sink(message) -> None:
    record = message.record
    extra = dict(record["extra"])
    payload = {
        "time": record["time"].isoformat(),
        "level": record["level"].name,
        "component": extra.pop("component", record["name"]),
        "event": extra.pop("event", record["message"].split(" ", 1)[0]),
        "message": record["message"],
        **extra,
    }
    sys.stderr.write(json.dumps(payload, default=str) + "\n")


def _configure_loguru() -> None:
    settings = get_log_settings()
    _loguru_logger.remove()
    if settings.format == "json":
        _loguru_logger.add(_json_sink, level=settings.level, colorize=False, enqueue=False)
    else:
        _loguru_logger.add(
            sys.stderr,
            level=settings.level,
            colorize=settings.color,
            format=(
                "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
                "<cyan>{extra[component]}</cyan> | <level>{message}</level>"
            ),
            enqueue=False,
        )
    _loguru_logger.add(_PropagateHandler(), level=settings.level, format="{message}")


try:
    _configure_loguru()
except Exception:  # pragma: no cover - defensive fallback for logging setup only
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:8]


def safe_preview(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    if limit <= 3:
        return "." * limit
    return text[: limit - 3] + "..."


def _is_secret_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if _is_secret_key(str(key)):
            safe[key] = "[redacted]"
        elif isinstance(value, list):
            safe[key] = f"list(len={len(value)})"
        elif isinstance(value, tuple):
            safe[key] = f"tuple(len={len(value)})"
        elif isinstance(value, dict):
            safe[key] = f"dict(keys={len(value)})"
        elif isinstance(value, str):
            safe[key] = safe_preview(value)
        else:
            safe[key] = value
    return safe


def _format_fields(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    return " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    try:
        safe = sanitize_fields(fields)
        trace = _current_trace.get()
        if trace is not None and "req_id" not in safe:
            safe = {"req_id": trace.req_id, **safe}
        field_text = _format_fields(safe)
        message = f"{event} {field_text}".strip()
        component = logger.name if isinstance(logger, logging.Logger) else "app"
        _loguru_logger.bind(component=component, event=event, **safe).info(message)
    except Exception:
        try:
            logger.info("%s", event)
        except Exception:
            pass


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
    log = get_logger("app.observability")
    with trace.activate():
        try:
            yield trace
        finally:
            fields = {"route": trace.route, **{f"{name}_ms": round(ms, 1) for name, ms in trace.timings.items()}}
            log_event(log, "trace.summary", **fields)
            log.info(trace.summary())


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
