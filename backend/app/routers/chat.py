import json
import re
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.guardrails import is_in_scope
from app.agent.router import classify_intent, Intent
from app.agent.tools.search_parts import search_parts
from app.agent.tools.check_compatibility import check_compatibility
from app.agent.tools.get_installation import get_installation_guide
from app.agent.tools.troubleshoot import troubleshoot_symptom
from app.agent.tools.add_to_cart import add_to_cart
from app.agent.graph import run_agent_streaming
from app.services.session_service import get_session, set_appliance_model, create_session

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    appliance_model: str | None = None
    stream: bool = True


@router.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or create_session()
    session = get_session(session_id)

    appliance_model = req.appliance_model
    if appliance_model:
        set_appliance_model(session_id, appliance_model)
    elif session:
        appliance_model = session.get("appliance_model")

    message = req.message.strip()

    if not is_in_scope(message):
        return {
            "session_id": session_id,
            "text": "I can only help with Refrigerator and Dishwasher parts. "
                    "Please ask me about appliance parts, compatibility, installation, or troubleshooting.",
            "out_of_scope": True,
        }

    intent = classify_intent(message)

    if intent == Intent.INSTALL:
        ps = re.search(r"PS\d+", message, re.IGNORECASE)
        if ps:
            guide = get_installation_guide(ps.group(0))
            return {
                "session_id": session_id,
                "text": f"Here are the installation instructions for {guide.get('part_name', ps.group(0))}:",
                "installation_steps": guide.get("steps", []),
                "parts": [{"ps_number": guide["ps_number"], "name": guide.get("part_name"),
                            "image_url": guide.get("image_url"), "product_url": guide.get("product_url")}]
                         if guide.get("found") else [],
            }

    if intent == Intent.COMPATIBILITY:
        ps = re.search(r"PS\d+", message, re.IGNORECASE)
        model_m = re.search(r"\b(?!PS\d)[A-Z]{2,6}\d{3,}[A-Z0-9]*\b", message, re.IGNORECASE)
        _model = appliance_model or (model_m.group(0) if model_m else "")
        _ps = ps.group(0) if ps else message
        result = check_compatibility(_model, _ps)
        return {
            "session_id": session_id,
            "text": result["reason"],
            "compatibility": result,
        }

    if intent == Intent.ADD_TO_CART:
        ps = re.search(r"PS\d+", message, re.IGNORECASE)
        if ps:
            result = add_to_cart(session_id, ps.group(0))
            return {"session_id": session_id, "text": f"Added {ps.group(0)} to your cart.",
                    "cart_update": result}

    if intent == Intent.SEARCH:
        results = search_parts(message)
        return {
            "session_id": session_id,
            "text": f"Found {len(results)} part(s):",
            "parts": results,
        }

    # TROUBLESHOOT / COMPLEX → LangGraph agent
    async def _stream() -> AsyncIterator[bytes]:
        async for chunk in run_agent_streaming(session_id, message, appliance_model, []):
            yield f"data: {json.dumps({'token': chunk})}\n\n".encode()
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n".encode()

    if req.stream:
        return StreamingResponse(_stream(), media_type="text/event-stream")
    else:
        text_parts = []
        async for chunk in run_agent_streaming(session_id, message, appliance_model, []):
            text_parts.append(chunk)
        return {"session_id": session_id, "text": "".join(text_parts)}
