from __future__ import annotations

_REFRIGERATOR = ("refrigerator", "fridge", "freezer")
_DISHWASHER = ("dishwasher",)


def parse_price(value) -> float | None:
    if value is None:
        return None
    s = str(value).strip().lstrip("$")
    if not s:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _appliance_from_text(description: str) -> str | None:
    desc = (description or "").lower()
    if any(k in desc for k in _DISHWASHER):
        return "dishwasher"
    if any(k in desc for k in _REFRIGERATOR):
        return "refrigerator"
    return None


def infer_category(raw: dict) -> str | None:
    """Return the primary category for a part based on its cross-reference descriptions.

    When refs span both appliance types, 'dishwasher' wins so the part is
    searchable in the dishwasher scope. Use extract_compat_rows to get
    per-ref appliance tags for the compatibility table.
    """
    combined = " ".join(
        (ref.get("description") or "").lower()
        for ref in (raw.get("model_cross_reference") or [])
    )
    if any(k in combined for k in _DISHWASHER):
        return "dishwasher"
    if any(k in combined for k in _REFRIGERATOR):
        return "refrigerator"
    return None


def reshape_part(raw: dict) -> dict:
    ps = raw.get("partselect_number")
    name = raw.get("name")
    if not ps or not name:
        raise ValueError(f"Part missing required fields ps_number={ps!r} name={name!r}")
    return {
        "ps_number": ps,
        "manufacturer_part_number": raw.get("manufacturer_part_number"),
        "name": name,
        "price": parse_price(raw.get("price")),
        "stock_status": raw.get("availability"),
        "brand": raw.get("manufacturer"),
        "manufactured_for": raw.get("manufactured_for"),
        "description": raw.get("description"),
        "category": infer_category(raw),
        "product_url": raw.get("product_url"),
        "image_url": raw.get("main_image"),
        "video_url": raw.get("video_url"),
        "symptoms": raw.get("symptoms") or [],
        "replaces": raw.get("replaces") or [],
        "installation_steps": raw.get("installation_steps") or [],
    }


def extract_compat_rows(raw: dict) -> list[dict]:
    """Return one compatibility row per model_cross_reference entry.

    Each row gets its own appliance tag derived from that ref's description,
    so mixed-appliance parts produce correctly tagged rows for both categories.
    """
    ps = raw.get("partselect_number")
    rows, seen = [], set()
    for ref in raw.get("model_cross_reference") or []:
        model = ref.get("model_number")
        if not model or model in seen:
            continue
        seen.add(model)
        rows.append({
            "ps_number": ps,
            "model_number": model,
            "brand": ref.get("brand"),
            "appliance": _appliance_from_text(ref.get("description", "")),
        })
    return rows
