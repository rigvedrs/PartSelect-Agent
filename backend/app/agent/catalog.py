"""Compatible-parts catalog resolution — DB first, optional live fallback."""

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


def _package(
    model: str,
    parts: list[dict],
    source: CatalogSource,
    *,
    full_catalog: bool,
    reason: str | None = None,
) -> dict:
    from app.agent.messages import model_referral
    from app.observability import get_logger, log_event

    log = get_logger("agent.catalog")

    if not parts:
        log_event(log, "tool.call.done", tool="resolve_compatible_parts", model=model, source=CatalogSource.NONE.value, count=0, full_catalog=full_catalog)
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

    log_event(log, "tool.call.done", tool="resolve_compatible_parts", model=model, source=source.value, count=len(parts), full_catalog=full_catalog)
    return {
        "model_number": model,
        "parts": parts,
        "count": len(parts),
        "source": source.value,
        "reason": reason,
    }


def _resolve_live_catalog(
    model: str,
    part_type_filter: str | None,
    limit: int,
    *,
    full_catalog: bool,
) -> dict:
    from app.live_scrape.gateway import get_gateway
    from app.observability import get_logger, span

    log = get_logger("agent.catalog")
    gw = get_gateway()

    with span("live"):
        page_result = gw.fetch_model_parts(model, part_type_filter)
        if not page_result.data:
            return _package(model, [], CatalogSource.NONE, full_catalog=full_catalog)

        stubs = page_result.data
        assert isinstance(stubs, list)
        parts: list[dict] = []
        for stub in stubs[:limit]:
            detail = gw.fetch_part(stub["ps_number"], stub.get("product_url"))
            if detail.data:
                row = dict(detail.data)
            else:
                row = dict(stub)
            row["compat_model"] = model
            row["source"] = "live"
            row["backend"] = page_result.backend
            parts.append(row)

        log.info(
            "catalog source=live model=%s filter=%r n=%d backend=%s",
            model,
            part_type_filter,
            len(parts),
            page_result.backend,
        )
        return _package(model, parts, CatalogSource.LIVE, full_catalog=full_catalog)


def resolve_compatible_parts(request: CatalogRequest) -> dict:
    """Resolve parts from the local DB; live-scrape model page when enabled and DB sparse."""
    from app.observability import get_logger, log_event, span

    log = get_logger("agent.catalog")
    settings = load_settings()
    catalog_cfg = settings.catalog
    model = request.model_number.strip()
    live_enabled = settings.live_scrape.enabled
    log_event(
        log,
        "tool.call.start",
        tool="resolve_compatible_parts",
        model=model,
        scope=request.scope.value,
        part_query=request.part_type_filter,
        limit=request.limit,
        live_enabled=live_enabled,
    )

    if not model:
        return _package(model, [], CatalogSource.NONE, full_catalog=False)

    with span("db"):
        if request.scope == CatalogScope.FULL:
            limit = max(request.limit, catalog_cfg.full_catalog_limit)
            db = sources.fetch_from_db(model, None, limit)
            if len(db) >= catalog_cfg.db_completeness_min_parts:
                log.info("catalog scope=full source=db model=%s n=%d", model, len(db))
                return _package(model, db, CatalogSource.DB, full_catalog=True)
            if live_enabled:
                return _resolve_live_catalog(model, None, limit, full_catalog=True)
            return _package(model, [], CatalogSource.NONE, full_catalog=True)

        limit = min(max(request.limit, 1), catalog_cfg.filtered_catalog_limit)
        db = sources.fetch_from_db(model, request.part_type_filter, limit)
        if db:
            log.info(
                "catalog scope=by_part_type source=db model=%s filter=%r n=%d",
                model,
                request.part_type_filter,
                len(db),
            )
            return _package(model, db, CatalogSource.DB, full_catalog=False)

        if live_enabled:
            return _resolve_live_catalog(
                model, request.part_type_filter, limit, full_catalog=False
            )

    if request.part_type_filter:
        from app.agent.messages import part_type_not_found
        return _package(
            model, [], CatalogSource.NONE, full_catalog=False,
            reason=part_type_not_found(model, request.part_type_filter),
        )
    return _package(model, [], CatalogSource.NONE, full_catalog=False)
