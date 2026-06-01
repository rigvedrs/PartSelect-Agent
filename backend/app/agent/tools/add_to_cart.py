from sqlalchemy import text
from app.db.engine import get_engine
from app.agent.tools.search_parts import get_part_by_ps
from app.agent.tools.part_validation import is_valid_part
from app.agent.tools.part_enrichment import enrich_part_details, needs_enrichment
from app.observability import get_logger, log_event, span

log = get_logger("tools.add_to_cart")


def _upsert_part(conn, part: dict) -> None:
    conn.execute(text("""
        INSERT INTO parts (ps_number, name, price, stock_status, brand, product_url, image_url)
        VALUES (:ps, :name, :price, :stock, :brand, :url, :img)
        ON CONFLICT (ps_number) DO UPDATE SET
            name = CASE
                WHEN parts.name ILIKE '%page not found%' OR parts.name = parts.ps_number
                THEN EXCLUDED.name ELSE parts.name END,
            price = CASE
                WHEN EXCLUDED.price IS NOT NULL THEN EXCLUDED.price
                ELSE parts.price END,
            stock_status = COALESCE(EXCLUDED.stock_status, parts.stock_status),
            brand = COALESCE(EXCLUDED.brand, parts.brand),
            product_url = COALESCE(EXCLUDED.product_url, parts.product_url),
            image_url = COALESCE(EXCLUDED.image_url, parts.image_url)
    """), {
        "ps": part["ps_number"].upper(),
        "name": part.get("name") or part["ps_number"],
        "price": part.get("price"),
        "stock": part.get("stock_status"),
        "brand": part.get("brand"),
        "url": part.get("product_url"),
        "img": part.get("image_url"),
    })


def _resolve_part_row(ps: str, part_hint: dict | None = None) -> dict | None:
    """Load a valid part row, refreshing junk DB cache when needed."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ps_number, name, price, stock_status, brand, product_url, image_url "
            "FROM parts WHERE ps_number = :ps"
        ), {"ps": ps}).mappings().first()

    if row and is_valid_part(dict(row)):
        part = dict(row)
        if part_hint and part_hint.get("product_url"):
            part["product_url"] = part_hint["product_url"]
        if not needs_enrichment(part):
            return part
        part = enrich_part_details(part, force_price_refresh=bool(part.get("product_url")))
        if is_valid_part(part) and not needs_enrichment(part):
            with engine.begin() as conn:
                _upsert_part(conn, part)
            return part

    hint = part_hint
    resolved = get_part_by_ps(ps, fallback=hint)
    if resolved:
        if hint and hint.get("product_url") and not resolved.get("product_url"):
            resolved["product_url"] = hint["product_url"]
        resolved = enrich_part_details(resolved, force_price_refresh=True)
    if not resolved or not is_valid_part(resolved):
        return None

    with engine.begin() as conn:
        _upsert_part(conn, resolved)
        row = conn.execute(text(
            "SELECT ps_number, name, price, stock_status, brand, product_url, image_url "
            "FROM parts WHERE ps_number = :ps"
        ), {"ps": ps}).mappings().first()
    return dict(row) if row else resolved


def add_to_cart(
    session_id: str,
    ps_number: str,
    quantity: int = 1,
    part_hint: dict | None = None,
) -> dict:
    """Add a part to the session cart. Returns updated cart summary."""
    ps = ps_number.upper()
    log_event(log, "tool.call.start", tool="add_to_cart", ps_number=ps, quantity=quantity, has_hint=bool(part_hint))
    with span("tool_add_to_cart"):
        part = _resolve_part_row(ps, part_hint)
        if not part:
            log_event(log, "tool.call.done", tool="add_to_cart", ps_number=ps, success=False)
            return {"success": False, "error": f"Part {ps} not found."}

        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO sessions (session_id) VALUES (:sid)
                ON CONFLICT (session_id) DO NOTHING
            """), {"sid": session_id})
            conn.execute(text("""
                INSERT INTO carts (session_id) VALUES (:sid)
                ON CONFLICT (session_id) DO NOTHING
            """), {"sid": session_id})

            conn.execute(text("""
                INSERT INTO cart_items (session_id, ps_number, quantity)
                VALUES (:sid, :ps, :qty)
                ON CONFLICT (session_id, ps_number)
                DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
            """), {"sid": session_id, "ps": ps, "qty": quantity})

            items = conn.execute(text("""
                SELECT ci.ps_number, ci.quantity, p.name, p.price, p.image_url, p.product_url
                FROM cart_items ci JOIN parts p ON ci.ps_number = p.ps_number
                WHERE ci.session_id = :sid
            """), {"sid": session_id}).mappings().all()

        item_list = [dict(i) for i in items]
        for item in item_list:
            if not is_valid_part(item):
                fresh = _resolve_part_row(item["ps_number"], part_hint)
                if fresh:
                    item.update({k: fresh.get(k) for k in ("name", "price", "image_url", "product_url")})

        total = sum((i["price"] or 0) * i["quantity"] for i in item_list)
        cart_count = sum(i["quantity"] for i in item_list)
        log_event(log, "tool.call.done", tool="add_to_cart", ps_number=ps, success=True, cart_count=cart_count, cart_total=round(float(total), 2))
        return {
            "success": True,
            "added": {
                "ps_number": ps,
                "name": part["name"],
                "price": float(part["price"] or 0),
            },
            "cart_total": round(float(total), 2),
            "cart_count": cart_count,
        }
