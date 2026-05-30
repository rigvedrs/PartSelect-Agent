from fastapi import APIRouter
from app.services.session_service import create_session

router = APIRouter(prefix="/api", tags=["session"])


@router.post("/session")
def new_session():
    return {"session_id": create_session()}
