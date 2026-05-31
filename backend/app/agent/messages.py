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


def search_referral(query: str) -> str:
    from urllib.parse import quote_plus
    return (
        "I couldn't find that in our catalog right now. You can search PartSelect directly: "
        f"https://www.partselect.com/search/?searchterm={quote_plus(query)}"
    )
