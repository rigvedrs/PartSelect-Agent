# Raw catalog data

Bundled JSONL for local demo and Docker Compose quickstart (curated scrape, not the old `_backup/` full crawl):

| File | Purpose |
|------|---------|
| `parts.jsonl` | Parts catalog with embeddings source fields |
| `repairs.jsonl` | Repair guides |
| `articles.jsonl` | Blog / article content |

On first `docker compose up`, the backend entrypoint ingests these into Postgres/pgvector (~60s). Set `FORCE_REINGEST=1` to reload after you replace the files.

To refresh from a new scrape:

```bash
PYTHONPATH=backend python -m scrapers.run_collection --stage seed-curated
PYTHONPATH=backend python -m scrapers.run_collection --stage details --limit 100
PYTHONPATH=backend python -m scrapers.run_collection --stage refresh-db
docker compose restart backend
```

Intermediate scrape checkpoints live under `backend/data/scrape_work/` (gitignored). Exports overwrite the JSONL files here; use `--backup` on export to copy previous files into `_backup/` (also gitignored).
