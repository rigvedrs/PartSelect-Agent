from sqlalchemy import text
from app.db.engine import get_engine


def get_cart(session_id: str) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        items = conn.execute(text("""
            SELECT ci.ps_number, ci.quantity, p.name, p.price, p.image_url
            FROM cart_items ci JOIN parts p ON ci.ps_number = p.ps_number
            WHERE ci.session_id = :sid
        """), {"sid": session_id}).mappings().all()
    item_list = [dict(i) for i in items]
    total = sum((i["price"] or 0) * i["quantity"] for i in item_list)
    return {
        "items": item_list,
        "total": round(float(total), 2),
        "count": sum(i["quantity"] for i in item_list),
    }


def remove_from_cart(session_id: str, ps_number: str) -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM cart_items WHERE session_id = :sid AND ps_number = :ps
        """), {"sid": session_id, "ps": ps_number})
    return get_cart(session_id)
