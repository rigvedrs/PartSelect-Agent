import os
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="requires TEST_DATABASE_URL env var and running Postgres",
)


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PASSWORD", "partselect")
    from app.main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_create_session(client):
    r = client.post("/api/session")
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_out_of_scope_rejected(client):
    sid = client.post("/api/session").json()["session_id"]
    r = client.post("/api/chat", json={
        "session_id": sid,
        "message": "what is a good pasta recipe?",
        "stream": False,
    })
    assert r.status_code == 200
    assert r.json().get("out_of_scope") is True


def test_install_query(client):
    """Case-study example query 1: install PS11752778"""
    sid = client.post("/api/session").json()["session_id"]
    r = client.post("/api/chat", json={
        "session_id": sid,
        "message": "How can I install part number PS11752778?",
        "stream": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "installation_steps" in data
    assert len(data["installation_steps"]) > 0


def test_compatibility_query(client):
    """PS11752778 + real ingested model (not demo seed)."""
    sid = client.post("/api/session").json()["session_id"]
    r = client.post("/api/chat", json={
        "session_id": sid,
        "message": "Is PS11752778 compatible with model 10640262010?",
        "stream": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "compatibility" in data
    assert data["compatibility"]["compatible"] is True


def test_remove_from_cart_via_chat(client):
    sid = client.post("/api/session").json()["session_id"]
    client.post("/api/chat", json={
        "session_id": sid, "message": "add PS11752778 to cart", "stream": False
    })
    r = client.post("/api/chat", json={
        "session_id": sid, "message": "remove PS11752778 from cart", "stream": False
    })
    assert r.status_code == 200
    assert "Removed" in r.json().get("text", "")
    assert client.get(f"/api/cart/{sid}").json()["count"] == 0


def test_greeting_does_not_assume_model(client):
    sid = client.post("/api/session").json()["session_id"]
    r = client.post("/api/chat", json={
        "session_id": sid, "message": "Hi", "stream": False
    })
    text = (r.json().get("text") or "").lower()
    assert "wdt780saem1" not in text


def test_appliance_model_persisted_in_session(client):
    """Model set in one request is returned in session and used in next."""
    sid = client.post("/api/session").json()["session_id"]
    # Set model via chat request
    client.post("/api/chat", json={
        "session_id": sid,
        "message": "check compatibility of PS11752778",
        "appliance_model": "WDT780SAEM1",
        "stream": False,
    })
    # Retrieve session and verify model stored
    from app.services.session_service import get_session
    os.environ["DB_HOST"] = "localhost"
    os.environ["POSTGRES_PASSWORD"] = "partselect"
    session = get_session(sid)
    assert session is not None
    assert session["appliance_model"] == "WDT780SAEM1"


def test_cart_flow(client):
    sid = client.post("/api/session").json()["session_id"]
    r = client.post("/api/chat", json={
        "session_id": sid,
        "message": "add PS11752778 to cart",
        "stream": False,
    })
    assert r.status_code == 200
    r2 = client.get(f"/api/cart/{sid}")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1


def test_cart_delete(client):
    sid = client.post("/api/session").json()["session_id"]
    client.post("/api/chat", json={
        "session_id": sid, "message": "add PS11752778 to cart", "stream": False
    })
    r = client.delete(f"/api/cart/{sid}/item/PS11752778")
    assert r.status_code == 200
    assert r.json()["count"] == 0
