"""LLM intent router — single structured call using the tool model."""
from __future__ import annotations

import re
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from app.agent.llm_provider import get_classifier_llm
from app.config import load_settings
from app.observability import get_logger, log_event, safe_preview, span

log = get_logger("agent.router")

_PS_PATTERN = re.compile(r"\bPS\d{5,}\b", re.IGNORECASE)
_MODEL_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,6}\d{3,}[A-Z0-9]*|\d{6,14})\b",
    re.IGNORECASE,
)

# LLMs often emit the word "null" in string fields instead of omitting them.
_LLM_EMPTY_TOKENS = frozenset({"null", "none", "nil", "n/a", "na", "undefined", "empty"})

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

Structured fields:
- browse_all_parts (boolean): true when the user wants the full compatible catalog for their model
  with NO part-type filter (e.g. "list all its parts", "show all parts for my model").
- part_query (string, optional): ONLY when browse_all_parts is false — a short part-type phrase
  such as "water filter" or "door hinge". Never put a model number or the word null here.
- ps_number: PartSelect PS##### when present in the message.

Rules:
- For add_to_cart/remove_from_cart with pronouns ("it", "that one"): omit ps_number — the app resolves from session.
- compatibility ONLY when both a PS number and model context appear; otherwise use search or parts_for_model.
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
    """Structured classifier output — validated at the LLM boundary."""

    intent: Intent
    browse_all_parts: bool = Field(
        default=False,
        description="True when listing the full compatible catalog without a part-type filter",
    )
    part_query: str | None = Field(
        default=None,
        description="Part-type keywords when browse_all_parts is false",
    )
    ps_number: str | None = Field(
        default=None,
        description="PartSelect PS number if mentioned",
    )

    @field_validator("part_query", mode="before")
    @classmethod
    def _coerce_part_query(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in _LLM_EMPTY_TOKENS:
            return None
        return text

    @field_validator("ps_number", mode="before")
    @classmethod
    def _coerce_ps_number(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip().upper()
        if not text or text in _LLM_EMPTY_TOKENS:
            return None
        if text.startswith("PS"):
            return text
        return None

    def catalog_filter_query(self, appliance_model: str | None = None) -> str | None:
        """Part-type filter for catalog lookups, or None for an unfiltered list."""
        if self.browse_all_parts:
            return None
        if not self.part_query:
            return None
        query = self.part_query.strip()
        if appliance_model and query.upper() == appliance_model.strip().upper():
            return None
        model_token = extract_model_number(query)
        if model_token and model_token.upper() == query.upper():
            return None
        return query


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


def _fallback_browse_all(message: str) -> bool:
    lower = message.lower()
    return bool(
        re.search(r"\b(?:list|show)\s+all\b", lower)
        or re.search(r"\ball\s+(?:of\s+)?(?:its|the|my)\s+parts?\b", lower)
    )


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
        return IntentResult(
            intent=Intent.PARTS_FOR_MODEL,
            browse_all_parts=_fallback_browse_all(message),
            part_query=None if _fallback_browse_all(message) else _guess_part_query(message),
        )
    if any(k in lower for k in ("not working", "leaking", "not draining", "how to fix", "repair")):
        return IntentResult(intent=Intent.TROUBLESHOOT)
    if any(k in lower for k in ("find", "need", "looking for", "search")):
        return IntentResult(
            intent=Intent.SEARCH,
            ps_number=ps_number,
            part_query=_guess_part_query(message),
        )
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
    settings = load_settings()
    log_event(log, "intent.classify.start", model=settings.llm.tool_model, message=safe_preview(text))

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
        with span("classifier"):
            result: IntentResult = await llm.ainvoke([
                SystemMessage(content=_CLASSIFIER_PROMPT),
                HumanMessage(content=user_content),
            ])
        log.info(
            "classified intent=%s browse_all=%s part_query=%r ps=%r",
            result.intent.value, result.browse_all_parts, result.part_query, result.ps_number,
        )
        log_event(
            log,
            "intent.classify.done",
            model=settings.llm.tool_model,
            intent=result.intent.value,
            browse_all=result.browse_all_parts,
            part_query=result.part_query,
            ps_number=result.ps_number,
            fallback=False,
        )
        return result
    except Exception:
        log.exception("LLM intent classification failed, using fallback")
        fallback = _fallback_classification(text)
        log_event(
            log,
            "intent.classify.done",
            model=settings.llm.tool_model,
            intent=fallback.intent.value,
            fallback=True,
        )
        return fallback
