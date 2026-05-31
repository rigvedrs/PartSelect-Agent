"""Compatible-parts catalog resolution — explicit scope and configurable source policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.agent import catalog_sources as sources
from app.config import load_settings


class CatalogScope(str, Enum):
    """What the user is asking for — drives source precedence."""

    FULL = "full"
    BY_PART_TYPE = "by_part_type"


class CatalogSource(str, Enum):
    DB = "db"
    LIVE = "live"
    NONE = "none"


@dataclass(frozen=True)
class CatalogRequest:
    model_number: str
    scope: CatalogScope
    part_type_filter: str | None = None
    limit: int = 10


def _live_enabled() -> bool:
    from scrapers.runtime_fetch import live_scrape_available
    return live_scrape_available()


def _package(
    model: str,
    parts: list[dict],
    source: CatalogSource,
    *,
    full_catalog: bool,
    reason: str | None = None,
) -> dict:
    from app.agent.messages import model_referral

    if not parts:
        return {
            "model_number": model,
            "parts": [],
            "count": 0,
            "source": CatalogSource.NONE.value,
            "reason": reason or model_referral(model),
        }

    if source == CatalogSource.LIVE:
        if full_catalog:
            reason = (
                f"Found {len(parts)} part(s) listed for {model} on PartSelect "
                "(live model page — local compatibility data may still be ingesting)."
            )
        else:
            reason = (
                f"Found {len(parts)} part(s) for {model} from a live PartSelect "
                "lookup — please confirm fit before ordering."
            )
    else:
        reason = f"Found {len(parts)} part(s) verified compatible with {model}."

    return {
        "model_number": model,
        "parts": parts,
        "count": len(parts),
        "source": source.value,
        "reason": reason,
    }


def _prefer_live_for_full_catalog(model: str, settings) -> bool:
    if not _live_enabled():
        return False
    if settings.full_catalog_primary_source == "live":
        return True
    db_count = len(sources.fetch_from_db(model, None, settings.db_completeness_min_parts + 1))
    return db_count < settings.db_completeness_min_parts


def resolve_compatible_parts(request: CatalogRequest) -> dict:
    """Resolve parts using scope-specific source precedence (see config [catalog])."""
    from app.observability import get_logger

    log = get_logger("agent.catalog")
    settings = load_settings().catalog
    model = request.model_number.strip()

    if not model:
        return _package(model, [], CatalogSource.NONE, full_catalog=False)

    if request.scope == CatalogScope.FULL:
        limit = max(request.limit, settings.full_catalog_limit)
        if _prefer_live_for_full_catalog(model, settings):
            live = sources.fetch_from_live(model, None, limit)
            if live.parts:
                log.info("catalog scope=full source=live model=%s n=%d", model, len(live.parts))
                return _package(model, live.parts, CatalogSource.LIVE, full_catalog=True)
        db = sources.fetch_from_db(model, None, limit)
        if db:
            log.info("catalog scope=full source=db model=%s n=%d", model, len(db))
            return _package(model, db, CatalogSource.DB, full_catalog=True)
        if _live_enabled():
            live = sources.fetch_from_live(model, None, limit)
            if live.parts:
                log.info("catalog scope=full source=live-fallback model=%s n=%d", model, len(live.parts))
                return _package(model, live.parts, CatalogSource.LIVE, full_catalog=True)
        return _package(model, [], CatalogSource.NONE, full_catalog=True)

    limit = min(max(request.limit, 1), settings.filtered_catalog_limit)
    db = sources.fetch_from_db(model, request.part_type_filter, limit)
    if db:
        log.info(
            "catalog scope=by_part_type source=db model=%s filter=%r n=%d",
            model, request.part_type_filter, len(db),
        )
        return _package(model, db, CatalogSource.DB, full_catalog=False)
    if _live_enabled():
        live = sources.fetch_from_live(model, request.part_type_filter, limit)
        if live.parts:
            log.info(
                "catalog scope=by_part_type source=live model=%s filter=%r n=%d",
                model, request.part_type_filter, len(live.parts),
            )
            return _package(model, live.parts, CatalogSource.LIVE, full_catalog=False)
        if request.part_type_filter and live.total_on_page > 0:
            from app.agent.messages import part_type_not_found
            hint = sources.infer_appliance_hint(live.page_part_names)
            log.info(
                "catalog scope=by_part_type model=%s filter=%r no_match total=%d hint=%r",
                model, request.part_type_filter, live.total_on_page, hint,
            )
            return _package(
                model, [], CatalogSource.NONE, full_catalog=False,
                reason=part_type_not_found(
                    model,
                    request.part_type_filter,
                    total_parts=live.total_on_page,
                    appliance_hint=hint,
                ),
            )
    return _package(model, [], CatalogSource.NONE, full_catalog=False)
