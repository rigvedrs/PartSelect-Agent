import re

from app.services.cart_service import remove_from_cart as _remove
from app.observability import get_logger, log_event

log = get_logger("tools.remove_from_cart")


def remove_from_cart(session_id: str, ps_number: str) -> dict:
    """Remove a part from the session cart by PS number."""
    ps = (ps_number or "").strip().upper()
    log_event(log, "tool.call.start", tool="remove_from_cart", ps_number=ps)
    if not ps:
        log_event(log, "tool.call.done", tool="remove_from_cart", success=False)
        return {"success": False, "error": "Part number is required."}
    if not ps.startswith("PS"):
        m = re.search(r"PS\d+", ps_number, re.IGNORECASE)
        ps = m.group(0).upper() if m else ps
    cart = _remove(session_id, ps)
    log_event(log, "tool.call.done", tool="remove_from_cart", ps_number=ps, success=True, cart_count=cart["count"], cart_total=cart["total"])
    return {
        "success": True,
        "removed": ps,
        "cart_total": cart["total"],
        "cart_count": cart["count"],
        "items": cart["items"],
    }
