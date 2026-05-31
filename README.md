# PartSelect AI Chat Agent

A conversational AI agent for PartSelect's e-commerce platform, specializing in **Refrigerator and Dishwasher parts**. The agent helps customers find parts, check appliance compatibility, get installation instructions, troubleshoot issues, and add parts to their cart.

---

## Architecture

```
User ──► React Chat Widget (port 3000)
              │
              ▼
        FastAPI POST /api/chat (port 8000)
              │
      ┌───────▼────────┐
      │  Scope guardrail│  keyword check — rejects clearly off-topic queries
      └───────┬─────────┘
              │
      ┌───────▼────────────────────────┐
      │  LLM intent classifier       │  deepseek-v4-flash, structured output
      │  (single call per message)   │
      └───────┬────────────────────────┘
              │
     ┌────────┴────────────────────────────────────────────┐
     │ Deterministic handlers (no LangGraph)                 │
     │  INSTALL · COMPAT · SEARCH · PARTS_FOR_MODEL        │
     │  ADD/REMOVE_CART · GREETING · TROUBLESHOOT            │
     └────────┬────────────────────────────────────────────┘
              │
     ┌────────┴──────────┬──────────────────────┐
     ▼                   ▼                      ▼
 SQL / Firecrawl    RAG + synthesis LLM    LangGraph ReAct
 tools              (troubleshoot only)    (GENERAL intent only)
     │                   │                      │
     │              pgvector retrieval          │ deepseek-v4-pro
     │              repair_guides + articles    │ search · compat · install
     └───────────────────┴──────────────────────┘
```

