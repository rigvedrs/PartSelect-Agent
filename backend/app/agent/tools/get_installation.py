import re
from sqlalchemy import text
from app.db.engine import get_engine


def get_installation_guide(part_number: str) -> dict:
    """Return installation steps for a part. Falls back to description if no steps."""
    engine = get_engine()
    ps_match = re.search(r"PS\d+", part_number, re.IGNORECASE)
    ps = ps_match.group(0).upper() if ps_match else part_number.upper()

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name, description, installation_steps, image_url, product_url, video_url "
            "FROM parts WHERE ps_number = :ps"
        ), {"ps": ps}).mappings().first()

        if not row:
            return {"found": False, "ps_number": ps, "steps": [], "description": ""}

        steps = list(row["installation_steps"] or [])
        if not steps and row["description"]:
            steps = [row["description"]]
        if not steps and row.get("video_url"):
            steps = [f"Watch the installation video: {row['video_url']}"]

        return {
            "found": True,
            "ps_number": ps,
            "part_name": row["name"],
            "steps": steps,
            "image_url": row["image_url"],
            "product_url": row["product_url"],
        }
