import os
import json
from decimal import Decimal

import pytest

from app.services.session_service import (
    remember_parts,
    get_last_parts,
    get_recent_parts,
    get_part_hint,
    _normalize_part,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires TEST_DATABASE_URL",
)


def test_remember_parts_serializes_decimal_price():
    normalized = _normalize_part({
        "ps_number": "PS11722130",
        "name": "Water Filter",
        "price": Decimal("83.89"),
    })
    json.dumps({"latest": [normalized], "history": [normalized]})


def test_remember_parts_keeps_history():
    sid = "test-session-history"
    from sqlalchemy import text
    from app.db.engine import get_engine

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO sessions (session_id) VALUES (:sid) ON CONFLICT DO NOTHING"
        ), {"sid": sid})

    remember_parts(sid, [
        {"ps_number": "PS11722130", "name": "Water Filter A", "price": Decimal("83.89")},
        {"ps_number": "PS12731165", "name": "Water Filter Bypass"},
    ])
    remember_parts(sid, [
        {"ps_number": "PS11743531", "name": "Pivot Block"},
    ])

    from app.services.session_service import get_session
    session = get_session(sid)

    assert len(get_last_parts(session)) == 1
    assert get_last_parts(session)[0]["ps_number"] == "PS11743531"
    assert len(get_recent_parts(session)) == 3
    assert get_part_hint(session, "PS11722130")["name"] == "Water Filter A"

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sessions WHERE session_id = :sid"), {"sid": sid})
