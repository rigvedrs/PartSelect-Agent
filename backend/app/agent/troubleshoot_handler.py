"""Generate troubleshooting answers via RAG + synthesis LLM."""
from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import load_settings
from app.agent.llm_provider import get_llm
from app.agent.messages import TROUBLESHOOT_REDIRECT
from app.agent.tools.troubleshoot import (
    detect_appliance_type,
    retrieve_troubleshoot_context,
    format_context_for_llm,
)
from app.observability import get_logger, log_event, safe_preview, span

log = get_logger("agent.troubleshoot")

_SYSTEM = """You help customers troubleshoot refrigerator and dishwasher problems using PartSelect repair guides and articles.

Rules:
- Use ONLY the retrieved context below. Do not invent part numbers or steps not supported by the context.
- Give practical troubleshooting steps (2-4 short paragraphs).
- If a related part is listed in context, mention it by name and PS number.
- Stay focused on refrigerator/dishwasher scope.
- Do NOT include PartSelect marketing links or generic resource pages — those are appended separately.
- If context is limited, give safe general checks for that symptom and say which parts to inspect."""


def _chunk_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def _prepare_context(message: str) -> tuple[str, dict]:
    log_event(log, "tool.call.start", tool="troubleshoot.prepare", message=safe_preview(message))
    appliance = detect_appliance_type(message)
    ctx = retrieve_troubleshoot_context(message, appliance)
    context_text = format_context_for_llm(ctx)
    log.info(
        "troubleshoot rag appliance=%s causes=%d articles=%d parts=%d",
        appliance, len(ctx["causes"]), len(ctx["articles"]), len(ctx["parts"]),
    )
    log_event(
        log,
        "tool.call.done",
        tool="troubleshoot.prepare",
        appliance=appliance,
        causes_count=len(ctx["causes"]),
        articles_count=len(ctx["articles"]),
        parts_count=len(ctx["parts"]),
    )
    return appliance, ctx


def _fallback_body(appliance: str) -> str:
    return (
        f"For {appliance} issues like this, check power, water supply, filters, and door seals. "
        "Inspect the parts most commonly associated with your symptom."
    )


def prepare_troubleshoot(message: str) -> dict:
    """Run RAG once; reuse for streaming and metadata."""
    appliance, ctx = _prepare_context(message)
    return {
        "appliance": appliance,
        "ctx": ctx,
        "context_text": format_context_for_llm(ctx),
        "parts": ctx["parts"] or None,
    }


async def stream_troubleshoot_answer(
    message: str,
    *,
    prep: dict | None = None,
) -> AsyncIterator[str]:
    """Stream synthesis tokens, then the standard resource footer."""
    if prep is None:
        prep = prepare_troubleshoot(message)
    appliance = prep["appliance"]
    context_text = prep["context_text"]
    llm = get_llm("synthesis")
    model = load_settings().llm.synthesis_model
    body_parts: list[str] = []

    try:
        with span("llm_synthesis"):
            log_event(log, "llm.stream.start", model=model, purpose="troubleshoot")
            async for chunk in llm.astream([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=f"Retrieved context:\n{context_text}\n\nCustomer message: {message}"),
            ]):
                token = _chunk_text(chunk.content)
                if token:
                    body_parts.append(token)
                    yield token
    except Exception:
        log.exception("troubleshoot LLM stream failed")
        log_event(log, "llm.stream.error", model=model, purpose="troubleshoot")

    body = "".join(body_parts).strip()
    if not body:
        body = _fallback_body(appliance)
        yield body

    footer = f"\n\n{TROUBLESHOOT_REDIRECT}"
    log_event(
        log,
        "llm.stream.done",
        model=model,
        purpose="troubleshoot",
        token_count=len(body_parts),
        char_count=len(body),
    )
    yield footer


async def generate_troubleshoot_answer(message: str) -> dict:
    """Non-streaming troubleshoot (tests and stream=false fallback)."""
    prep = prepare_troubleshoot(message)
    llm = get_llm("synthesis")
    model = load_settings().llm.synthesis_model
    try:
        with span("llm_synthesis"):
            log_event(log, "llm.stream.start", model=model, purpose="troubleshoot_non_stream")
            response = await llm.ainvoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=f"Retrieved context:\n{prep['context_text']}\n\nCustomer message: {message}"),
            ])
        body = _chunk_text(response.content).strip()
    except Exception:
        log.exception("troubleshoot LLM failed")
        log_event(log, "llm.stream.error", model=model, purpose="troubleshoot_non_stream")
        body = ""

    if not body:
        body = _fallback_body(prep["appliance"])

    text = f"{body}\n\n{TROUBLESHOOT_REDIRECT}"
    log_event(
        log,
        "llm.stream.done",
        model=model,
        purpose="troubleshoot_non_stream",
        char_count=len(body),
    )
    return {"text": text, "parts": prep["parts"]}


def troubleshoot_parts(message: str) -> list[dict] | None:
    """Parts related to the symptom (for response metadata)."""
    return prepare_troubleshoot(message)["parts"]
