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
            "SELECT session_id, appliance_model FROM sessions WHERE session_id = :sid"
        ), {"sid": session_id}).mappings().first()
    return dict(row) if row else None


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
