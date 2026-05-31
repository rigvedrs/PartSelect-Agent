from fastapi import APIRouter, HTTPException
from app.services.session_service import create_session, get_session
from app.services.chat_history_service import load_ui_messages

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/session")
def new_session():
    return {"session_id": create_session()}


@router.get("/session/{session_id}/messages")
def session_messages(session_id: str):
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "messages": load_ui_messages(session_id),
    }
