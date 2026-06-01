"""List parts compatible with an appliance model — thin wrapper over catalog resolver."""

from __future__ import annotations

from app.agent.catalog import CatalogRequest, CatalogScope, resolve_compatible_parts
from app.observability import get_logger, log_event, safe_preview

log = get_logger("tools.list_compatible_parts")


def list_compatible_parts(
    model_number: str,
    part_query: str | None = None,
    limit: int = 10,
    *,
    scope: CatalogScope | None = None,
    part_type_filter: str | None = None,
) -> dict:
    """List compatible parts.

    Prefer passing scope from IntentResult.browse_all_parts.
    part_query remains for LangGraph tools and legacy callers.
    """
    filt = part_type_filter if part_type_filter is not None else part_query
    log_event(
        log,
        "tool.call.start",
        tool="list_compatible_parts",
        model=model_number,
        part_query=safe_preview(filt),
        limit=limit,
        scope=scope.value if scope else "infer",
    )
    if scope == CatalogScope.FULL:
        result = resolve_compatible_parts(CatalogRequest(
            model_number=model_number,
            scope=CatalogScope.FULL,
            limit=limit,
        ))
        log_event(log, "tool.call.done", tool="list_compatible_parts", source=result.get("source"), count=result.get("count"), scope=CatalogScope.FULL.value)
        return result
    if scope == CatalogScope.BY_PART_TYPE:
        result = resolve_compatible_parts(CatalogRequest(
            model_number=model_number,
            scope=CatalogScope.BY_PART_TYPE,
            part_type_filter=filt,
            limit=limit,
        ))
        log_event(log, "tool.call.done", tool="list_compatible_parts", source=result.get("source"), count=result.get("count"), scope=CatalogScope.BY_PART_TYPE.value)
        return result
    # Legacy: infer scope only when caller did not classify (e.g. agent tools)
    from app.agent.catalog_sources import part_type_keywords
    inferred = (
        CatalogScope.BY_PART_TYPE
        if part_type_keywords(filt or "")
        else CatalogScope.FULL
    )
    result = resolve_compatible_parts(CatalogRequest(
        model_number=model_number,
        scope=inferred,
        part_type_filter=filt if inferred == CatalogScope.BY_PART_TYPE else None,
        limit=limit,
    ))
    log_event(log, "tool.call.done", tool="list_compatible_parts", source=result.get("source"), count=result.get("count"), scope=inferred.value)
    return result
