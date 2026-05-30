"""Hardcoded seed parts ensuring the 3 case-study example queries always work."""

SEED_PARTS = [
    {
        "ps_number": "PS11752778",
        "manufacturer_part_number": "WPW10321304",
        "name": "Refrigerator Door Shelf Bin",
        "price": 47.40,
        "stock_status": "In Stock",
        "brand": "Whirlpool",
        "manufactured_for": "Whirlpool, KitchenAid, Maytag, Amana",
        "description": (
            "Genuine OEM replacement door bin. Clear design with white trim. "
            "Tool-free installation."
        ),
        "category": "refrigerator",
        "product_url": (
            "https://www.partselect.com/PS11752778-Whirlpool-WPW10321304"
            "-Refrigerator-Door-Shelf-Bin.htm"
        ),
        "image_url": "https://www.partselect.com/assets/images/parts/PS11752778.jpg",
        "video_url": None,
        "symptoms": ["Door bin cracked or broken"],
        "replaces": [],
        "installation_steps": [
            "Grab the old bin with both hands",
            "Lift it away from the door",
            "Line up the new bin where the old one was",
            "Drop it into place — no tools required",
        ],
    },
]

# Compatibility pairs: (model_number, brand) for each seed PS number.
# WDT780SAEM1 is the model from case-study example query 2.
SEED_COMPAT = {
    "PS11752778": [
        ("WDT780SAEM1", "Whirlpool"),
        ("WRS325SDHZ", "Whirlpool"),
        ("KRFF305ESS", "KitchenAid"),
    ],
}
