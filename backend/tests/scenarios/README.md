# Chat scenario tests

Exhaustive API scenarios live in `chat_scenarios.json`. Run against Docker Postgres:

```bash
export TEST_DATABASE_URL=postgresql+psycopg://partselect:partselect@localhost:5432/partselect
export DB_HOST=localhost
export POSTGRES_PASSWORD=partselect

PYTHONPATH=backend pytest backend/tests/test_chat_scenarios.py -v
```

Add new scenarios to the JSON file; each entry supports:

- `message` — single turn
- `sequence` — multi-turn in one session
- `expect` — assertions (parts, compatibility, cart, out_of_scope, etc.)
- `requires_llm` — skips without `OPENROUTER_API_KEY`
