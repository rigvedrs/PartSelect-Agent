import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.part_context import resolve_ps_for_cart, match_parts_by_query
from app.agent.guardrails import is_in_scope, reconcile_cart_intent, assert_tool_allowed
from app.agent.router import classify_intent, extract_model_number, latest_utterance, Intent
from app.agent.tools.search_parts import search_parts
from app.agent.tools.check_compatibility import check_compatibility
from app.agent.tools.list_compatible_parts import list_compatible_parts
from app.agent.tools.get_installation import get_installation_guide
from app.agent.tools.add_to_cart import add_to_cart
from app.agent.tools.remove_from_cart import remove_from_cart
from app.agent.graph import run_agent_streaming
from app.agent.troubleshoot_handler import generate_troubleshoot_answer
from app.services.chat_history_service import load_langchain_history, record_exchange
from app.services.session_service import (
    get_session, set_appliance_model, create_session, set_pending, clear_pending,
    remember_parts, get_last_parts, get_recent_parts, get_part_hint,
)
from app.observability import get_logger, new_request_id

log = get_logger("routers.chat")

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    appliance_model: str | None = None
    stream: bool = True


def _resolve_model(message: str, appliance_model: str | None, session: dict | None) -> str:
    """Model from current message, then explicit request field, then session."""
    m = extract_model_number(message)
    if m:
        return m
    if appliance_model and appliance_model.strip():
        return appliance_model.strip()
    if session and session.get("appliance_model"):
        return session["appliance_model"]
    return ""



def _parts_lookup_limit(intent: Intent, part_query: str | None) -> int:
    if intent == Intent.PARTS_FOR_MODEL:
        return 20
    q = (part_query or "").lower()
    if any(kw in q for kw in ("list all", "all parts")):
        return 20
    return 10


def _track_parts(session_id: str, parts: list | None) -> None:
    if parts:
        remember_parts(session_id, parts)


def _respond(session_id: str, message: str, payload: dict) -> dict:
    _track_parts(session_id, payload.get("parts"))
    if "text" in payload:
        record_exchange(session_id, message, payload["text"])
    return payload


