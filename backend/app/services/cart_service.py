from sqlalchemy import text
from app.db.engine import get_engine
from app.agent.tools.add_to_cart import _resolve_part_row
from app.agent.tools.part_validation import is_valid_part
from app.agent.tools.part_enrichment import enrich_part_details, needs_enrichment


def get_cart(session_id: str) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        items = conn.execute(text("""
            SELECT ci.ps_number, ci.quantity, p.name, p.price, p.image_url, p.product_url
            FROM cart_items ci JOIN parts p ON ci.ps_number = p.ps_number
            WHERE ci.session_id = :sid
        """), {"sid": session_id}).mappings().all()

    item_list = [dict(i) for i in items]
    for item in item_list:
        if not is_valid_part(item) or needs_enrichment(item):
            fresh = _resolve_part_row(item["ps_number"])
            if fresh:
                item["name"] = fresh["name"]
                item["price"] = fresh.get("price")
                item["image_url"] = fresh.get("image_url")
                item["product_url"] = fresh.get("product_url")
            elif is_valid_part(item):
                enriched = enrich_part_details(
                    {**item, "ps_number": item["ps_number"]},
                    force_price_refresh=bool(item.get("product_url")),
                )
                item["price"] = enriched.get("price")
                item["name"] = enriched.get("name", item["name"])

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
        """), {"sid": session_id, "ps": ps_number.upper()})
    return get_cart(session_id)
