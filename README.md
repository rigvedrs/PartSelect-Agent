# PartSelect AI Chat Agent

A conversational AI agent for PartSelect's e-commerce platform, specializing in **Refrigerator and Dishwasher parts**. The agent helps customers find parts, check appliance compatibility, get installation instructions, troubleshoot issues, and add parts to their cart.

---

## Architecture

```
User ──► React Chat Widget (port 3000)
              │
              ▼
        FastAPI /api/chat (port 8000)
              │
      ┌───────▼────────┐
      │  Scope Guardrail│  keyword check — rejects off-topic
      └───────┬─────────┘
              │
      ┌───────▼────────┐
      │  Intent Router  │  INSTALL/COMPAT/SEARCH/CART → direct SQL
      └───────┬─────────┘  TROUBLESHOOT/COMPLEX → LangGraph agent
              │
     ┌────────┴──────────┐
     │                   │
     ▼                   ▼
Direct Tool Response  LangGraph ReAct Agent
(no LLM needed)       (DeepSeek via OpenRouter)
                           │
                      5 Tools:
                      ├── search_parts        (SQL + Firecrawl fallback)
                      ├── check_compatibility  (deterministic SQL)
                      ├── get_installation    (SQL)
                      ├── troubleshoot_symptom (pgvector semantic search)
                      └── add_to_cart         (SQL)
```

**Data:** PostgreSQL 16 + pgvector HNSW index for semantic search. Embeddings generated locally via `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions). ~2,100 refrigerator/dishwasher parts pre-ingested from JSONL.

**Phase 2 fallback:** When a PS number is not in the database, `search_parts` triggers a live Firecrawl scrape, ingests the result on-the-fly, and returns it — all within the same request (requires `FIRECRAWL_API_KEY`).

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — required for Postgres + Redis
- **OpenRouter API key** — required for LLM responses (troubleshoot / complex queries). Get one at [openrouter.ai](https://openrouter.ai)
- **Firecrawl API key** — optional, enables live scraping for unknown PS numbers. Get one at [firecrawl.dev](https://firecrawl.dev)
- For local dev without Docker: Python 3.11 via conda, Node.js 22.12.0 via [asdf](https://asdf-vm.com)

---

## Quickstart (Docker Compose)

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd partselect-agent

# 2. Set environment variables
cp .env.example .env
# Edit .env — set OPENROUTER_API_KEY at minimum

# 3. Start everything
docker compose up -d

# 4. Wait ~60s for data ingestion, then open:
open http://localhost:3000
```

The first startup downloads the embedding model (~90 MB) and ingests ~2,100 parts — takes about 60 seconds. Subsequent starts are instant.

---

## Example Queries

These three queries are guaranteed to work and demonstrate the full agent:

| # | Query | How it's handled |
|---|-------|-----------------|
| 1 | `How can I install part number PS11752778?` | Deterministic SQL → numbered installation steps (no LLM) |
| 2 | `Is PS11752778 compatible with my WDT780SAEM1 model?` | Deterministic SQL → compatibility badge (no LLM) |
| 3 | `My ice maker is not working` | LangGraph agent → pgvector search → part recommendations |

Queries 1 and 2 do not require an API key. Query 3 requires `OPENROUTER_API_KEY`.

---

## Local Development

### Backend

```bash
# Create and activate conda env
conda create -n instalily python=3.11 -y
conda activate instalily
pip install -r backend/requirements.txt

# Start infrastructure
docker compose up -d postgres redis

# Run ingestion (first time only)
DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  python -m app.rag.ingest

# Start API server
DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  uvicorn app.main:app --reload --port 8000
```

### Scraping pipeline (Selenium)

Requires Google Chrome and network access. Installs matching ChromeDriver via `webdriver-manager`.

