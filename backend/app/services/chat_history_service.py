"""Persist and load chat history per session for LLM context and UI restore."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import text

from app.db.engine import get_engine

MAX_HISTORY_MESSAGES = 12  # last ~6 turns; keeps LLM focused on recent context
MAX_UI_MESSAGES = 100


def _metadata_json(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    cleaned = {k: v for k, v in metadata.items() if v is not None}
    return json.dumps(cleaned) if cleaned else None


def append_message(
    session_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not content or not content.strip():
        return
    engine = get_engine()
    meta = _metadata_json(metadata)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id) VALUES (:sid)
            ON CONFLICT (session_id) DO NOTHING
        """), {"sid": session_id})
        conn.execute(text("""
            INSERT INTO session_messages (session_id, role, content, metadata)
            VALUES (:sid, :role, :content, CAST(:metadata AS jsonb))
        """), {
            "sid": session_id,
            "role": role,
            "content": content.strip(),
            "metadata": meta,
        })


def load_messages(session_id: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT role, content, metadata FROM session_messages
            WHERE session_id = :sid
            ORDER BY id DESC
            LIMIT :limit
        """), {"sid": session_id, "limit": limit}).mappings().all()
    return [dict(r) for r in reversed(rows)]


def load_ui_messages(session_id: str, limit: int = MAX_UI_MESSAGES) -> list[dict]:
    """Messages for frontend restore (role, content, plus stored metadata fields)."""
    rows = load_messages(session_id, limit=limit)
    ui: list[dict] = []
    for row in rows:
        msg: dict[str, Any] = {"role": row["role"], "content": row["content"]}
        meta = row.get("metadata")
        if isinstance(meta, str):
            meta = json.loads(meta)
        if isinstance(meta, dict):
            msg.update(meta)
        ui.append(msg)
    return ui


def to_langchain_messages(rows: list[dict]) -> list[BaseMessage]:
    """Convert stored rows to LangChain messages (excludes current turn)."""
    lc: list[BaseMessage] = []
    for row in rows:
        role, content = row["role"], row["content"]
        if role == "user":
            lc.append(HumanMessage(content=content))
        elif role == "assistant":
            lc.append(AIMessage(content=content))
    return lc


def load_langchain_history(session_id: str) -> list[BaseMessage]:
    return to_langchain_messages(load_messages(session_id))


def _assistant_metadata(payload: dict[str, Any]) -> dict[str, Any] | None:
    keys = (
        "parts", "installation_steps", "compatibility",
        "out_of_scope", "source", "cart_update",
    )
    meta = {k: payload[k] for k in keys if payload.get(k) is not None}
    return meta or None


def record_exchange(
    session_id: str,
    user_text: str,
    assistant_text: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    append_message(session_id, "user", user_text)
    append_message(session_id, "assistant", assistant_text, metadata=metadata)


def record_assistant_response(
    session_id: str,
    user_text: str,
    payload: dict[str, Any],
) -> None:
    """Persist user turn + assistant payload including rich metadata for UI restore."""
    text = (payload.get("text") or "").strip()
    if not text:
        return
    record_exchange(session_id, user_text, text, metadata=_assistant_metadata(payload))
