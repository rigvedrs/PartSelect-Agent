import re
from sqlalchemy import text
from app.db.engine import get_engine
from app.observability import get_logger, log_event

log = get_logger("tools.get_installation")


def format_installation_response(guide: dict, ps: str) -> str:
    """Build user-facing text from an installation guide result."""
    if not guide.get("found"):
        return (
            f"I couldn't find installation instructions for {ps} in our catalog or on PartSelect. "
            "Please verify the part number and try again."
        )

    name = guide.get("part_name") or ps
    lines = [f"Here are the installation instructions for {name}:"]
    steps = guide.get("steps") or []
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step}")

    if guide.get("source") == "live":
        lines.append("")
        lines.append("(Fetched live from PartSelect — Please confirm details on the product page before starting.)")

    missing = guide.get("missing_fields") or []
    if missing:
        lines.append(f"Note: {', '.join(missing)} were not available from the live page.")

    product_url = guide.get("product_url")
    if product_url:
        lines.append(f"Product page: {product_url}")

    return "\n".join(lines)


def get_installation_guide(part_number: str) -> dict:
    """Return installation steps for a part. Falls back to live scrape when enabled."""
    engine = get_engine()
    ps_match = re.search(r"PS\d+", part_number, re.IGNORECASE)
    ps = ps_match.group(0).upper() if ps_match else part_number.upper()
    log_event(log, "tool.call.start", tool="get_installation_guide", ps_number=ps)

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name, description, installation_steps, image_url, product_url "
            "FROM parts WHERE ps_number = :ps"
        ), {"ps": ps}).mappings().first()

    if row:
        steps = list(row["installation_steps"] or [])
        if steps:
            log_event(log, "tool.call.done", tool="get_installation_guide", ps_number=ps, source="db", found=True, steps_count=len(steps))
            return {
                "found": True,
                "ps_number": ps,
                "part_name": row["name"],
                "steps": steps,
                "source": "db",
                "image_url": row["image_url"],
                "product_url": row["product_url"],
            }

    from app.live_scrape.gateway import get_gateway

    gw = get_gateway()
    if gw.is_enabled():
        product_url = row["product_url"] if row else None
        live = gw.fetch_installation(ps, product_url)
        if live.data:
            data = live.data
            steps = list(data.get("steps") or [])
            log_event(log, "tool.call.done", tool="get_installation_guide", ps_number=ps, source="live", found=bool(steps), steps_count=len(steps), backend=live.backend)
            return {
                "found": bool(steps),
                "ps_number": ps,
                "part_name": data.get("part_name"),
                "steps": steps,
                "source": "live",
                "backend": live.backend,
                "complete": live.complete,
                "missing_fields": list(live.missing_fields),
                "product_url": data.get("product_url"),
                "image_url": None,
            }

    if not row:
        log_event(log, "tool.call.done", tool="get_installation_guide", ps_number=ps, source="none", found=False, steps_count=0)
        return {
            "found": False,
            "ps_number": ps,
            "steps": [],
            "description": "",
            "source": "none",
        }

    steps = list(row["installation_steps"] or [])
    if not steps and row["description"]:
        steps = [row["description"]]

    log_event(log, "tool.call.done", tool="get_installation_guide", ps_number=ps, source="db", found=bool(steps), steps_count=len(steps))
    return {
        "found": bool(steps),
        "ps_number": ps,
        "part_name": row["name"],
        "steps": steps,
        "source": "db",
        "image_url": row["image_url"],
        "product_url": row["product_url"],
    }
