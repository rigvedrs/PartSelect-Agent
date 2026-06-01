"""Single entry point for runtime live scraping — no DB writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.live_scrape import settings as live_settings
from app.observability import get_logger, log_event

log = get_logger("live_scrape.gateway")

Backend = Literal["firecrawl", "selenium"]


@dataclass(frozen=True)
class LiveResult:
    data: dict | list[dict] | None
    source: Literal["live"]
    backend: Backend
    complete: bool
    missing_fields: tuple[str, ...] = ()

    @classmethod
    def empty(cls, backend: Backend = "firecrawl") -> LiveResult:
        return cls(
            data=None,
            source="live",
            backend=backend,
            complete=False,
            missing_fields=(),
        )


def _backend() -> Backend:
    b = live_settings.resolve_backend()
    return "selenium" if b == "selenium" else "firecrawl"


def _empty() -> LiveResult:
    return LiveResult.empty(_backend())


class LiveScrapeGateway:
    def is_enabled(self) -> bool:
        return live_settings.is_enabled()

    def fetch_part(self, ps: str, product_url: str | None = None) -> LiveResult:
        if not live_settings.is_available():
            return _empty()

        backend = _backend()
        ps = ps.upper()
        log_event(log, "tool.call.start", tool="live.fetch_part", ps_number=ps, backend=backend, has_product_url=bool(product_url))
        try:
            from scrapers.parts_scraper import scrape_and_parse
            from app.ingest_models import reshape_part
            from app.agent.tools.part_validation import is_valid_part

            raw = scrape_and_parse(ps, product_url=product_url)
            if not raw:
                log_event(log, "tool.call.done", tool="live.fetch_part", ps_number=ps, backend=backend, source="none", complete=False)
                return LiveResult.empty(backend)

            shaped = reshape_part(raw)
            if not is_valid_part({"ps_number": shaped["ps_number"], "name": shaped["name"]}):
                log_event(log, "tool.call.done", tool="live.fetch_part", ps_number=ps, backend=backend, source="none", complete=False)
                return LiveResult.empty(backend)

            missing: list[str] = []
            if shaped.get("price") is None:
                missing.append("price")

            shaped["source"] = "live"
            shaped["backend"] = backend
            log_event(log, "tool.call.done", tool="live.fetch_part", ps_number=ps, backend=backend, source="live", complete=not missing, missing_count=len(missing))
            return LiveResult(
                data=shaped,
                source="live",
                backend=backend,
                complete=not missing,
                missing_fields=tuple(missing),
            )
        except Exception:
            log.exception("fetch_part failed ps=%s backend=%s", ps, backend)
            log_event(log, "tool.call.error", tool="live.fetch_part", ps_number=ps, backend=backend)
            return LiveResult.empty(backend)

    def fetch_model_parts(
        self, model: str, part_filter: str | None = None
    ) -> LiveResult:
        if not live_settings.is_available():
            return _empty()

        backend = _backend()
        log_event(log, "tool.call.start", tool="live.fetch_model_parts", model=model, part_query=part_filter, backend=backend)
        try:
            from scrapers.model_lookup import scrape_model_parts

            page = scrape_model_parts(model, part_filter)
            if not page.parts:
                log_event(log, "tool.call.done", tool="live.fetch_model_parts", model=model, backend=backend, source="none", count=0)
                return LiveResult.empty(backend)

            stubs = [
                {
                    "ps_number": p["ps_number"],
                    "name": p["name"],
                    "product_url": p.get("product_url"),
                    "source": "live",
                    "backend": backend,
                }
                for p in page.parts
            ]
            log_event(log, "tool.call.done", tool="live.fetch_model_parts", model=model, backend=backend, source="live", count=len(stubs))
            return LiveResult(
                data=stubs,
                source="live",
                backend=backend,
                complete=True,
                missing_fields=(),
            )
        except Exception:
            log.exception("fetch_model_parts failed model=%s backend=%s", model, backend)
            log_event(log, "tool.call.error", tool="live.fetch_model_parts", model=model, backend=backend)
            return LiveResult.empty(backend)

    def fetch_installation(
        self, ps: str, product_url: str | None = None
    ) -> LiveResult:
        if not live_settings.is_available():
            return _empty()

        backend = _backend()
        ps = ps.upper()
        log_event(log, "tool.call.start", tool="live.fetch_installation", ps_number=ps, backend=backend, has_product_url=bool(product_url))
        try:
            from scrapers.parts_scraper import scrape_installation_record

            raw = scrape_installation_record(ps, product_url=product_url)
            if not raw:
                log_event(log, "tool.call.done", tool="live.fetch_installation", ps_number=ps, backend=backend, source="none", complete=False)
                return LiveResult.empty(backend)

            name = (raw.get("name") or "").strip()
            if not name or "page not found" in name.lower():
                log_event(log, "tool.call.done", tool="live.fetch_installation", ps_number=ps, backend=backend, source="none", complete=False)
                return LiveResult.empty(backend)

            steps = list(raw.get("installation_steps") or [])
            missing = () if steps else ("installation_steps",)

            data = {
                "ps_number": ps,
                "part_name": name,
                "steps": steps,
                "product_url": raw.get("product_url"),
                "description": raw.get("description"),
                "source": "live",
                "backend": backend,
            }
            log_event(log, "tool.call.done", tool="live.fetch_installation", ps_number=ps, backend=backend, source="live", complete=bool(steps), missing_count=len(missing))
            return LiveResult(
                data=data,
                source="live",
                backend=backend,
                complete=bool(steps),
                missing_fields=missing,
            )
        except Exception:
            log.exception("fetch_installation failed ps=%s backend=%s", ps, backend)
            log_event(log, "tool.call.error", tool="live.fetch_installation", ps_number=ps, backend=backend)
            return LiveResult.empty(backend)

    def check_compat_on_model_page(self, model: str, ps: str) -> LiveResult:
        if not live_settings.is_available():
            return _empty()

        backend = _backend()
        ps = ps.upper()
        log_event(log, "tool.call.start", tool="live.check_compat_on_model_page", model=model, ps_number=ps, backend=backend)
        try:
            page_result = self.fetch_model_parts(model)
            if not page_result.data:
                data = {"compatible": False, "ps_number": ps, "model": model}
                log_event(log, "tool.call.done", tool="live.check_compat_on_model_page", model=model, ps_number=ps, backend=backend, compatible=False)
                return LiveResult(
                    data=data,
                    source="live",
                    backend=backend,
                    complete=True,
                    missing_fields=(),
                )

            stubs = page_result.data
            assert isinstance(stubs, list)
            compatible = any(s.get("ps_number") == ps for s in stubs)
            log_event(log, "tool.call.done", tool="live.check_compat_on_model_page", model=model, ps_number=ps, backend=backend, compatible=compatible, count=len(stubs))
            return LiveResult(
                data={"compatible": compatible, "ps_number": ps, "model": model},
                source="live",
                backend=backend,
                complete=True,
                missing_fields=(),
            )
        except Exception:
            log.exception(
                "check_compat_on_model_page failed model=%s ps=%s backend=%s",
                model,
                ps,
                backend,
            )
            log_event(log, "tool.call.error", tool="live.check_compat_on_model_page", model=model, ps_number=ps, backend=backend)
            return LiveResult.empty(backend)


_gateway: LiveScrapeGateway | None = None


def get_gateway() -> LiveScrapeGateway:
    global _gateway
    if _gateway is None:
        _gateway = LiveScrapeGateway()
    return _gateway