**Data:** PostgreSQL 16 + pgvector HNSW index for semantic search. Embeddings generated locally via `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions). Parts, compatibility, repair guides, and articles are ingested from JSONL under `backend/data/raw/`.

**Live fallback:** When a PS number or model page is not in the database, tools use **Selenium + Chrome** (free, default) to scrape PartSelect and return results in the same request. Optional: set `LIVE_SCRAPE_BACKEND=firecrawl` + `FIRECRAWL_API_KEY` for a paid API path that avoids spinning up a browser per request.

---

## Request flow

Every chat message goes through the same pipeline:

1. **Scope check** — reject only when the message has zero appliance keywords *and* contains a known off-of-scope keyword.
2. **Intent classification** — one structured LLM call (`deepseek/deepseek-v4-flash`) returns intent, optional `part_query`, and optional `ps_number`.
3. **Cart intent reconciliation** — verb-based override (`add` / `remove`) corrects misclassified cart intents.
4. **PS resolution** — for cart actions, resolve the target part in priority order: explicit PS in message → pronoun reference to **latest** shown batch → name match in session history → classifier PS.
5. **Handler** — run the matching deterministic handler or, for `general` only, stream through the LangGraph agent.

Handlers record exchanges in `session_messages` and update `last_parts_json` whenever parts are returned, so follow-up turns ("add it", "remove that filter") stay grounded in what the user actually saw.

---

## Intent routing

| Intent | Handler | LLM used? |
|--------|---------|-----------|
| `greeting` | Static welcome | No |
| `search` | Model-first `list_compatible_parts` or PS lookup | No |
| `parts_for_model` | Compatible parts for session model | No |
| `compatibility` | `check_compatibility` or model-scoped search | No |
| `install` | `get_installation_guide` | No |
| `troubleshoot` | RAG retrieval + pro synthesis + resource footer | Yes (synthesis only) |
| `add_to_cart` / `remove_from_cart` | Cart tools + session PS resolution | No |
| `general` | LangGraph ReAct agent (no cart tools) | Yes (pro) |

**Pending slots:** If the user searches for a part type without a model number, the session stores `pending_intent` + `pending_part_query`. The next message that includes a model clears the slot and completes the search.

**Intent–tool guardrails:** Each intent maps to an allowed tool set (`guardrails.py`). Handlers call `assert_tool_allowed()` before cart mutations. The LangGraph agent does not expose cart tools — cart changes always go through the deterministic router.

---

## Session state

Stored per session in PostgreSQL:

| Field | Purpose |
|-------|---------|
| `appliance_model` | Persisted model number from chat or the UI field |
| `pending_intent` / `pending_part_query` | Multi-turn search when model was missing |
| `last_parts_json` | `{ "latest": [...], "history": [...] }` — parts shown to the user |

- **`latest`** — most recent batch of parts (used for "add it" / "that one").
- **`history`** — rolling window (max 20) for name-based cart resolution ("add the water filter").

---

## Troubleshooting (RAG)

`Intent.TROUBLESHOOT` does **not** use the LangGraph agent. Instead:

1. Detect appliance type from the message (`dishwasher` vs `refrigerator`).
2. Embed the symptom and retrieve top repair guides + articles via pgvector (`app/agent/tools/troubleshoot.py`).
3. Synthesize a concise answer with `deepseek/deepseek-v4-pro` using only retrieved context (`app/agent/troubleshoot_handler.py`).
4. Append the PartSelect resource footer (Repair hub + Instant Repairman links).

Related parts from repair-guide matches are returned in the `parts` field when found in the catalog.

---

## LLM configuration

Two models, configured in `config.toml`:

| Role | Model | Used for |
|------|-------|----------|
| Classifier (`tool_model`) | `deepseek/deepseek-v4-flash` | Intent routing, structured output, `temperature=0` |
| Synthesis (`synthesis_model`) | `deepseek/deepseek-v4-pro` | Troubleshoot answers, LangGraph agent |

Switch providers by changing `base_url`, `api_key_env_var`, and model slugs — no code changes required.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — required for Postgres + Redis
- **OpenRouter API key** — required for intent classification, troubleshoot synthesis, and `general` agent turns. Get one at [openrouter.ai](https://openrouter.ai)
- **Google Chrome** — required for live runtime scraping (Selenium) and the bulk scrape pipeline
- **Firecrawl API key** — optional; set `LIVE_SCRAPE_BACKEND=firecrawl` for paid API scraping instead of local Chrome
- For local dev without Docker: Python 3.11 via conda, Node.js 22.12.0 via [asdf](https://asdf-vm.com)
- For bulk scraping: Google Chrome (Selenium + `webdriver-manager`)

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

The first startup downloads the embedding model (~90 MB) and ingests JSONL data — takes about 60 seconds. Subsequent starts are instant unless `FORCE_REINGEST=1` is set.

---

## Example queries

| # | Query | How it's handled |
|---|-------|-----------------|
| 1 | `How can I install part number PS11752778?` | Deterministic SQL → installation steps (no LangGraph) |
| 2 | `Is PS11752778 compatible with my WDT780SAEM1 model?` | Deterministic SQL → compatibility result |
| 3 | `My ice maker is not working` | RAG over repair guides + articles → pro synthesis → resource footer |
| 4 | `find a water filter for my fridge` then `add it` | Model-first search → session `latest` → contextual cart add |

Queries 1–2 work without an API key for the data layer; intent classification and query 3+ require `OPENROUTER_API_KEY`.

---

## Local development

### Backend

```bash
conda create -n instalily python=3.11 -y
conda activate instalily
pip install -r backend/requirements.txt

docker compose up -d postgres redis

# First-time ingest (from repo root; JSONL must exist under backend/data/raw/)
DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  python -m app.rag.ingest

uvicorn app.main:app --reload --port 8000
# Run from backend/ with DB_HOST=localhost in the environment, or use docker compose backend service
```

When running ingest or pytest **on the host** (not inside Docker), always set `DB_HOST=localhost`. Inside containers, `config.toml` defaults to `DB_HOST=postgres`.

### Scraping pipeline (Selenium)

Requires Google Chrome and network access. Installs matching ChromeDriver via `webdriver-manager`.

```bash
conda activate instalily
cd partselect-agent

# Full pipeline: catalog → product details → enrich → repairs → articles → export
PYTHONPATH=backend python -m scrapers.run_collection --stage all --backup

