import json
import re
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.guardrails import is_in_scope
from app.agent.router import classify_intent, routing_query, extract_model_number, Intent
from app.agent.tools.search_parts import search_parts
from app.agent.tools.check_compatibility import check_compatibility
from app.agent.tools.list_compatible_parts import list_compatible_parts
from app.agent.tools.get_installation import get_installation_guide
from app.agent.tools.troubleshoot import troubleshoot_symptom
from app.agent.tools.add_to_cart import add_to_cart
from app.agent.tools.remove_from_cart import remove_from_cart
from app.agent.graph import run_agent_streaming
from app.agent.messages import TROUBLESHOOT_REDIRECT
from app.services.chat_history_service import load_langchain_history, record_exchange
from app.services.session_service import (
    get_session, set_appliance_model, create_session, set_pending, clear_pending,
)
from app.observability import get_logger, new_request_id

log = get_logger("routers.chat")

router = APIRouter(prefix="/api", tags=["chat"])

_PS_RE = re.compile(r"PS\d+", re.IGNORECASE)


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    appliance_model: str | None = None
    stream: bool = True


def _resolve_model(message: str, appliance_model: str | None, session: dict | None) -> str:
    """Model from current message, then explicit request field, then session — never guess."""
    m = extract_model_number(message)
    if m:
        return m
    if appliance_model and appliance_model.strip():
        return appliance_model.strip()
    if session and session.get("appliance_model"):
        return session["appliance_model"]
    return ""


def _extract_ps(message: str) -> str | None:
    m = _PS_RE.search(message)
    return m.group(0).upper() if m else None


