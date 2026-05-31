"""List parts compatible with an appliance model — thin wrapper over catalog resolver."""

from __future__ import annotations

from app.agent.catalog import CatalogRequest, CatalogScope, resolve_compatible_parts


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
    if scope == CatalogScope.FULL:
        return resolve_compatible_parts(CatalogRequest(
            model_number=model_number,
            scope=CatalogScope.FULL,
            limit=limit,
        ))
    if scope == CatalogScope.BY_PART_TYPE:
        return resolve_compatible_parts(CatalogRequest(
            model_number=model_number,
            scope=CatalogScope.BY_PART_TYPE,
            part_type_filter=filt,
            limit=limit,
        ))
    # Legacy: infer scope only when caller did not classify (e.g. agent tools)
    from app.agent.catalog_sources import part_type_keywords
    inferred = (
        CatalogScope.BY_PART_TYPE
        if part_type_keywords(filt or "")
        else CatalogScope.FULL
    )
    return resolve_compatible_parts(CatalogRequest(
        model_number=model_number,
        scope=inferred,
        part_type_filter=filt if inferred == CatalogScope.BY_PART_TYPE else None,
        limit=limit,
    ))
