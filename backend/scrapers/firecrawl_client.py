import os
from firecrawl import FirecrawlApp


def get_client() -> FirecrawlApp:
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY not set")
    return FirecrawlApp(api_key=key)


def scrape_markdown(url: str) -> str:
    app = get_client()
    result = app.scrape_url(url, params={"formats": ["markdown"]})
    return result.get("markdown", "") if isinstance(result, dict) else ""
