from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.part_context import resolve_ps_for_cart, match_parts_by_query
from app.agent.guardrails import is_in_scope, reconcile_cart_intent, assert_tool_allowed
from app.agent.catalog import CatalogScope
from app.agent.router import classify_intent, extract_model_number, latest_utterance, Intent
from app.agent.tools.search_parts import search_parts
from app.agent.tools.check_compatibility import check_compatibility
from app.agent.tools.list_compatible_parts import list_compatible_parts
from app.agent.tools.get_installation import get_installation_guide, format_installation_response
from app.agent.tools.add_to_cart import add_to_cart
from app.agent.tools.remove_from_cart import remove_from_cart
from app.agent.graph import run_agent_streaming
from app.agent.troubleshoot_handler import stream_troubleshoot_answer, prepare_troubleshoot
from app.services.chat_history_service import (
    load_langchain_history,
    record_assistant_response,
    record_exchange,
)
from app.services.session_service import (
    get_session, set_appliance_model, create_session, set_pending, clear_pending,
    remember_parts, get_last_parts, get_recent_parts, get_part_hint,
)
from app.routers.sse import sse_done, sse_stage, sse_token
from app.observability import (
    get_logger,
    log_event,
    new_request_id,
    safe_preview,
    span,
    trace_request,
)

log = get_logger("routers.chat")


@asynccontextmanager
async def _async_span(name: str):
    with span(name):
        yield


