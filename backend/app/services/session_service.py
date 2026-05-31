import uuid
from sqlalchemy import text
from app.db.engine import get_engine


def create_session() -> str:
    session_id = str(uuid.uuid4())
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id) VALUES (:sid)
            ON CONFLICT (session_id) DO NOTHING
        """), {"sid": session_id})
    return session_id


def get_session(session_id: str) -> dict | None:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT session_id, appliance_model, pending_intent, pending_part_query "
            "FROM sessions WHERE session_id = :sid"
        ), {"sid": session_id}).mappings().first()
    return dict(row) if row else None


def set_pending(session_id: str, intent: str, part_query: str | None) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id, pending_intent, pending_part_query)
            VALUES (:sid, :intent, :pq)
            ON CONFLICT (session_id) DO UPDATE SET
                pending_intent = EXCLUDED.pending_intent,
                pending_part_query = EXCLUDED.pending_part_query,
                updated_at = now()
        """), {"sid": session_id, "intent": intent, "pq": part_query})


def clear_pending(session_id: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE sessions SET pending_intent = NULL, pending_part_query = NULL, updated_at = now()
            WHERE session_id = :sid
        """), {"sid": session_id})


def set_appliance_model(session_id: str, model: str | None) -> None:
    model = (model or "").strip() or None
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id, appliance_model)
            VALUES (:sid, :model)
            ON CONFLICT (session_id) DO UPDATE SET
                appliance_model = EXCLUDED.appliance_model,
                updated_at = now()
        """), {"sid": session_id, "model": model})
