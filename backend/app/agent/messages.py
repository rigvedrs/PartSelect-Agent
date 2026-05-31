"""User-facing message templates shared across handlers and the LLM prompt."""

TROUBLESHOOT_REDIRECT = (
    "PartSelect has many resources to help you with troubleshooting and repairing your "
    "products. For helpful articles and how-to videos you can visit "
    "https://www.partselect.com/Repair/. To get help finding parts that may fix the issue "
    "you are facing you can also try our Instant Repairman feature at "
    "https://www.partselect.com/Instant-Repairman/."
)


def model_referral(model: str) -> str:
    return (
        "I couldn't confirm that from our catalog right now. You can check directly on "
        f"PartSelect: https://www.partselect.com/Models/{model}/"
    )


def part_type_not_found(
    model: str,
    part_query: str,
    *,
    total_parts: int,
    appliance_hint: str | None = None,
) -> str:
    """Model page exists but no parts matched the part-type filter."""
    label = part_query.strip().strip("\"'") or "that part type"
    text = (
        f"I found model {model} on PartSelect ({total_parts} compatible part(s) listed), "
        f"but none matching \"{label}\"."
    )
    if appliance_hint:
        text += (
            f" The listed parts look like {appliance_hint} components — "
            "double-check the model number if you expected something else."
        )
    text += f" Browse all parts: https://www.partselect.com/Models/{model}/"
    return text


def search_referral(query: str) -> str:
    from urllib.parse import quote_plus
    return (
        "I couldn't find that in our catalog right now. You can search PartSelect directly: "
        f"https://www.partselect.com/search/?searchterm={quote_plus(query)}"
    )