@router.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or create_session()
    session = get_session(session_id)

    # Only persist model when client sends a non-empty value
    if req.appliance_model is not None:
        set_appliance_model(session_id, req.appliance_model.strip() or None)
        session = get_session(session_id)

    message = req.message.strip()
    latest = routing_query(message)
    appliance_model = _resolve_model(latest, req.appliance_model, session)
    rid = new_request_id()
    log.info("req=%s intent_msg=%r model=%r", rid, latest[:60], appliance_model or "")

    if not is_in_scope(latest):
        oos_text = (
            "I can only help with Refrigerator and Dishwasher parts. "
            "Please ask me about appliance parts, compatibility, installation, or troubleshooting."
        )
        record_exchange(session_id, message, oos_text)
        return {
            "session_id": session_id,
            "text": oos_text,
            "out_of_scope": True,
        }

    intent = classify_intent(message)

    # Short greetings — deterministic, no LLM (avoids invented model assumptions)
    if re.match(r"^(hi|hello|hey|good\s+(morning|afternoon|evening))\b", latest, re.I):
        greet = (
            "Hi! I can help with refrigerator and dishwasher parts — finding parts, "
            "checking compatibility, installation steps, troubleshooting, and cart actions. "
            "What do you need help with?"
        )
        record_exchange(session_id, message, greet)
        return {"session_id": session_id, "text": greet}

    # Resolve a previously stored request now that we may have a model
    if session and session.get("pending_intent") and appliance_model:
        pending = session["pending_intent"]
        part_query = session.get("pending_part_query") or ""
        clear_pending(session_id)
        if pending in ("search", "parts_for_model"):
            result = list_compatible_parts(appliance_model, part_query=part_query or None)
            record_exchange(session_id, message, result["reason"])
            return {"session_id": session_id, "text": result["reason"], "parts": result["parts"]}

    if intent == Intent.INSTALL:
        ps = _extract_ps(latest)
        if ps:
            guide = get_installation_guide(ps)
            text = f"Here are the installation instructions for {guide.get('part_name', ps)}:"
            record_exchange(session_id, message, text)
            return {
                "session_id": session_id,
                "text": text,
                "installation_steps": guide.get("steps", []),
                "parts": [{"ps_number": guide["ps_number"], "name": guide.get("part_name"),
                            "image_url": guide.get("image_url"), "product_url": guide.get("product_url")}]
                         if guide.get("found") else [],
            }

    if intent == Intent.COMPATIBILITY:
        ps = _extract_ps(latest)
        model = _resolve_model(latest, req.appliance_model, session)
        if not model:
            text = "Please enter your appliance model number in the field below so I can check compatibility."
            record_exchange(session_id, message, text)
            return {"session_id": session_id, "text": text}
        if not ps:
            text = "Please include the PartSelect part number (e.g. PS11752778) to check compatibility."
            record_exchange(session_id, message, text)
            return {"session_id": session_id, "text": text}
        result = check_compatibility(model, ps)
        record_exchange(session_id, message, result["reason"])
        return {
            "session_id": session_id,
            "text": result["reason"],
            "compatibility": result,
        }

    if intent == Intent.PARTS_FOR_MODEL:
        model = _resolve_model(latest, req.appliance_model, session)
        if not model:
            text = (
                "To list parts that fit your appliance, enter your model number "
                "in the field below (e.g. WRS325SDHZ)."
            )
            record_exchange(session_id, message, text)
            return {"session_id": session_id, "text": text}
        result = list_compatible_parts(model, part_query=latest)
        record_exchange(session_id, message, result["reason"])
        return {
            "session_id": session_id,
            "text": result["reason"],
            "parts": result["parts"],
            "source": result.get("source"),
        }

    if intent == Intent.REMOVE_FROM_CART:
        ps = _extract_ps(latest)
        if ps:
            result = remove_from_cart(session_id, ps)
            text = (
                f"Removed {ps} from your cart."
                if result.get("success")
                else result.get("error", "Could not remove item.")
            )
            record_exchange(session_id, message, text)
            return {
                "session_id": session_id,
                "text": text,
                "cart_update": result,
            }
        text = "Which part should I remove? Include the PS number (e.g. PS11752778)."
        record_exchange(session_id, message, text)
        return {"session_id": session_id, "text": text}

    if intent == Intent.ADD_TO_CART:
        ps = _extract_ps(latest)
        if ps:
            result = add_to_cart(session_id, ps)
            text = f"Added {ps} to your cart."
            record_exchange(session_id, message, text)
            return {"session_id": session_id, "text": text, "cart_update": result}

    if intent == Intent.TROUBLESHOOT:
        record_exchange(session_id, message, TROUBLESHOOT_REDIRECT)
        return {"session_id": session_id, "text": TROUBLESHOOT_REDIRECT}

    if intent == Intent.SEARCH:
        ps = _extract_ps(latest)
        if ps:
            results = search_parts(latest)
            text = f"Found {len(results)} part(s):"
            record_exchange(session_id, message, text)
            return {"session_id": session_id, "text": text, "parts": results}
        if not appliance_model:
            set_pending(session_id, "search", latest)
            ask = (
                "Sure — what's your appliance model number? I'll find parts verified to fit it. "
                "You can type it in the model field below or just reply with it here."
            )
            record_exchange(session_id, message, ask)
            return {"session_id": session_id, "text": ask}
        result = list_compatible_parts(appliance_model, part_query=latest)
        record_exchange(session_id, message, result["reason"])
        return {"session_id": session_id, "text": result["reason"], "parts": result["parts"], "source": result.get("source")}

    history = load_langchain_history(session_id)

    async def _stream() -> AsyncIterator[bytes]:
        text_parts = []
        async for chunk in run_agent_streaming(
            session_id, message, appliance_model or None, history
        ):
            text_parts.append(chunk)
            yield f"data: {json.dumps({'token': chunk})}\n\n".encode()
        full_text = "".join(text_parts)
        record_exchange(session_id, message, full_text)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n".encode()

    if req.stream:
        return StreamingResponse(_stream(), media_type="text/event-stream")
    else:
        text_parts = []
        async for chunk in run_agent_streaming(
            session_id, message, appliance_model or None, history
        ):
            text_parts.append(chunk)
        full_text = "".join(text_parts).strip()
        if not full_text:
            full_text = (
                "I couldn't complete that request. Please try again or rephrase your question."
            )
        record_exchange(session_id, message, full_text)
        return {"session_id": session_id, "text": full_text}
