from app.config import load_settings

_settings = None


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
