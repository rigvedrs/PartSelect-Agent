from __future__ import annotations
import re
from enum import Enum

_PS_PATTERN = re.compile(r"\bPS\d{5,}\b", re.IGNORECASE)
# Alphanumeric (WRS325SDHZ) or numeric-only OEM model numbers (10640262010)
_MODEL_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,6}\d{3,}[A-Z0-9]*|\d{6,14})\b",
    re.IGNORECASE,
)


def extract_model_number(message: str) -> str | None:
    """First appliance model token in text (excludes PS part numbers)."""
    for m in _MODEL_PATTERN.finditer(message):
        token = m.group(0)
        if not token.upper().startswith("PS"):
            return token
    return None


class Intent(str, Enum):
    INSTALL = "install"
    COMPATIBILITY = "compatibility"
    PARTS_FOR_MODEL = "parts_for_model"
    TROUBLESHOOT = "troubleshoot"
    SEARCH = "search"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    COMPLEX = "complex"


_INSTALL_KW = ("install", "installation", "how to install", "replace", "how do i put")
_COMPAT_KW = ("compatible", "compatibility", "fit", "work with", "work on", "fits")
_PARTS_FOR_MODEL_KW = (
    "compatible parts", "parts compatible", "parts for my", "parts that fit",
    "what parts fit", "which parts fit", "list parts", "show parts for",
    "parts work with", "fits my model", "for my model",
)
_TROUBLE_KW = (
    "not working", "broken", "leaking", "won't", "wont", "doesn't", "doesnt",
    "stopped", "noise", "error", "problem", "issue", "not cooling",
    "not draining", "not heating", "not dispensing",
    "how to fix", "how can i fix", "how do i fix", "fix it", "fix my",
)
_CART_ADD_KW = ("add to cart", "add to my cart", "to cart")
_CART_REMOVE_KW = (
    "remove from cart", "delete from cart", "remove from my cart",
    "take out of cart", "take off cart", "remove it from cart",
)
_SEARCH_KW = ("find", "search", "look up", "show me", "what is", "price of", "need a", "looking for")


def routing_query(message: str) -> str:
    """Intent classification uses only the latest user utterance (last line or sentence)."""
    text = (message or "").strip()
    if not text:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        return lines[-1]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 1:
        return sentences[-1]
    return text


def classify_intent(message: str) -> Intent:
    """Classify intent from the latest query fragment only (not prior chat turns)."""
    message = routing_query(message)
    lower = message.lower()
    has_ps = bool(_PS_PATTERN.search(message))
    has_model = extract_model_number(message) is not None

    has_remove = any(kw in lower for kw in _CART_REMOVE_KW) or (
        "remove" in lower and "cart" in lower
    )
    has_cart_add = any(kw in lower for kw in _CART_ADD_KW) or (
        "add" in lower and "cart" in lower
    )
    has_order_intent = any(kw in lower for kw in ("order", "buy", "purchase"))
    has_install = any(kw in lower for kw in _INSTALL_KW)
    has_compat = any(kw in lower for kw in _COMPAT_KW)
    has_parts_for_model = any(kw in lower for kw in _PARTS_FOR_MODEL_KW)
    has_trouble = any(kw in lower for kw in _TROUBLE_KW)
    has_search = any(kw in lower for kw in _SEARCH_KW)

    if has_remove:
        return Intent.REMOVE_FROM_CART

    intents_detected = sum([
        has_cart_add, has_install, has_compat and not has_parts_for_model, has_trouble,
        has_parts_for_model, has_order_intent,
    ])
    if intents_detected > 1:
        return Intent.COMPLEX

    if has_cart_add and has_ps:
        return Intent.ADD_TO_CART
    if has_install and has_ps:
        return Intent.INSTALL
    if has_compat and has_ps and (has_model or has_compat):
        return Intent.COMPATIBILITY
    if has_parts_for_model or (has_compat and has_model and not has_ps):
        return Intent.PARTS_FOR_MODEL
    if has_compat and has_ps:
        return Intent.COMPATIBILITY
    if has_trouble:
        return Intent.TROUBLESHOOT
    if has_search or (has_ps and not has_compat):
        return Intent.SEARCH

    return Intent.COMPLEX