```bash
conda activate instalily
pip install -r backend/requirements.txt

# Full pipeline: catalog → product details → enrich → repairs → articles → export
cd partselect-agent
PYTHONPATH=backend python -m scrapers.run_collection --stage all --backup

# Individual stages
PYTHONPATH=backend python -m scrapers.run_collection --stage repairs
PYTHONPATH=backend python -m scrapers.run_collection --stage articles
PYTHONPATH=backend python -m scrapers.run_collection --stage catalog
PYTHONPATH=backend python -m scrapers.run_collection --stage details --limit 100  # smoke test
PYTHONPATH=backend python -m scrapers.run_collection --stage enrich
PYTHONPATH=backend python -m scrapers.run_collection --stage export

# Verify scraped samples against existing JSONL baselines
PYTHONPATH=backend python -m scrapers.verify_output --samples 10

# Audit cross-reference completeness (checks for legacy 30-row truncation)
PYTHONPATH=backend python -m scrapers.verify_output --audit
# Exits 0 if max cross-ref count > 30 (cap removed); exits 1 if still truncated
```

**Data completeness note:** The original baseline `parts.jsonl` caps `model_cross_reference` at exactly 30 rows per part (1,551 parts hit this ceiling). The new Selenium `compat_enricher` clicks "Load more" until exhausted — no cap — so a full fresh scrape will produce complete compatibility lists. Run `--audit` to verify completeness after a scrape.

Intermediate files live under `backend/data/scrape_work/`. Final exports overwrite `backend/data/raw/{parts,repairs,articles}.jsonl` (previous files copied to `backend/data/raw/_backup/` when using `--backup`).

Re-ingest after a fresh scrape:

```bash
FORCE_REINGEST=1 DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  python -m app.rag.ingest
```

Docker: set `FORCE_REINGEST=1` in `.env` before `docker compose up` to reload JSONL on startup.

Runtime Firecrawl fallback (`scrapers.parts_scraper.scrape_and_parse`) is unchanged and independent of this pipeline.

### Frontend

```bash
cd frontend
asdf shell nodejs 22.12.0
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
# Opens at http://localhost:3000
```

---

## Observability

The backend logs one structured line per request stage to stdout, visible via:

```bash
docker compose logs -f backend
```

Each log line includes a short `req=<id>` prefix so you can trace a single request end-to-end. Key log events:

| Logger | What it reports |
|--------|----------------|
| `routers.chat` | Intent classified, model source (message / session / pending slot), handler invoked |
| `tools.list_compatible_parts` | DB hit count, live-scrape fallback trigger + part count |
| `tools.check_compatibility` | Live-confirmed compat (with `ps=` and `model=`) |
| `scrapers.model_lookup` | Model page scrape outcome, PS numbers found |
| `agent.graph` | Empty-text warning, full exception traceback on LLM/tool failure |

**Log level:** Set `LOG_LEVEL=DEBUG` in `.env` for verbose output; default is `INFO`.

**Fallback chain decisions** — when local DB returns nothing, the agent tries a live Firecrawl scrape and tags the result `source: "live"` in the response. On failure it returns a graceful referral URL. Both decisions are logged so you can see exactly why a fallback fired.

---

## Running Tests

```bash
conda activate instalily
cd partselect-agent

# Unit tests (no DB required — 40+ tests)
PYTHONPATH=backend pytest backend/tests/ \
  --ignore=backend/tests/test_ingest_integration.py \
  --ignore=backend/tests/test_api_integration.py -v

# API integration tests (requires running Postgres via docker compose up -d postgres)
TEST_DATABASE_URL=postgresql+psycopg://partselect:partselect@localhost:5432/partselect \
  DB_HOST=localhost POSTGRES_PASSWORD=partselect \
  PYTHONPATH=backend pytest backend/tests/ -v
```

---

## API Reference

### `POST /api/chat`

```json
{
  "session_id": "uuid",          // omit to auto-create
  "message": "string",
  "appliance_model": "WDT780SAEM1",  // optional, persisted in session
  "stream": false
}
```

Response fields vary by intent:

