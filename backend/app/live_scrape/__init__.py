"""Runtime live-scrape fallback gateway (config-toggleable, ephemeral)."""

from app.live_scrape.gateway import LiveResult, LiveScrapeGateway, get_gateway

__all__ = ["LiveResult", "LiveScrapeGateway", "get_gateway"]
