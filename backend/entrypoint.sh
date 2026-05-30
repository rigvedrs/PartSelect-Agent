#!/usr/bin/env bash
set -e

echo "Waiting for Postgres..."
until pg_isready -h "${DB_HOST:-postgres}" -p 5432 -U "${DB_USER:-partselect}" >/dev/null 2>&1; do
  sleep 1
done
echo "Postgres ready. Running ingestion..."
python -m app.rag.ingest
echo "Ingestion done. Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