@router.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or create_session()
    session = get_session(session_id)

    if req.appliance_model is not None:
        set_appliance_model(session_id, req.appliance_model.strip() or None)
        session = get_session(session_id)

    message = req.message.strip()
    active = latest_utterance(message)
    appliance_model = _resolve_model(message, req.appliance_model, session)

    _model_in_msg = extract_model_number(message)
    if _model_in_msg and (not session or session.get("appliance_model") != _model_in_msg):
        set_appliance_model(session_id, _model_in_msg)
        session = get_session(session_id)
        appliance_model = appliance_model or _model_in_msg

    rid = new_request_id()
    log.info("req=%s msg=%r model=%r", rid, message[:60], appliance_model or "")

    if not is_in_scope(active):
        oos_text = (
            "I can only help with Refrigerator and Dishwasher parts. "
            "Please ask me about appliance parts, compatibility, installation, or troubleshooting."
        )
        record_exchange(session_id, message, oos_text)
        return {"session_id": session_id, "text": oos_text, "out_of_scope": True}

    classification = await classify_intent(
        message,
        session_model=session.get("appliance_model") if session else None,
        last_parts=get_last_parts(session),
    )
    intent = reconcile_cart_intent(classification.intent, active)
    catalog_filter = classification.catalog_filter_query(appliance_model)
    part_query = catalog_filter or active
    last_parts = get_last_parts(session)
    recent_parts = get_recent_parts(session)
    ps = resolve_ps_for_cart(
        active, classification.ps_number, part_query, last_parts, recent_parts,
    )

    log.info("req=%s intent=%s part_query=%r ps=%r", rid, intent.value, part_query, ps)

    if intent == Intent.GREETING:
        greet = (
            "Hi! I can help with refrigerator and dishwasher parts — finding parts, "
            "checking compatibility, installation steps, troubleshooting, and cart actions. "
            "What do you need help with?"
        )
        record_exchange(session_id, message, greet)
        return {"session_id": session_id, "text": greet}

    if session and session.get("pending_intent") and appliance_model:
        pending = session["pending_intent"]
        pending_query = session.get("pending_part_query") or part_query
        clear_pending(session_id)
        if pending in ("search", "parts_for_model"):
            result = list_compatible_parts(appliance_model, part_query=pending_query or None)
            return _respond(session_id, message, {
                "session_id": session_id,
                "text": result["reason"],
                "parts": result["parts"],
            })

    if intent == Intent.INSTALL:
        if ps:
            guide = get_installation_guide(ps)
            text = f"Here are the installation instructions for {guide.get('part_name', ps)}:"
            return _respond(session_id, message, {
                "session_id": session_id,
                "text": text,
                "installation_steps": guide.get("steps", []),
                "parts": [{"ps_number": guide["ps_number"], "name": guide.get("part_name"),
                            "image_url": guide.get("image_url"), "product_url": guide.get("product_url")}]
                         if guide.get("found") else [],
            })

    if intent == Intent.COMPATIBILITY:
        model = appliance_model
        if not ps and model and catalog_filter:
            result = list_compatible_parts(
                model,
                part_query=catalog_filter,
                limit=_parts_lookup_limit(Intent.SEARCH, part_query),
            )
            return _respond(session_id, message, {
                "session_id": session_id,
                "text": result["reason"],
                "parts": result["parts"],
                "source": result.get("source"),
            })
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
        return {"session_id": session_id, "text": result["reason"], "compatibility": result}

    if intent == Intent.PARTS_FOR_MODEL:
        model = appliance_model
        if not model:
            text = (
                "To list parts that fit your appliance, enter your model number "
                "in the field below (e.g. WRS325SDHZ)."
            )
            record_exchange(session_id, message, text)
            return {"session_id": session_id, "text": text}
        result = list_compatible_parts(
            model,
            part_query=catalog_filter,
            limit=_parts_lookup_limit(intent, catalog_filter or part_query),
        )
        return _respond(session_id, message, {
            "session_id": session_id,
            "text": result["reason"],
            "parts": result["parts"],
            "source": result.get("source"),
        })

    if intent == Intent.REMOVE_FROM_CART:
        assert_tool_allowed(intent, "remove_from_cart")
        if ps:
            result = remove_from_cart(session_id, ps)
            text = (
                f"Removed {ps} from your cart."
                if result.get("success")
                else result.get("error", "Could not remove item.")
            )
            return _respond(session_id, message, {
                "session_id": session_id, "text": text, "cart_update": result,
            })
        if len(last_parts) > 1:
            options = ", ".join(p["ps_number"] for p in last_parts[:5])
            text = f"Which part should I remove? Recently shown: {options}"
        else:
            text = "Which part should I remove? Include the PS number (e.g. PS11752778)."
        record_exchange(session_id, message, text)
        return {"session_id": session_id, "text": text}

    if intent == Intent.ADD_TO_CART:
        assert_tool_allowed(intent, "add_to_cart")
        if ps:
            result = add_to_cart(session_id, ps, part_hint=get_part_hint(session, ps))
            if result.get("success"):
                text = f"Added {ps} to your cart."
            else:
                text = result.get("error", f"Could not add {ps} to cart.")
            return _respond(session_id, message, {
                "session_id": session_id, "text": text, "cart_update": result,
            })
        type_matches = match_parts_by_query(recent_parts, part_query)
        if len(type_matches) > 1:
            options = ", ".join(
                f"{p['ps_number']} ({p.get('name') or 'part'})" for p in type_matches[:5]
            )
            text = f"Which one should I add? Matching parts: {options}"
        elif len(recent_parts) > 1:
            options = ", ".join(
                f"{p['ps_number']} ({p.get('name') or 'part'})" for p in recent_parts[:5]
            )
            text = f"Which part should I add? Recently shown: {options}"
        else:
            text = "Which part should I add? Include the PS number or search for a part first."
        record_exchange(session_id, message, text)
        return {"session_id": session_id, "text": text}

    if intent == Intent.TROUBLESHOOT:
        result = await generate_troubleshoot_answer(active)
        return _respond(session_id, message, {
            "session_id": session_id,
            "text": result["text"],
            "parts": result.get("parts"),
        })

    if intent == Intent.SEARCH:
        if ps:
            results = search_parts(ps)
            text = f"Found {len(results)} part(s):"
            return _respond(session_id, message, {
                "session_id": session_id, "text": text, "parts": results,
            })
        if not appliance_model:
            set_pending(session_id, "search", part_query)
            ask = (
                "Sure — what's your appliance model number? I'll find parts verified to fit it. "
                "You can type it in the model field below or just reply with it here."
            )
            record_exchange(session_id, message, ask)
            return {"session_id": session_id, "text": ask}
        result = list_compatible_parts(
            appliance_model,
            part_query=part_query,
            limit=_parts_lookup_limit(intent, part_query),
        )
        return _respond(session_id, message, {
            "session_id": session_id,
            "text": result["reason"],
            "parts": result["parts"],
            "source": result.get("source"),
        })

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

    text_parts = []
    async for chunk in run_agent_streaming(
        session_id, message, appliance_model or None, history
    ):
        text_parts.append(chunk)
    full_text = "".join(text_parts).strip()
    if not full_text:
        full_text = "I couldn't complete that request. Please try again or rephrase your question."
    record_exchange(session_id, message, full_text)
    return {"session_id": session_id, "text": full_text}
