import json
import uuid
from decimal import Decimal

from sqlalchemy import text
from app.db.engine import get_engine

_MAX_HISTORY = 20


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def create_session() -> str:
    session_id = str(uuid.uuid4())
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id) VALUES (:sid)
            ON CONFLICT (session_id) DO NOTHING
        """), {"sid": session_id})
    return session_id


def _normalize_part(part: dict) -> dict:
    price = part.get("price")
    return {
        "ps_number": part["ps_number"].upper(),
        "name": part.get("name") or "",
        "product_url": part.get("product_url"),
        "price": _json_safe(price) if price is not None else None,
        "image_url": part.get("image_url"),
    }


def _parse_parts_state(raw) -> tuple[list[dict], list[dict]]:
    if not raw:
        return [], []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, list):
        return raw, raw
    if isinstance(raw, dict):
        return raw.get("latest", []), raw.get("history", [])
    return [], []


def get_session(session_id: str) -> dict | None:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT session_id, appliance_model, pending_intent, pending_part_query, last_parts_json "
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


def remember_parts(session_id: str, parts: list[dict]) -> None:
    """Store latest batch plus rolling history for contextual cart actions."""
    shown = [_normalize_part(p) for p in parts if p.get("ps_number")][:10]
    if not shown:
        return

    session = get_session(session_id)
    _, history = _parse_parts_state(session.get("last_parts_json") if session else None)

    merged: dict[str, dict] = {}
    order: list[str] = []
    for p in history + shown:
        ps = p["ps_number"]
        if ps not in merged:
            order.append(ps)
        merged[ps] = {**merged.get(ps, {}), **_normalize_part(p)}

    history_list = [merged[ps] for ps in order][-_MAX_HISTORY:]
    payload = {"latest": shown, "history": history_list}

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO sessions (session_id, last_parts_json)
            VALUES (:sid, CAST(:parts AS jsonb))
            ON CONFLICT (session_id) DO UPDATE SET
                last_parts_json = EXCLUDED.last_parts_json,
                updated_at = now()
        """), {"sid": session_id, "parts": json.dumps(payload)})


def get_last_parts(session: dict | None) -> list[dict]:
    latest, _ = _parse_parts_state(session.get("last_parts_json") if session else None)
    return latest


def get_recent_parts(session: dict | None) -> list[dict]:
    _, history = _parse_parts_state(session.get("last_parts_json") if session else None)
    return history


def get_part_hint(session: dict | None, ps_number: str) -> dict | None:
    ps = ps_number.upper()
    for p in get_recent_parts(session):
        if p.get("ps_number") == ps:
            return p
    return None


# Backward-compatible alias
set_last_parts = remember_parts
