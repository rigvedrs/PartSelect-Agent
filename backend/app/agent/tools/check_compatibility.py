import re
from sqlalchemy import text
from app.db.engine import get_engine
from app.observability import get_logger, log_event, safe_preview

log = get_logger("tools.check_compatibility")


def _resolve_ps(conn, part_number_or_query: str) -> tuple[str | None, dict | None, str]:
    """Return (ps_number, part_dict|None, part_source)."""
    ps_match = re.search(r"PS\d+", part_number_or_query, re.IGNORECASE)
    ps_number = ps_match.group(0).upper() if ps_match else None

    if not ps_number:
        row = conn.execute(text(
            "SELECT ps_number, name, price, image_url, product_url FROM parts "
            "WHERE LOWER(name) LIKE :q LIMIT 1"
        ), {"q": f"%{part_number_or_query.lower()}%"}).mappings().first()
        if row:
            return row["ps_number"], dict(row), "db"
        return None, None, "none"

    row = conn.execute(text(
        "SELECT ps_number, name, price, image_url, product_url FROM parts WHERE ps_number = :ps"
    ), {"ps": ps_number}).mappings().first()
    if row:
        return ps_number, dict(row), "db"

    from app.live_scrape.gateway import get_gateway

    gw = get_gateway()
    if gw.is_enabled():
        live = gw.fetch_part(ps_number)
        if live.data:
            return ps_number, dict(live.data), "live"

    return ps_number, None, "none"


def check_compatibility(model_number: str, part_number_or_query: str) -> dict:
    """Deterministic compatibility check. DB first, live model-page fallback when enabled."""
    log_event(
        log,
        "tool.call.start",
        tool="check_compatibility",
        model=model_number,
        part=safe_preview(part_number_or_query),
    )
    engine = get_engine()
    with engine.connect() as conn:
        ps_number, part, part_source = _resolve_ps(conn, part_number_or_query)

        if not ps_number:
            log_event(log, "tool.call.done", tool="check_compatibility", source="none", compatible=False)
            return {
                "compatible": False,
                "source": "none",
                "reason": "Part not found.",
                "alternative_parts": [],
            }

        compat = conn.execute(text("""
            SELECT c.model_number, c.brand, c.appliance
            FROM compatibility c
            WHERE c.ps_number = :ps AND UPPER(c.model_number) = UPPER(:model)
        """), {"ps": ps_number, "model": model_number}).mappings().first()

        if not part:
            part = conn.execute(text(
                "SELECT name, price, image_url, product_url FROM parts WHERE ps_number = :ps"
            ), {"ps": ps_number}).mappings().first()
            if part:
                part = dict(part)
                part_source = "db"

        part_name = (part or {}).get("name") or ps_number

        if compat:
            log_event(log, "tool.call.done", tool="check_compatibility", source="db", ps_number=ps_number, model=model_number, compatible=True)
            return {
                "compatible": True,
                "source": "db",
                "ps_number": ps_number,
                "part_name": part_name,
                "reason": f"{ps_number} is compatible with model {model_number}.",
                "alternative_parts": [],
            }

        from app.live_scrape.gateway import get_gateway

        gw = get_gateway()
        if gw.is_enabled():
            live_compat = gw.check_compat_on_model_page(model_number, ps_number)
            if live_compat.data:
                compatible = bool(live_compat.data.get("compatible"))
                reason = (
                    f"{ps_number} appears on PartSelect's model page for {model_number}."
                    if compatible
                    else f"{ps_number} was not found on PartSelect's model page for {model_number}."
                )
                log_event(log, "tool.call.done", tool="check_compatibility", source="live", ps_number=ps_number, model=model_number, compatible=compatible)
                return {
                    "compatible": compatible,
                    "source": "live",
                    "backend": live_compat.backend,
                    "ps_number": ps_number,
                    "part_name": part_name,
                    "reason": reason,
                    "alternative_parts": [],
                }

        if part_source == "none" and not part:
            log_event(log, "tool.call.done", tool="check_compatibility", source="none", ps_number=ps_number, model=model_number, compatible=False)
            return {
                "compatible": False,
                "source": "none",
                "ps_number": ps_number,
                "part_name": ps_number,
                "reason": "Part not found.",
                "alternative_parts": [],
            }

        log_event(log, "tool.call.done", tool="check_compatibility", source="db", ps_number=ps_number, model=model_number, compatible=False)
        return {
            "compatible": False,
            "source": "db",
            "ps_number": ps_number,
            "part_name": part_name,
            "reason": (
                f"{ps_number} is not listed as compatible with model {model_number} "
                "in our catalog. Verify on PartSelect before ordering."
            ),
            "alternative_parts": [],
        }
