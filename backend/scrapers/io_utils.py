"""JSON/JSONL helpers and scrape workspace paths."""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any, Iterable, Iterator

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = BACKEND_ROOT / "data" / "raw"
BACKUP_DIR = RAW_DIR / "_backup"
WORK_DIR = BACKEND_ROOT / "data" / "scrape_work"

PARTS_OUT = RAW_DIR / "parts.jsonl"
REPAIRS_OUT = RAW_DIR / "repairs.jsonl"
ARTICLES_OUT = RAW_DIR / "articles.jsonl"

CATALOG_DIR = WORK_DIR / "catalog"
BRANDS_FILE = CATALOG_DIR / "brands.json"
SUBCATS_FILE = CATALOG_DIR / "subcategories.json"
PRODUCT_LINKS = CATALOG_DIR / "product_links.jsonl"
SUBCAT_CHECKPOINT = CATALOG_DIR / "subcat_done.txt"

DETAILS_DIR = WORK_DIR / "details"
DETAILS_JSONL = DETAILS_DIR / "product_details.jsonl"
DETAILS_CHECKPOINT = DETAILS_DIR / "urls_done.txt"
DETAILS_FAILED = DETAILS_DIR / "urls_failed.txt"

ENRICH_DIR = WORK_DIR / "enrich"
ENRICHED_JSONL = ENRICH_DIR / "enriched_parts.jsonl"

REPAIR_WORK = WORK_DIR / "repairs"
ARTICLE_WORK = WORK_DIR / "articles"
ARTICLE_LINKS_CSV = ARTICLE_WORK / "filtered_links.csv"


def ensure_dirs() -> None:
    for d in (RAW_DIR, BACKUP_DIR, WORK_DIR, CATALOG_DIR, DETAILS_DIR, ENRICH_DIR, REPAIR_WORK, ARTICLE_WORK):
        d.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}


def mark_checkpoint(path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(key.strip() + "\n")


def urls_from_jsonl(path: Path, field: str = "product_url") -> set[str]:
    return {(r.get(field) or "").strip() for r in iter_jsonl(path) if (r.get(field) or "").strip()}


def dedupe_jsonl_by_url(in_path: Path, out_path: Path, url_field: str = "product_url") -> int:
    seen: set[str] = set()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as out:
        for row in iter_jsonl(in_path):
            url = (row.get(url_field) or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def backup_raw_files() -> None:
    ensure_dirs()
    for name in ("parts.jsonl", "repairs.jsonl", "articles.jsonl"):
        src = RAW_DIR / name
        if src.exists():
            shutil.copy2(src, BACKUP_DIR / name)


def sample_ps_numbers(parts_path: Path, n: int, seed: int = 42) -> list[str]:
    nums = []
    for row in iter_jsonl(parts_path):
        ps = row.get("partselect_number")
        if ps:
            nums.append(ps)
    rng = random.Random(seed)
    if len(nums) <= n:
        return nums
    return rng.sample(nums, n)


def merge_jsonl_files(paths: Iterable[Path], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open("w", encoding="utf-8") as out:
        for p in paths:
            for row in iter_jsonl(p):
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                total += 1
    return total
