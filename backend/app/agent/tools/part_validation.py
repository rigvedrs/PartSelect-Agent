"""Shared helpers to reject scraped/ cached junk part rows."""


def is_valid_part(part: dict) -> bool:
    name = (part.get("name") or "").strip().lower()
    if not name:
        return False
    if "page not found" in name:
        return False
    ps = (part.get("ps_number") or "").upper()
    if name == ps.lower():
        return False
    return True
