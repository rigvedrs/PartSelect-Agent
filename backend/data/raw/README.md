# Raw catalog data (local only)

JSONL files in this directory are **gitignored** — they are produced by the scrape pipeline or copied from your own exports.

Required for first-time ingest:

- `parts.jsonl`
- `repairs.jsonl`
- `articles.jsonl`

Quickstart without a full 6k scrape:

```bash
PYTHONPATH=backend python -m scrapers.run_collection --stage seed-curated
PYTHONPATH=backend python -m scrapers.run_collection --stage details --limit 100
PYTHONPATH=backend python -m scrapers.run_collection --stage refresh-db
```

Or copy pre-built JSONL files here before running `docker compose up` or `python -m app.rag.ingest`.
