"""Generate troubleshooting answers via RAG + synthesis LLM."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm_provider import get_llm
from app.agent.messages import TROUBLESHOOT_REDIRECT
from app.agent.tools.troubleshoot import (
    detect_appliance_type,
    retrieve_troubleshoot_context,
    format_context_for_llm,
)
from app.observability import get_logger

log = get_logger("agent.troubleshoot")

_SYSTEM = """You help customers troubleshoot refrigerator and dishwasher problems using PartSelect repair guides and articles.

Rules:
- Use ONLY the retrieved context below. Do not invent part numbers or steps not supported by the context.
- Give practical troubleshooting steps (2-4 short paragraphs).
- If a related part is listed in context, mention it by name and PS number.
- Stay focused on refrigerator/dishwasher scope.
- Do NOT include PartSelect marketing links or generic resource pages — those are appended separately.
- If context is limited, give safe general checks for that symptom and say which parts to inspect."""


async def generate_troubleshoot_answer(message: str) -> dict:
    """RAG retrieval + pro model synthesis, with PartSelect resource footer."""
    appliance = detect_appliance_type(message)
    ctx = retrieve_troubleshoot_context(message, appliance)
    context_text = format_context_for_llm(ctx)

    log.info(
        "troubleshoot rag appliance=%s causes=%d articles=%d parts=%d",
        appliance, len(ctx["causes"]), len(ctx["articles"]), len(ctx["parts"]),
    )

    llm = get_llm("synthesis")
    try:
        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=f"Retrieved context:\n{context_text}\n\nCustomer message: {message}"),
        ])
        body = response.content
        if isinstance(body, list):
            body = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in body
            )
        body = (body or "").strip()
    except Exception:
        log.exception("troubleshoot LLM failed")
        body = ""

    if not body:
        body = (
            f"For {appliance} issues like this, check power, water supply, filters, and door seals. "
            "Inspect the parts most commonly associated with your symptom."
        )

    text = f"{body}\n\n{TROUBLESHOOT_REDIRECT}"
    return {"text": text, "parts": ctx["parts"] or None}
