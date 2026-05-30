from __future__ import annotations

_REFRIGERATOR = ("refrigerator", "fridge", "freezer")
_DISHWASHER = ("dishwasher",)


def parse_price(value) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def infer_category(raw: dict) -> str | None:
    """Return 'refrigerator'|'dishwasher'|None from cross-reference descriptions."""
    blobs = []
    for ref in raw.get("model_cross_reference") or []:
        blobs.append((ref.get("description") or "").lower())
    text = " ".join(blobs)
    if any(k in text for k in _DISHWASHER):
        return "dishwasher"
    if any(k in text for k in _REFRIGERATOR):
        return "refrigerator"
    return None


def reshape_part(raw: dict) -> dict:
    return {
        "ps_number": raw.get("partselect_number"),
        "manufacturer_part_number": raw.get("manufacturer_part_number"),
        "name": raw.get("name"),
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
    ps = raw.get("partselect_number")
    appliance = infer_category(raw)
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
            "appliance": appliance,
        })
    return rows
