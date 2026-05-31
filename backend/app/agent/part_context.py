"""Match recently shown parts to natural-language cart/search requests."""
from __future__ import annotations

import re

from app.agent.tools.search_parts import _extract_keywords

_PS_RE = re.compile(r"PS\d+", re.IGNORECASE)

_CART_STOP = frozenset({
    "add", "put", "remove", "delete", "cart", "also", "too", "well", "please",
    "the", "a", "an", "to", "from", "in", "my", "it", "that", "this", "one",
    "mean", "just", "only",
})


def _part_type_terms(text: str) -> list[str]:
    terms = [
        t for t in _extract_keywords(text or "").split()
        if t not in _CART_STOP and len(t) > 2
    ]
    return terms


def match_parts_by_query(parts: list[dict], query: str) -> list[dict]:
    """Return parts whose names match part-type keywords in the query."""
    terms = _part_type_terms(query)
    if not terms or not parts:
        return []

    strong = [
        p for p in parts
        if all(t in (p.get("name") or "").lower() for t in terms)
    ]
    if strong:
        return strong

    return [
        p for p in parts
        if any(t in (p.get("name") or "").lower() for t in terms)
    ]


def pick_best_part_match(matches: list[dict], query: str) -> dict | None:
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    lower = (query or "").lower()
    if "bypass" not in lower:
        non_bypass = [
            p for p in matches
            if "bypass" not in (p.get("name") or "").lower()
        ]
        if len(non_bypass) == 1:
            return non_bypass[0]
    return matches[0]


def _is_pronoun_reference(message: str) -> bool:
    lower = message.lower()
    return any(
        phrase in lower
        for phrase in (
            " it", "it ", "add it", "remove it", "that one", "this one",
            "that part", "this part", "the one",
        )
    )


def _is_pronoun_only_referent(message: str) -> bool:
    """True when the user refers to 'it/that' with no named part type in the message."""
    return _is_pronoun_reference(message) and not _part_type_terms(message)


def _is_cart_action(message: str) -> bool:
    lower = message.lower()
    return bool(re.search(r"\b(add|remove|delete|put)\b", lower)) or "cart" in lower


def resolve_ps_for_cart(
    message: str,
    classification_ps: str | None,
    part_query: str | None,
    last_parts: list[dict],
    recent_parts: list[dict],
) -> str | None:
    """Resolve PS number for cart actions.

    Priority:
    1. Explicit PS in the user message
    2. Pronoun-only ('add it') → latest shown batch (ignore classifier PS)
    3. Named part type in message → match session history
    4. Classifier PS (only when not a pronoun-only referent)
    """
    m = _PS_RE.search(message)
    if m:
        return m.group(0).upper()

    if not _is_cart_action(message):
        return None

    # Latest batch = what the assistant just showed; 'it' always means this set.
    if _is_pronoun_only_referent(message):
        if len(last_parts) == 1:
            return last_parts[0]["ps_number"]
        return None

    msg_terms = _part_type_terms(message)
    lookup = message if msg_terms else (part_query or message)
    if _part_type_terms(lookup):
        type_matches = match_parts_by_query(recent_parts, lookup)
        best = pick_best_part_match(type_matches, lookup)
        if best:
            return best["ps_number"]

    if classification_ps and not _is_pronoun_reference(message):
        return classification_ps.upper()

    return None
