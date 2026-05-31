"""LLM intent router — single structured call using the tool model."""
from __future__ import annotations

import re
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm_provider import get_classifier_llm
from app.observability import get_logger

log = get_logger("agent.router")

_PS_PATTERN = re.compile(r"\bPS\d{5,}\b", re.IGNORECASE)
_MODEL_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,6}\d{3,}[A-Z0-9]*|\d{6,14})\b",
    re.IGNORECASE,
)

_CLASSIFIER_PROMPT = """You route messages for a PartSelect refrigerator and dishwasher parts assistant.

Choose exactly one intent:
- greeting: hi, hello, thanks, goodbye
- search: user wants to find/order a part type (water filter, screw, hinge, tube kit)
- parts_for_model: list or browse parts for their appliance model (with or without a part type)
- compatibility: check if one specific PS##### part fits a model — requires a PS number in the message
- install: installation instructions for a part
- troubleshoot: appliance broken, not working, leaking, how to fix/repair
- add_to_cart: add a part to cart
- remove_from_cart: remove a part from cart
- general: anything else or multi-step requests

Rules:
- Extract ps_number (PS#####) when present in the message.
- For add_to_cart/remove_from_cart with pronouns ("it", "that one"): leave ps_number null — the app resolves from the latest shown parts.
- compatibility ONLY when both a PS number and model context appear; otherwise use search or parts_for_model.
- For search/parts_for_model, set part_query to the part type only (e.g. "water filter", "door hinge").
- Use session model context when the user says "for it", "same model", "its parts".
- Prefer parts_for_model when listing parts for a named model; search when finding a part type."""


class Intent(str, Enum):
    GREETING = "greeting"
    SEARCH = "search"
    PARTS_FOR_MODEL = "parts_for_model"
    COMPATIBILITY = "compatibility"
    INSTALL = "install"
    TROUBLESHOOT = "troubleshoot"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    GENERAL = "general"


class IntentResult(BaseModel):
    intent: Intent
    part_query: str | None = Field(
        default=None,
        description="Part type or description for search/parts_for_model",
    )
    ps_number: str | None = Field(
        default=None,
        description="PartSelect PS number if mentioned",
    )


def latest_utterance(message: str) -> str:
    """Last non-empty line — used when a message contains prior context."""
    lines = [ln.strip() for ln in message.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else message.strip()


def extract_model_number(message: str) -> str | None:
    """First appliance model token in text (excludes PS part numbers)."""
    for m in _MODEL_PATTERN.finditer(message):
        token = m.group(0)
        if not token.upper().startswith("PS"):
            return token
    return None


def _guess_part_query(message: str) -> str | None:
    m = re.search(r"what\s+(.+?)\s+parts?\s", message, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?:find|need|looking for)\s+(?:a\s+)?(.+?)(?:\s+for|\?|$)", message, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _fallback_classification(message: str) -> IntentResult:
    """Minimal regex fallback if the LLM call fails."""
    ps = _PS_PATTERN.search(message)
    ps_number = ps.group(0).upper() if ps else None
    lower = message.lower()
    model = extract_model_number(message)

    if re.match(r"^(hi|hello|hey|good\s+(morning|afternoon|evening))\b", lower):
        return IntentResult(intent=Intent.GREETING)
    if ps_number and "cart" in lower:
        if "remove" in lower or "delete" in lower:
            return IntentResult(intent=Intent.REMOVE_FROM_CART, ps_number=ps_number)
        if "add" in lower:
            return IntentResult(intent=Intent.ADD_TO_CART, ps_number=ps_number)
    if "cart" in lower or re.search(r"\badd\s+it\b", lower):
        if "remove" in lower or "delete" in lower:
            return IntentResult(intent=Intent.REMOVE_FROM_CART)
        if "add" in lower or re.search(r"\badd\s+it\b", lower):
            return IntentResult(intent=Intent.ADD_TO_CART)
    if ps_number and "install" in lower:
        return IntentResult(intent=Intent.INSTALL, ps_number=ps_number)
    if ps_number and model:
        return IntentResult(intent=Intent.COMPATIBILITY, ps_number=ps_number)
    if model and not ps_number and any(k in lower for k in ("compatible", "parts", "fit")):
        return IntentResult(intent=Intent.PARTS_FOR_MODEL, part_query=_guess_part_query(message))
    if any(k in lower for k in ("not working", "leaking", "not draining", "how to fix", "repair")):
        return IntentResult(intent=Intent.TROUBLESHOOT)
    if any(k in lower for k in ("find", "need", "looking for", "search")):
        return IntentResult(intent=Intent.SEARCH, ps_number=ps_number, part_query=_guess_part_query(message))
    return IntentResult(intent=Intent.GENERAL, ps_number=ps_number)


async def classify_intent(
    message: str,
    session_model: str | None = None,
    last_parts: list[dict] | None = None,
) -> IntentResult:
    """Classify user intent via the tool LLM with structured output."""
    text = latest_utterance(message)
    if not text:
        return IntentResult(intent=Intent.GENERAL)

    context: list[str] = []
    if session_model:
        context.append(f"Known appliance model: {session_model}")
    if last_parts:
        shown = ", ".join(
            f"{p['ps_number']} ({p.get('name') or 'part'})" for p in last_parts[:5]
        )
        context.append(f"Latest shown parts (most recent reply): {shown}")

    user_content = text
    if context:
        user_content = f"[{' | '.join(context)}]\n{text}"

    try:
        llm = get_classifier_llm().with_structured_output(
            IntentResult, method="function_calling",
        )
        result: IntentResult = await llm.ainvoke([
            SystemMessage(content=_CLASSIFIER_PROMPT),
            HumanMessage(content=user_content),
        ])
        if result.ps_number:
            result.ps_number = result.ps_number.upper()
        log.info(
            "classified intent=%s part_query=%r ps=%r",
            result.intent.value, result.part_query, result.ps_number,
        )
        return result
    except Exception:
        log.exception("LLM intent classification failed, using fallback")
        return _fallback_classification(text)