router = APIRouter(prefix="/api", tags=["chat"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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


def _catalog_scope(classification) -> CatalogScope:
    return CatalogScope.FULL if classification.browse_all_parts else CatalogScope.BY_PART_TYPE


def _parts_lookup_limit(intent: Intent, scope: CatalogScope) -> int:
    from app.config import load_settings
    limits = load_settings().catalog
    if scope == CatalogScope.FULL:
        return limits.full_catalog_limit
    if intent == Intent.PARTS_FOR_MODEL:
        return limits.filtered_catalog_limit
    return 10


def _track_parts(session_id: str, parts: list | None) -> None:
    if parts:
        remember_parts(session_id, parts)


def _payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_text": bool(payload.get("text")),
        "parts_count": len(payload.get("parts") or []),
        "installation_steps_count": len(payload.get("installation_steps") or []),
        "has_compatibility": bool(payload.get("compatibility")),
        "has_cart_update": bool(payload.get("cart_update")),
        "out_of_scope": bool(payload.get("out_of_scope")),
        "source": payload.get("source"),
    }


def _finalize(session_id: str, user_message: str, payload: dict[str, Any]) -> dict[str, Any]:
    full = {"session_id": session_id, **payload}
    _track_parts(session_id, full.get("parts"))
    record_assistant_response(session_id, user_message, full)
    log_event(log, "chat.response.done", **_payload_metadata(full))
    return full


def _sse_response(gen: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers=_SSE_HEADERS)


async def _respond_json_or_sse(
    req: ChatRequest,
    session_id: str,
    user_message: str,
    payload: dict[str, Any],
    stage: str | None = None,
) -> dict[str, Any] | StreamingResponse:
    if req.stream:
        full = {"session_id": session_id, **payload}

        async def _gen() -> AsyncIterator[bytes]:
            if stage:
                log_event(log, "sse.stage", stage=stage)
                yield sse_stage(stage)
            _track_parts(session_id, full.get("parts"))
            record_assistant_response(session_id, user_message, full)
            log_event(log, "chat.response.done", **_payload_metadata(full))
            yield sse_done(full)

        return _sse_response(_gen())
    return _finalize(session_id, user_message, payload)


async def _stream_llm_tokens(
    req: ChatRequest,
    session_id: str,
    user_message: str,
    token_source: AsyncIterator[str],
    extra: dict[str, Any] | None = None,
    stage: str | None = None,
) -> StreamingResponse:
    async def _gen() -> AsyncIterator[bytes]:
        if stage:
            log_event(log, "sse.stage", stage=stage)
            yield sse_stage(stage)
        text_parts: list[str] = []
        log_event(log, "llm.stream.start", has_extra=bool(extra))
        async for token in token_source:
            text_parts.append(token)
            yield sse_token(token)
        full_text = "".join(text_parts).strip()
        if not full_text:
            full_text = "I couldn't complete that request. Please try again or rephrase your question."
        payload: dict[str, Any] = {"session_id": session_id, "text": full_text, **(extra or {})}
        _track_parts(session_id, payload.get("parts"))
        record_assistant_response(session_id, user_message, payload)
        log_event(
            log,
            "llm.stream.done",
            token_count=len(text_parts),
            char_count=len(full_text),
        )
        log_event(log, "chat.response.done", **_payload_metadata(payload))
        yield sse_done(payload)

    return _sse_response(_gen())


async def _stream_troubleshoot(
    req: ChatRequest,
    session_id: str,
    user_message: str,
    active: str,
) -> StreamingResponse | dict[str, Any]:
    prep = prepare_troubleshoot(user_message)
    extra = {"parts": prep["parts"]}

    if not req.stream:
        from app.agent.troubleshoot_handler import generate_troubleshoot_answer
        result = await generate_troubleshoot_answer(active)
        return _finalize(session_id, user_message, {
            "text": result["text"],
            "parts": result.get("parts"),
        })

    async def _tokens() -> AsyncIterator[str]:
        async for token in stream_troubleshoot_answer(active, prep=prep):
            yield token

    return await _stream_llm_tokens(
        req,
        session_id,
        user_message,
        _tokens(),
        extra=extra,
        stage="Reviewing repair guidance...",
    )


@router.post("/chat")
async def chat(req: ChatRequest):
    rid = new_request_id()
    if req.stream:
        async def _gen() -> AsyncIterator[bytes]:
            with trace_request(rid, route="chat") as trace:
                log_event(log, "sse.stage", stage="Understanding your request...")
                yield sse_stage("Understanding your request...")
                result = await _chat_inner(req, rid, trace)
                if isinstance(result, StreamingResponse):
                    async for chunk in result.body_iterator:
                        yield chunk
                    return
                log_event(log, "chat.response.done", **_payload_metadata(result))
                yield sse_done(result)

        return _sse_response(_gen())

    with trace_request(rid, route="chat") as trace:
        return await _chat_inner(req, rid, trace)


async def _chat_inner(req: ChatRequest, rid: str, trace) -> dict[str, Any] | StreamingResponse:
    session_id = req.session_id or create_session()
    session = get_session(session_id)

    if req.appliance_model is not None:
        set_appliance_model(session_id, req.appliance_model.strip() or None)
        session = get_session(session_id)

    message = req.message.strip()
    active = latest_utterance(message)
    appliance_model = _resolve_model(message, req.appliance_model, session)
    log_event(
        log,
        "chat.request.start",
        has_session=bool(req.session_id),
        stream=req.stream,
        message=safe_preview(message),
        active=safe_preview(active),
        provided_model=safe_preview(req.appliance_model),
    )

    _model_in_msg = extract_model_number(message)
    if _model_in_msg and (not session or session.get("appliance_model") != _model_in_msg):
        set_appliance_model(session_id, _model_in_msg)
        session = get_session(session_id)
        appliance_model = appliance_model or _model_in_msg

    log_event(
        log,
        "chat.model.resolved",
        model=appliance_model or "",
        session_model=bool(session and session.get("appliance_model")),
    )
    log.info("req=%s msg=%r model=%r", rid, message[:60], appliance_model or "")

    if not is_in_scope(active):
        oos_text = (
            "I can only help with Refrigerator and Dishwasher parts. "
            "Please ask me about appliance parts, compatibility, installation, or troubleshooting."
        )
        payload = {"text": oos_text, "out_of_scope": True}
        log_event(log, "chat.scope.rejected", active=safe_preview(active))
        if req.stream:
            full = {"session_id": session_id, **payload}

            async def _oos_gen() -> AsyncIterator[bytes]:
                record_exchange(session_id, message, oos_text, metadata={"out_of_scope": True})
                log_event(log, "chat.response.done", **_payload_metadata(full))
                yield sse_done(full)

            return _sse_response(_oos_gen())
        record_exchange(session_id, message, oos_text, metadata={"out_of_scope": True})
        return {"session_id": session_id, **payload}

    async with _async_span("intent"):
        classification = await classify_intent(
            message,
            session_model=session.get("appliance_model") if session else None,
            last_parts=get_last_parts(session),
        )
    intent = reconcile_cart_intent(classification.intent, active)
    trace.route = intent.value
    catalog_filter = classification.catalog_filter_query(appliance_model)
    catalog_scope = _catalog_scope(classification)
    part_query = catalog_filter or active
    last_parts = get_last_parts(session)
    recent_parts = get_recent_parts(session)
    ps = resolve_ps_for_cart(
        active, classification.ps_number, part_query, last_parts, recent_parts,
    )

    log.info("req=%s intent=%s part_query=%r ps=%r", rid, intent.value, part_query, ps)
    log_event(
        log,
        "intent.classified",
        intent=intent.value,
        browse_all=classification.browse_all_parts,
        part_query=catalog_filter,
        ps_number=ps,
        catalog_scope=catalog_scope.value,
        model=appliance_model or "",
    )
    log_event(log, "chat.branch.selected", branch=intent.value)

    if intent == Intent.GREETING:
        greet = (
            "Hi! I can help with refrigerator and dishwasher parts — finding parts, "
            "checking compatibility, installation steps, troubleshooting, and cart actions. "
            "What do you need help with?"
        )
        return await _respond_json_or_sse(
            req, session_id, message, {"text": greet}, "Putting the answer together..."
        )

    if session and session.get("pending_intent") and appliance_model:
        pending = session["pending_intent"]
        pending_query = session.get("pending_part_query") or catalog_filter
        clear_pending(session_id)
        if pending in ("search", "parts_for_model"):
            result = list_compatible_parts(
                appliance_model,
                scope=CatalogScope.BY_PART_TYPE,
                part_type_filter=pending_query or None,
            )
            return await _respond_json_or_sse(req, session_id, message, {
                "text": result["reason"],
                "parts": result["parts"],
            }, "Checking matching parts...")

    if intent == Intent.INSTALL:
        if ps:
            guide = get_installation_guide(ps)
            text = format_installation_response(guide, ps)
            return await _respond_json_or_sse(req, session_id, message, {
                "text": text,
                "installation_steps": guide.get("steps", []),
                "parts": [{"ps_number": guide["ps_number"], "name": guide.get("part_name"),
                            "image_url": guide.get("image_url"), "product_url": guide.get("product_url")}]
                         if guide.get("found") else [],
            }, "Finding installation steps...")

    if intent == Intent.COMPATIBILITY:
        model = appliance_model
        if not ps and model and catalog_filter:
            result = list_compatible_parts(
                model,
                scope=catalog_scope,
                part_type_filter=catalog_filter,
                limit=_parts_lookup_limit(Intent.SEARCH, catalog_scope),
            )
            return await _respond_json_or_sse(req, session_id, message, {
                "text": result["reason"],
                "parts": result["parts"],
                "source": result.get("source"),
            }, "Checking matching parts...")
        if not model:
            text = "Please enter your appliance model number in the field below so I can check compatibility."
            return await _respond_json_or_sse(
                req, session_id, message, {"text": text}, "Putting the answer together..."
            )
        if not ps:
            text = "Please include the PartSelect part number (e.g. PS11752778) to check compatibility."
            return await _respond_json_or_sse(
                req, session_id, message, {"text": text}, "Putting the answer together..."
            )
        result = check_compatibility(model, ps)
        return await _respond_json_or_sse(req, session_id, message, {
            "text": result["reason"],
            "compatibility": result,
        }, "Checking compatibility...")

    if intent == Intent.PARTS_FOR_MODEL:
        model = appliance_model
        if not model:
            text = (
                "To list parts that fit your appliance, enter your model number "
                "in the field below (e.g. WRS325SDHZ)."
            )
            return await _respond_json_or_sse(
                req, session_id, message, {"text": text}, "Putting the answer together..."
            )
        result = list_compatible_parts(
            model,
            scope=catalog_scope,
            part_type_filter=catalog_filter,
            limit=_parts_lookup_limit(intent, catalog_scope),
        )
        return await _respond_json_or_sse(req, session_id, message, {
            "text": result["reason"],
            "parts": result["parts"],
            "source": result.get("source"),
        }, "Checking matching parts...")

    if intent == Intent.REMOVE_FROM_CART:
        assert_tool_allowed(intent, "remove_from_cart")
        if ps:
            with span("cart"):
                result = remove_from_cart(session_id, ps)
            text = (
                f"Removed {ps} from your cart."
                if result.get("success")
                else result.get("error", "Could not remove item.")
            )
            return await _respond_json_or_sse(req, session_id, message, {
                "text": text,
                "cart_update": result,
            }, "Updating your cart...")
        if len(last_parts) > 1:
            options = ", ".join(p["ps_number"] for p in last_parts[:5])
            text = f"Which part should I remove? Recently shown: {options}"
        else:
            text = "Which part should I remove? Include the PS number (e.g. PS11752778)."
        return await _respond_json_or_sse(
            req, session_id, message, {"text": text}, "Putting the answer together..."
        )

    if intent == Intent.ADD_TO_CART:
        assert_tool_allowed(intent, "add_to_cart")
        if ps:
            with span("cart"):
                result = add_to_cart(session_id, ps, part_hint=get_part_hint(session, ps))
            if result.get("success"):
                text = f"Added {ps} to your cart."
            else:
                text = result.get("error", f"Could not add {ps} to cart.")
            return await _respond_json_or_sse(req, session_id, message, {
                "text": text,
                "cart_update": result,
            }, "Updating your cart...")
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
        return await _respond_json_or_sse(
            req, session_id, message, {"text": text}, "Putting the answer together..."
        )

    if intent == Intent.TROUBLESHOOT:
        return await _stream_troubleshoot(req, session_id, message, active)

    if intent == Intent.SEARCH:
        if ps:
            results = search_parts(ps)
            text = f"Found {len(results)} part(s):"
            return await _respond_json_or_sse(req, session_id, message, {
                "text": text,
                "parts": results,
            }, "Checking matching parts...")
        if not appliance_model:
            set_pending(session_id, "search", part_query)
            ask = (
                "Sure — what's your appliance model number? I'll find parts verified to fit it. "
                "You can type it in the model field below or just reply with it here."
            )
            return await _respond_json_or_sse(
                req, session_id, message, {"text": ask}, "Putting the answer together..."
            )
        result = list_compatible_parts(
            appliance_model,
            scope=catalog_scope,
            part_type_filter=catalog_filter,
            limit=_parts_lookup_limit(intent, catalog_scope),
        )
        return await _respond_json_or_sse(req, session_id, message, {
            "text": result["reason"],
            "parts": result["parts"],
            "source": result.get("source"),
        }, "Checking matching parts...")

    history = load_langchain_history(session_id)

    if req.stream:
        return await _stream_llm_tokens(
            req,
            session_id,
            message,
            run_agent_streaming(session_id, message, appliance_model or None, history),
            stage="Putting the answer together...",
        )

    text_parts = []
    async for chunk in run_agent_streaming(
        session_id, message, appliance_model or None, history
    ):
        text_parts.append(chunk)
    full_text = "".join(text_parts).strip()
    if not full_text:
        full_text = "I couldn't complete that request. Please try again or rephrase your question."
    return _finalize(session_id, message, {"text": full_text})
