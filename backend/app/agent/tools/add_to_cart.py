from sqlalchemy import text
from app.db.engine import get_engine


def add_to_cart(session_id: str, ps_number: str, quantity: int = 1) -> dict:
    """Add a part to the session cart. Returns updated cart summary."""
    engine = get_engine()
    with engine.begin() as conn:
        part = conn.execute(text(
            "SELECT ps_number, name, price, image_url FROM parts WHERE ps_number = :ps"
        ), {"ps": ps_number}).mappings().first()

        if not part:
            return {"success": False, "error": f"Part {ps_number} not found."}

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
        """), {"sid": session_id, "ps": ps_number, "qty": quantity})

        items = conn.execute(text("""
            SELECT ci.ps_number, ci.quantity, p.name, p.price
            FROM cart_items ci JOIN parts p ON ci.ps_number = p.ps_number
            WHERE ci.session_id = :sid
        """), {"sid": session_id}).mappings().all()

    total = sum((i["price"] or 0) * i["quantity"] for i in items)
    return {
        "success": True,
        "added": {"ps_number": ps_number, "name": part["name"], "price": float(part["price"] or 0)},
        "cart_total": round(float(total), 2),
        "cart_count": sum(i["quantity"] for i in items),
    }
