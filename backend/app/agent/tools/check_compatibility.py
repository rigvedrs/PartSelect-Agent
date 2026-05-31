import re
from sqlalchemy import text
from app.db.engine import get_engine
from app.observability import get_logger


def check_compatibility(model_number: str, part_number_or_query: str) -> dict:
    """Deterministic SQL compatibility check. Never uses vector search."""
    engine = get_engine()
    with engine.connect() as conn:
        ps_match = re.search(r"PS\d+", part_number_or_query, re.IGNORECASE)
        ps_number = ps_match.group(0).upper() if ps_match else None

        if not ps_number:
            row = conn.execute(text(
                "SELECT ps_number FROM parts WHERE LOWER(name) LIKE :q LIMIT 1"
            ), {"q": f"%{part_number_or_query.lower()}%"}).mappings().first()
            ps_number = row["ps_number"] if row else None

        if not ps_number:
            return {"compatible": False, "source": "none", "reason": "Part not found.", "alternative_parts": []}

        compat = conn.execute(text("""
            SELECT c.model_number, c.brand, c.appliance
            FROM compatibility c
            WHERE c.ps_number = :ps AND UPPER(c.model_number) = UPPER(:model)
        """), {"ps": ps_number, "model": model_number}).mappings().first()

        part = conn.execute(text(
            "SELECT name, price, image_url, product_url FROM parts WHERE ps_number = :ps"
        ), {"ps": ps_number}).mappings().first()

        log = get_logger("tools.check_compatibility")

        if compat:
            return {
                "compatible": True, "source": "db", "ps_number": ps_number,
                "part_name": part["name"] if part else ps_number,
                "reason": f"{ps_number} is compatible with model {model_number}.",
                "alternative_parts": [],
            }

        from scrapers.model_lookup import model_lists_part
        live = model_lists_part(model_number, ps_number)
        if live is True:
            log.info("compat live-confirmed ps=%s model=%s", ps_number, model_number)
            return {
                "compatible": True, "source": "live", "ps_number": ps_number,
                "part_name": part["name"] if part else ps_number,
                "reason": (
                    f"{ps_number} appears compatible with model {model_number} "
                    "(from a live PartSelect lookup — please confirm before ordering)."
                ),
                "alternative_parts": [],
            }
        return {
            "compatible": False, "source": "db" if live is False else "unverified",
            "ps_number": ps_number,
            "part_name": part["name"] if part else ps_number,
            "reason": f"{ps_number} is not confirmed compatible with model {model_number}.",
            "alternative_parts": [],
        }
