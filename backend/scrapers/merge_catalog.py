"""Merge fresh scrape layers into parts.jsonl without losing compatibility cross-refs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from scrapers import io_utils

_PRESERVE_IF_EMPTY = (
    "model_cross_reference",
    "main_image",
    "installation_complexity",
    "installation_time",
    "video_url",
)


def _ps_key(row: dict) -> str | None:
    ps = (row.get("partselect_number") or row.get("ps_number") or "").strip().upper()
    return ps or None


def _merge_row(existing: dict, fresh: dict) -> dict:
    merged = dict(existing)
    for key, val in fresh.items():
        if val is None or val == "" or val == []:
            continue
        merged[key] = val
    for key in _PRESERVE_IF_EMPTY:
        if not merged.get(key) and existing.get(key):
            merged[key] = existing[key]
    return merged


def merge_parts_catalog(
    *,
    base_path: Path | None = None,
    fresh_paths: list[Path] | None = None,
    out_path: Path | None = None,
    backup: bool = True,
) -> dict[str, int]:
    """Overlay fresh detail/enrich records onto the baseline catalog by PS number."""
    io_utils.ensure_dirs()
    base_path = base_path or io_utils.PARTS_OUT
    out_path = out_path or io_utils.PARTS_OUT
    fresh_paths = fresh_paths or [
        p for p in (io_utils.ENRICHED_JSONL, io_utils.DETAILS_JSONL) if p.exists()
    ]

    by_ps: dict[str, dict] = {}
    if base_path.exists():
        for row in io_utils.iter_jsonl(base_path):
            ps = _ps_key(row)
            if ps:
                by_ps[ps] = row

    baseline = len(by_ps)
    updated = 0
    added = 0

    for fresh_path in fresh_paths:
        for row in io_utils.iter_jsonl(fresh_path):
            ps = _ps_key(row)
            if not ps:
                continue
            if ps in by_ps:
                by_ps[ps] = _merge_row(by_ps[ps], row)
                updated += 1
            else:
                by_ps[ps] = row
                added += 1

    if backup and out_path.exists() and out_path == io_utils.PARTS_OUT:
        io_utils.backup_raw_files()

    tmp = out_path.with_suffix(".merged.jsonl")
    with tmp.open("w", encoding="utf-8") as out:
        for row in by_ps.values():
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    shutil.move(str(tmp), str(out_path))

    return {
        "baseline_parts": baseline,
        "updated_from_fresh": updated,
        "added_from_fresh": added,
        "total_parts": len(by_ps),
        "fresh_sources": [str(p) for p in fresh_paths],
        "output": str(out_path),
    }


def run_refresh_db(*, merge: bool = True, force_reingest: bool = True) -> dict:
    """Merge scrape work into parts.jsonl and reload Postgres."""
    import os

    result: dict = {}
    if merge:
        result["merge"] = merge_parts_catalog(backup=True)

    if force_reingest:
        os.environ["FORCE_REINGEST"] = "1"
    from app.rag.ingest import run_ingestion

    result["ingest"] = run_ingestion()
    return result


if __name__ == "__main__":
    import sys

    stats = run_refresh_db(merge="--no-merge" not in sys.argv)
    print(json.dumps(stats, indent=2))
