from __future__ import annotations
import re
from enum import Enum

_PS_PATTERN = re.compile(r"\bPS\d{5,}\b", re.IGNORECASE)
_MODEL_PATTERN = re.compile(r"\b[A-Z]{2,6}\d{3,}[A-Z0-9]*\b")


class Intent(str, Enum):
    INSTALL = "install"
    COMPATIBILITY = "compatibility"
    TROUBLESHOOT = "troubleshoot"
    SEARCH = "search"
    ADD_TO_CART = "add_to_cart"
    COMPLEX = "complex"


_INSTALL_KW = ("install", "installation", "how to install", "replace", "how do i put")
_COMPAT_KW = ("compatible", "compatibility", "fit", "work with", "work on")
_TROUBLE_KW = ("not working", "broken", "leaking", "won't", "wont", "doesn't", "doesnt",
               "stopped", "noise", "error", "problem", "issue", "not cooling",
               "not draining", "not heating", "not dispensing")
_CART_KW = ("add to cart", "add to my cart", "to cart", "buy", "order", "purchase")
_SEARCH_KW = ("find", "search", "look up", "show me", "what is", "price of")


def classify_intent(message: str) -> Intent:
    lower = message.lower()
    has_ps = bool(_PS_PATTERN.search(message))
    has_model = bool(_MODEL_PATTERN.search(message))

    has_cart = any(kw in lower for kw in _CART_KW)
    has_install = any(kw in lower for kw in _INSTALL_KW)
    has_compat = any(kw in lower for kw in _COMPAT_KW)
    has_trouble = any(kw in lower for kw in _TROUBLE_KW)
    has_search = any(kw in lower for kw in _SEARCH_KW)

    intents_detected = sum([has_cart, has_install, has_compat, has_trouble])
    if intents_detected > 1:
        return Intent.COMPLEX

    if has_cart and has_ps:
        return Intent.ADD_TO_CART
    if has_install and has_ps:
        return Intent.INSTALL
    if has_compat and (has_ps or has_model):
        return Intent.COMPATIBILITY
    if has_trouble:
        return Intent.TROUBLESHOOT
    if has_search or has_ps:
        return Intent.SEARCH

    return Intent.COMPLEX
