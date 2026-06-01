"""Live scrape config resolution — config.toml first, env override for backend."""

from __future__ import annotations

import os

from app.config import load_settings


def is_enabled() -> bool:
    return load_settings().live_scrape.enabled


def resolve_backend() -> str:
    env = os.getenv("LIVE_SCRAPE_BACKEND", "").strip().lower()
    if env in ("firecrawl", "selenium"):
        return env
    return load_settings().live_scrape.backend


def is_available() -> bool:
    """True when live scrape is enabled and the chosen backend can run."""
    if not is_enabled():
        return False
    if resolve_backend() == "selenium":
        return True
    return bool(os.getenv("FIRECRAWL_API_KEY"))