| Field | Present when |
|-------|-------------|
| `text` | Always |
| `parts` | Search results available |
| `installation_steps` | Install intent |
| `compatibility` | Compatibility check |
| `cart_update` | Item added to cart |
| `out_of_scope` | Query rejected by guardrail |

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check → `{"ok": true}` |
| `POST` | `/api/session` | Create session → `{"session_id": "uuid"}` |
| `GET` | `/api/cart/{session_id}` | Get cart → `{items, total, count}` |
| `DELETE` | `/api/cart/{session_id}/item/{ps_number}` | Remove item |

---

## Project Structure

```
partselect-agent/
├── config.toml              # All settings (LLM, DB, Redis, retrieval, scope)
├── .env.example             # Environment variable template
├── docker-compose.yml       # postgres + redis + backend + frontend
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── entrypoint.sh        # wait-for-db → ingest → uvicorn
│   ├── data/raw/            # JSONL source data (gitignored)
│   └── app/
│       ├── main.py          # FastAPI app + CORS
│       ├── config.py        # Pydantic settings (config.toml + env vars)
│       ├── db/
│       │   ├── schema.sql   # PostgreSQL DDL (pgvector + HNSW index)
│       │   └── engine.py
│       ├── rag/
│       │   ├── embedder.py  # sentence-transformers wrapper
│       │   └── ingest.py    # JSONL → Postgres pipeline
│       ├── agent/
│       │   ├── guardrails.py
│       │   ├── router.py    # Deterministic intent classifier
│       │   ├── llm_provider.py
│       │   ├── graph.py     # LangGraph ReAct agent
│       │   ├── state.py
│       │   └── tools/       # search_parts, check_compat, install, troubleshoot, cart
│       ├── services/        # session_service, cart_service
│       └── routers/         # chat, cart, session
└── frontend/
    ├── .tool-versions       # nodejs 22.12.0
    ├── Dockerfile
    └── src/
        ├── lib/api.js
        ├── hooks/           # useSession, useCart, useChat
        └── components/      # ChatWidget, ProductCard, InstallationGuide,
                             # CompatibilityBadge, CartDrawer, + 8 more
```

---

## Configuration

All tunable settings live in `config.toml`. Key sections:

```toml
[llm]
provider = "openrouter"
base_url = "https://openrouter.ai/api/v1"
api_key_env_var = "OPENROUTER_API_KEY"
tool_model = "deepseek/deepseek-chat"
synthesis_model = "deepseek/deepseek-chat"

[retrieval]
top_k = 5

[scope]
appliance_keywords = ["refrigerator", "dishwasher", ...]
out_of_scope_keywords = ["recipe", "weather", ...]
```

Switch LLM providers by changing `base_url`, `api_key_env_var`, and model slugs — no code changes needed.

---

## Design Decisions

**Deterministic-first routing:** Install, compatibility, search, and cart queries bypass the LLM entirely — they use SQL lookups with sub-millisecond response times. Only troubleshoot and complex multi-step queries invoke the LangGraph agent. This makes the three demo queries bulletproof regardless of LLM availability.

**Hybrid data strategy:** ~2,100 parts ingested from JSONL. Critical parts (PS11752778) are hardcoded as seeds so demo queries always work even on a fresh database. Firecrawl provides live fallback for any PS number not yet ingested.

**pgvector HNSW index:** Semantic similarity search for troubleshooting uses 384-dimension MiniLM embeddings with an HNSW index (m=16, ef_construction=64) — cosine similarity in <1 ms at this dataset size.

**Provider-agnostic LLM:** All model slugs, base URLs, and temperatures are in `config.toml`. Switching from DeepSeek to any OpenAI-compatible API requires only a config change.

**Session + cart persistence:** Sessions and carts are stored in PostgreSQL (not Redis) for durability. The frontend stores `session_id` in `localStorage`, so the cart survives page refreshes. The appliance model number is also persisted per session and automatically used in subsequent compatibility checks.
