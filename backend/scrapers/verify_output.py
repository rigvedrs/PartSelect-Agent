"""Compare freshly scraped samples against existing raw JSONL baselines."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from scrapers import browser, io_utils
from scrapers import compat_enricher, detail_extractor
from scrapers.product_utils import clean_product_url


def _norm_price(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip().lstrip("$").replace(",", "")
    if not s:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _compare_part(old: dict, new: dict) -> dict[str, bool]:
    old_price = _norm_price(old.get("price"))
    new_price = _norm_price(new.get("price"))
    checks = {
        "name": (old.get("name") or "").strip() == (new.get("name") or "").strip(),
        "price": old_price is not None and new_price is not None,
        "availability": bool((old.get("availability") or "").strip())
        and bool((new.get("availability") or "").strip()),
        "manufacturer_part_number": (old.get("manufacturer_part_number") or "").strip()
        == (new.get("manufacturer_part_number") or "").strip(),
        "symptoms_count": len(old.get("symptoms") or []) == len(new.get("symptoms") or []),
        "crossref_count": len(new.get("model_cross_reference") or []) >= len(
            old.get("model_cross_reference") or []
        ),
    }
    return checks


def verify_parts(samples: int, seed: int) -> dict[str, Any]:
    baseline_path = io_utils.PARTS_OUT
    if not baseline_path.exists():
        return {"error": f"missing {baseline_path}"}

    by_ps = {r["partselect_number"]: r for r in io_utils.iter_jsonl(baseline_path) if r.get("partselect_number")}
    picks = io_utils.sample_ps_numbers(baseline_path, samples, seed=seed)
    driver = browser.build_chrome(headless=True)
    results: list[dict] = []
    try:
        for ps in picks:
            old = by_ps.get(ps)
            if not old:
                continue
            url = clean_product_url(old.get("product_url")) or detail_extractor.ps_url_from_number(ps)
            detail = detail_extractor.extract_product_record(driver, url)
            fresh = compat_enricher.enrich_record(driver, detail)
            checks = _compare_part(old, fresh)
            core = {k: checks[k] for k in ("name", "manufacturer_part_number", "symptoms_count", "price")}
            results.append(
                {
                    "ps": ps,
                    "checks": checks,
                    "core_match": all(core.values()),
                    "all_match": all(checks.values()),
                }
            )
    finally:
        driver.quit()

    matched = sum(1 for r in results if r["all_match"])
    core_matched = sum(1 for r in results if r["core_match"])
    return {
        "sampled": len(results),
        "full_match": matched,
        "core_match": core_matched,
        "match_rate": round(matched / len(results), 3) if results else 0.0,
        "core_match_rate": round(core_matched / len(results), 3) if results else 0.0,
        "details": results,
    }


def verify_repairs(sample: int = 5) -> dict[str, Any]:
    path = io_utils.REPAIRS_OUT
    required = {"item", "symptom", "part", "text"}
    rows = list(io_utils.iter_jsonl(path))[:sample]
    ok = all(required <= set(r) for r in rows)
    return {"path": str(path), "rows_checked": len(rows), "schema_ok": ok}


def verify_articles(sample: int = 5) -> dict[str, Any]:
    path = io_utils.ARTICLES_OUT
    rows = list(io_utils.iter_jsonl(path))[:sample]
    schema_ok = True
    for row in rows:
        if not {"url", "title", "sections"} <= set(row):
            schema_ok = False
            break
        for sec in row.get("sections") or []:
            if not {"heading", "text", "video"} <= set(sec):
                schema_ok = False
                break
    return {"path": str(path), "rows_checked": len(rows), "schema_ok": schema_ok}


def audit_crossref_completeness(parts_path: str | None = None) -> dict[str, Any]:
    """Report cross-reference completeness; flags the legacy 30-row truncation.

    The original scrape capped model_cross_reference at 30 entries per part.
    A complete scrape will have at least some parts exceeding 30 rows.
    max > 30 means the cap is gone.
    """
    from pathlib import Path
    path = Path(parts_path) if parts_path else io_utils.PARTS_OUT
    if not path.exists():
        return {"error": f"missing {path}", "complete": False}
    counts = [
        len(json.loads(line).get("model_cross_reference") or [])
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not counts:
        return {"parts": 0, "max": 0, "at_cap_30": 0, "over_30": 0, "complete": False}
    at_cap = sum(1 for c in counts if c == 30)
    over_cap = sum(1 for c in counts if c > 30)
    result: dict[str, Any] = {
        "parts": len(counts),
        "max": max(counts),
        "at_cap_30": at_cap,
        "over_30": over_cap,
        "complete": max(counts) > 30,
    }
    print("crossref audit:", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--audit", action="store_true", help="Run cross-reference completeness audit only")
    args = parser.parse_args(argv)

    if args.audit:
        result = audit_crossref_completeness()
        return 0 if result.get("complete") else 1

    report = {
        "parts": verify_parts(args.samples, args.seed),
        "repairs": verify_repairs(),
        "articles": verify_articles(),
    }
    print(json.dumps(report, indent=2))
    parts = report.get("parts") or {}
    if parts.get("core_match_rate", 0) < 0.7 and parts.get("sampled", 0) > 0:
        return 1
    if not report["repairs"].get("schema_ok") or not report["articles"].get("schema_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