# Individual stages
PYTHONPATH=backend python -m scrapers.run_collection --stage repairs
PYTHONPATH=backend python -m scrapers.run_collection --stage articles
PYTHONPATH=backend python -m scrapers.run_collection --stage catalog
PYTHONPATH=backend python -m scrapers.run_collection --stage details --limit 100   # smoke test
PYTHONPATH=backend python -m scrapers.run_collection --stage enrich
PYTHONPATH=backend python -m scrapers.run_collection --stage export

# Verify scraped samples against existing JSONL baselines
PYTHONPATH=backend python -m scrapers.verify_output --samples 10

# Audit cross-reference completeness (detects legacy 30-row truncation)
PYTHONPATH=backend python -m scrapers.verify_output --audit
```

**Stages:**

| Stage | Module | Output |
|-------|--------|--------|
| `catalog` | `catalog_crawler.py` | Product URLs by category |
| `details` | `detail_extractor.py` | Per-product JSONL (price, name, symptoms) |
| `enrich` | `compat_enricher.py` | Model cross-references (clicks "Load more", no 30-row cap) |
| `repairs` | `repair_guides.py` | Symptom → part repair rows |
| `articles` | `article_collector.py` | Blog / how-to articles |
| `export` | `run_collection.py` | Copies work files → `backend/data/raw/*.jsonl` |

Intermediate files live under `backend/data/scrape_work/` (gitignored). Final exports overwrite `backend/data/raw/{parts,repairs,articles}.jsonl` (previous files copied to `backend/data/raw/_backup/` when using `--backup`).

**Shared price parsing:** `scrapers/product_utils.py` (`parse_product_price`, `clean_product_url`) is used by the bulk pipeline and runtime enrichment so chat/cart prices match PartSelect product pages.

Re-ingest after a fresh scrape (or merge partial scrape work):

```bash
# Recommended: merge scrape_work + reload Postgres (~30s)
DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  python -m scrapers.run_collection --stage refresh-db
```

**Incremental workflow** — full Selenium scrape of 6k+ URLs takes hours. Run in batches:

```bash
# Resume details (checkpoints skip done URLs; skip video by default for speed)
PYTHONPATH=backend python -m scrapers.run_collection --stage details --limit 200

# Optional: add model cross-refs (slow — clicks "Load more" per product)
PYTHONPATH=backend python -m scrapers.run_collection --stage enrich --limit 50

# Merge fresh data into parts.jsonl + re-ingest
DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  python -m scrapers.run_collection --stage refresh-db
```

`merge` overlays `scrape_work/details/` and `scrape_work/enrich/` onto `parts.jsonl` by PS number and **keeps existing `model_cross_reference`** when fresh rows lack it.

Manual ingest only:

```bash
FORCE_REINGEST=1 DB_HOST=localhost POSTGRES_PASSWORD=partselect PYTHONPATH=backend \
  python -m app.rag.ingest
```

Runtime live scrape (`scrapers/runtime_fetch.py`, `parts_scraper.py`) uses Selenium by default; Firecrawl is opt-in via env.

### Frontend

```bash
cd frontend
asdf shell nodejs 22.12.0
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

---

## Observability

```bash
docker compose logs -f backend
```

Each log line includes `req=<id>` for end-to-end tracing:

| Logger | What it reports |
|--------|----------------|
| `routers.chat` | Intent, model source, handler path |
| `agent.router` | Classification result |
| `agent.troubleshoot` | RAG hit counts (causes, articles, parts) |
| `agent.graph` | Empty-text warnings, LLM/tool exceptions |
| `tools.list_compatible_parts` | DB hits, live-scrape fallback |
| `scrapers.model_lookup` | Model page scrape outcomes |

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output.

---

## Running tests

```bash
conda activate instalily
cd partselect-agent

# Unit tests (no DB / no API key for most)
PYTHONPATH=backend pytest backend/tests/ \
  --ignore=backend/tests/test_ingest_integration.py \
  --ignore=backend/tests/test_api_integration.py \
  --ignore=backend/tests/test_chat_scenarios.py -v

# API integration + scenarios (requires Postgres)
docker compose up -d postgres
DB_HOST=localhost POSTGRES_PASSWORD=partselect OPENROUTER_API_KEY=<key> \
  PYTHONPATH=backend pytest backend/tests/test_api_integration.py \
  backend/tests/test_chat_scenarios.py -v
```

Router live tests and some scenario cases require `OPENROUTER_API_KEY`.

---

## API reference

### `POST /api/chat`

```json
{
  "session_id": "uuid",
  "message": "string",
  "appliance_model": "WDT780SAEM1",
  "stream": true
}
```

| Field | Present when |
|-------|-------------|
| `text` | Always |
| `parts` | Search / troubleshoot / install |
| `installation_steps` | Install intent |
| `compatibility` | Compatibility check |
| `cart_update` | Cart add/remove |
| `source` | `"db"` or `"live"` when parts came from scrape fallback |
| `out_of_scope` | Guardrail rejection |

### Other endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{"ok": true}` |
| `POST` | `/api/session` | Create session |
| `GET` | `/api/cart/{session_id}` | Cart items + total |
| `DELETE` | `/api/cart/{session_id}/item/{ps_number}` | Remove item |

---

## Project structure

```
partselect-agent/
├── config.toml                 # LLM, DB, retrieval, scope
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── router.py           # LLM intent classifier
│   │   │   ├── guardrails.py       # Scope + intent–tool map
│   │   │   ├── part_context.py     # Session PS / name resolution
│   │   │   ├── troubleshoot_handler.py  # RAG + synthesis + footer
│   │   │   ├── llm_provider.py     # flash classifier + pro synthesis
│   │   │   ├── graph.py            # LangGraph (GENERAL only)
│   │   │   ├── messages.py         # Shared user-facing templates
│   │   │   └── tools/              # search, compat, install, troubleshoot, cart
│   │   ├── routers/chat.py         # Intent → handler dispatch
│   │   ├── services/               # session, cart, chat history
│   │   └── rag/                    # embedder + ingest
│   ├── scrapers/                   # Selenium pipeline + Firecrawl runtime
│   │   ├── run_collection.py       # Stage orchestrator CLI
│   │   └── product_utils.py        # Shared URL/price parsing
│   └── tests/
└── frontend/
```

---

## Configuration (`config.toml`)

```toml
[llm]
tool_model = "deepseek/deepseek-v4-flash"      # intent classifier
synthesis_model = "deepseek/deepseek-v4-pro"   # troubleshoot + agent
tool_temperature = 0.0
synthesis_temperature = 0.3

[retrieval]
top_k = 7
```

---

## Design decisions

**Deterministic-first routing:** Install, compatibility, search, parts-for-model, cart, and troubleshoot use direct handlers. Only ambiguous multi-step requests hit LangGraph. Demo-critical paths (install PS11752778, compatibility checks) do not depend on agent tool-choice.

**Dual-model split:** Flash model for fast, cheap structured classification; pro model for natural-language synthesis where quality matters.

**Session-grounded cart:** Pronoun cart requests bind to the **latest** part batch, not the classifier's stale PS field. Name-based requests search rolling history.

**RAG troubleshoot with guardrails:** Retrieved repair guides and articles constrain the synthesis prompt; a fixed footer always points users to PartSelect Repair and Instant Repairman.

**Hybrid data + live enrichment:** JSONL bulk ingest plus Firecrawl/Selenium refresh for missing or stale prices. `part_enrichment.py` validates parts, refreshes prices from product URLs, and filters "Page Not Found" junk.

**pgvector HNSW:** 384-dim MiniLM embeddings; cosine search over `repair` and `article` sources in the `embeddings` table.

---

## Next phases (suggested)

- Complete bulk scrape (`details` + `enrich`) and re-ingest for full catalog coverage
- Expand scenario tests for contextual cart and troubleshoot RAG quality
- Optional: stream troubleshoot responses; cache retrieval results in Redis (`retrieval_ttl_seconds`)
- Frontend: surface `source: live` badge and troubleshoot-related parts more prominently
