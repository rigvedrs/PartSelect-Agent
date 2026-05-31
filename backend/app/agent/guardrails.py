import re

from app.agent.router import Intent
from app.config import load_settings
from app.observability import get_logger

log = get_logger("agent.guardrails")

_settings = None

# Deterministic handler tool names (not LangChain tool names).
INTENT_ALLOWED_TOOLS: dict[Intent, frozenset[str]] = {
    Intent.GREETING: frozenset(),
    Intent.SEARCH: frozenset({"search_parts", "list_compatible_parts"}),
    Intent.PARTS_FOR_MODEL: frozenset({"list_compatible_parts"}),
    Intent.COMPATIBILITY: frozenset({"check_compatibility", "list_compatible_parts"}),
    Intent.INSTALL: frozenset({"get_installation_guide"}),
    Intent.TROUBLESHOOT: frozenset(),
    Intent.ADD_TO_CART: frozenset({"add_to_cart"}),
    Intent.REMOVE_FROM_CART: frozenset({"remove_from_cart"}),
    Intent.GENERAL: frozenset({
        "search_parts", "list_compatible_parts", "check_compatibility",
        "get_installation_guide",
    }),
}

# LangGraph agent tools — cart mutations stay on the deterministic router only.
GRAPH_BLOCKED_TOOLS = frozenset({"add_to_cart_tool", "remove_from_cart_tool"})


class IntentToolMismatchError(ValueError):
    """Raised when a handler tries to invoke a tool outside its classified intent."""


def _get_settings():
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def is_in_scope(message: str) -> bool:
    """Return False only when the message has zero appliance keywords AND
    contains a known out-of-scope keyword. Ambiguous messages pass through."""
    settings = _get_settings()
    lower = message.lower()
    has_appliance = any(kw in lower for kw in settings.scope.appliance_keywords)
    has_out_of_scope = any(kw in lower for kw in settings.scope.out_of_scope_keywords)
    if has_out_of_scope and not has_appliance:
        return False
    return True


def detect_cart_action(message: str) -> str | None:
    """Return 'add', 'remove', or None from explicit cart verbs in the message."""
    lower = message.lower()
    has_add = bool(re.search(r"\b(add|put)\b", lower))
    has_remove = bool(re.search(r"\b(remove|delete)\b", lower))
    refers = bool(re.search(r"\b(it|that|this|cart)\b", lower))
    if has_add and not has_remove and (refers or "cart" in lower):
        return "add"
    if has_remove and not has_add and (refers or "cart" in lower):
        return "remove"
    return None


def reconcile_cart_intent(intent: Intent, message: str) -> Intent:
    """Override classifier when message verbs clearly indicate add vs remove."""
    action = detect_cart_action(message)
    if action == "add":
        if intent != Intent.ADD_TO_CART:
            log.info("guardrail: intent %s -> add_to_cart (message verbs)", intent.value)
        return Intent.ADD_TO_CART
    if action == "remove":
        if intent != Intent.REMOVE_FROM_CART:
            log.info("guardrail: intent %s -> remove_from_cart (message verbs)", intent.value)
        return Intent.REMOVE_FROM_CART
    return intent


def assert_tool_allowed(intent: Intent, tool: str) -> None:
    """Block handler/tool pairings that contradict the classified intent."""
    allowed = INTENT_ALLOWED_TOOLS.get(intent)
    if allowed is None or tool in allowed:
        return
    log.warning("blocked tool=%s for intent=%s", tool, intent.value)
    raise IntentToolMismatchError(
        f"Tool {tool!r} is not allowed for intent {intent.value!r}"
    )


def filter_graph_tools(tool_names: list[str]) -> list[str]:
    """Drop cart tools from the LangGraph agent — cart is deterministic only."""
    return [name for name in tool_names if name not in GRAPH_BLOCKED_TOOLS]
