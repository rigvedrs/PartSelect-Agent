"""Re-scrape a single part and patch parts.jsonl + Postgres."""
from __future__ import annotations

import argparse
import json
import os
import sys

from scrapers import browser, io_utils
from scrapers.detail_extractor import extract_product_record, ps_url_from_number
from app.ingest_models import reshape_part
from app.rag.ingest import _insert_part
from app.db.engine import get_engine


def patch_part(ps_number: str, *, headless: bool = True) -> dict:
    ps = ps_number.upper()
    url = ps_url_from_number(ps)
    driver = browser.build_chrome(headless=headless)
    try:
        raw = extract_product_record(driver, url)
    finally:
        driver.quit()

    if not raw.get("partselect_number"):
        raw["partselect_number"] = ps

    parts_path = io_utils.PARTS_OUT
    lines: list[dict] = []
    replaced = False
    if parts_path.exists():
        for row in io_utils.iter_jsonl(parts_path):
            if (row.get("partselect_number") or "").upper() == ps:
                lines.append(raw)
                replaced = True
            else:
                lines.append(row)
    if not replaced:
        lines.append(raw)

    with parts_path.open("w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    shaped = reshape_part(raw)
    engine = get_engine()
    with engine.begin() as conn:
        _insert_part(conn, shaped)

    return {
        "ps_number": ps,
        "installation_steps": len(raw.get("installation_steps") or []),
        "has_description": bool(raw.get("description")),
        "video_url": raw.get("video_url"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-scrape one PS part into JSONL + DB")
    parser.add_argument("ps_number", help="e.g. PS11752778")
    parser.add_argument("--no-headless", dest="headless", action="store_false", default=True)
    args = parser.parse_args(argv)
    os.environ.setdefault("DB_HOST", "localhost")
    print(json.dumps(patch_part(args.ps_number, headless=args.headless), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
