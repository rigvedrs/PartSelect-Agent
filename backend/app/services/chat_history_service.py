"""Persist and load chat history per session for LLM context."""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import text

from app.db.engine import get_engine

MAX_HISTORY_MESSAGES = 40  # cap prior turns (user + assistant pairs)


def append_message(session_id: str, role: str, content: str) -> None:
    if not content or not content.strip():
        return
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id) VALUES (:sid)
            ON CONFLICT (session_id) DO NOTHING
        """), {"sid": session_id})
        conn.execute(text("""
            INSERT INTO session_messages (session_id, role, content)
            VALUES (:sid, :role, :content)
        """), {"sid": session_id, "role": role, "content": content.strip()})


def load_messages(session_id: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT role, content FROM session_messages
            WHERE session_id = :sid
            ORDER BY id DESC
            LIMIT :limit
        """), {"sid": session_id, "limit": limit}).mappings().all()
    # Return chronological order
    return [dict(r) for r in reversed(rows)]


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


def record_exchange(session_id: str, user_text: str, assistant_text: str) -> None:
    append_message(session_id, "user", user_text)
    append_message(session_id, "assistant", assistant_text)
