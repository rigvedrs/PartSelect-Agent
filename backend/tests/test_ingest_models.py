import pytest
from app.ingest_models import (
    reshape_part, infer_category, extract_compat_rows, parse_price,
)

RAW = {
    "product_url": "https://www.partselect.com/PS12745538-Whirlpool-W11419334-HOSE.htm",
    "name": "HOSE W11419334",
    "price": "43.8300",
    "availability": "In Stock",
    "partselect_number": "PS12745538",
    "manufacturer_part_number": "W11419334",
    "manufacturer": "Whirlpool",
    "manufactured_for": "Whirlpool, KitchenAid",
    "description": "A hose.",
    "replaces": ["W11250985"],
    "main_image": "https://img/x.jpg",
    "symptoms": ["Leaking"],
    "model_cross_reference": [
        {"brand": "Whirlpool", "model_number": "BLB14GRANA3", "description": "Dishwasher"},
        {"brand": "Maytag", "model_number": "JDPSG244LS0", "description": "Dishwasher - Dishwasher"},
    ],
}


def test_parse_price():
    assert parse_price("43.8300") == 43.83
    assert parse_price(None) is None
    assert parse_price("") is None


def test_parse_price_strips_dollar_sign():
    assert parse_price("$47.40") == 47.40


def test_infer_category_from_cross_reference():
    assert infer_category(RAW) == "dishwasher"


def test_infer_category_refrigerator():
    raw = dict(RAW)
    raw["model_cross_reference"] = [
        {"brand": "W", "model_number": "X", "description": "Refrigerator"}
    ]
    assert infer_category(raw) == "refrigerator"


def test_reshape_part_maps_fields():
    p = reshape_part(RAW)
    assert p["ps_number"] == "PS12745538"
    assert p["manufacturer_part_number"] == "W11419334"
    assert p["price"] == 43.83
    assert p["stock_status"] == "In Stock"
    assert p["image_url"] == "https://img/x.jpg"
    assert p["category"] == "dishwasher"
    assert p["replaces"] == ["W11250985"]


def test_reshape_part_raises_on_missing_ps_number():
    raw = dict(RAW)
    del raw["partselect_number"]
    with pytest.raises(ValueError, match="ps_number"):
        reshape_part(raw)


def test_reshape_part_raises_on_missing_name():
    raw = dict(RAW)
    del raw["name"]
    with pytest.raises(ValueError, match="name"):
        reshape_part(raw)


def test_extract_compat_rows_per_ref_appliance():
    raw = dict(RAW)
    raw["model_cross_reference"] = [
        {"brand": "Whirlpool", "model_number": "M1", "description": "Refrigerator"},
        {"brand": "Whirlpool", "model_number": "M2", "description": "Dishwasher"},
    ]
    rows = extract_compat_rows(raw)
    assert len(rows) == 2
    appliances = {r["model_number"]: r["appliance"] for r in rows}
    assert appliances["M1"] == "refrigerator"
    assert appliances["M2"] == "dishwasher"


def test_extract_compat_rows():
    rows = extract_compat_rows(RAW)
    assert {"ps_number": "PS12745538", "model_number": "BLB14GRANA3",
            "brand": "Whirlpool", "appliance": "dishwasher"} in rows
    assert len(rows) == 2


def test_infer_category_returns_none_for_out_of_scope():
    raw = dict(RAW)
    raw["model_cross_reference"] = [{"brand": "X", "model_number": "Y", "description": "Washer"}]
    assert infer_category(raw) is None
