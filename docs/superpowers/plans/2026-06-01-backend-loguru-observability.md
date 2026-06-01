# Backend Loguru Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable Loguru-backed backend logs that make chat requests, model usage, intent routing, agent invocation, tool calls, source selection, stages, timings, and errors easy to follow.

**Architecture:** Preserve `app.observability` as the logging boundary and replace its internals with a Loguru configuration plus safe event helpers. Add targeted `log_event(...)` calls at chat, classifier, agent, catalog/live, and deterministic tool boundaries without changing user-facing behavior.

**Tech Stack:** Python 3.11, FastAPI, Loguru, pytest, existing conda `instalily` backend environment.

---

## File Structure

- Modify: `backend/requirements.txt`  
  Add the `loguru` dependency.

- Modify: `backend/app/observability.py`  
  Configure Loguru, preserve existing request trace/span APIs, add `log_event`, `safe_preview`, `sanitize_fields`, and logging settings helpers.

- Modify: `backend/tests/test_observability.py`  
  Add tests for settings, redaction, truncation, event formatting, and preserve existing span/summary tests.

- Modify: `backend/app/routers/chat.py`  
  Add lifecycle logs for request start, model resolution, branch selection, SSE stages, token streams, deterministic final responses, and errors.

- Modify: `backend/app/agent/router.py`  
  Log classifier start/end/fallback with configured tool model.

- Modify: `backend/app/agent/graph.py`  
  Log synthesis model use, agent invocation, graph tool transitions, stream completion, and fallback/error paths.

- Modify: `backend/app/agent/catalog.py`  
  Log compatible-parts resolver start/done/source decisions.

- Modify: `backend/app/live_scrape/gateway.py`  
  Log live scrape tool start/done/error for part/model/install/compat calls.

- Modify: `backend/app/agent/tools/search_parts.py`  
  Log search start/done/source/count.

- Modify: `backend/app/agent/tools/check_compatibility.py`  
  Log compatibility start/done/source/result.

- Modify: `backend/app/agent/tools/list_compatible_parts.py`  
  Log wrapper start/done with inferred scope and count.

- Modify: `backend/app/agent/tools/get_installation.py`  
  Log installation lookup start/done/source/found.

- Modify: `backend/app/agent/tools/add_to_cart.py`  
  Log add-to-cart start/done without full cart payload.

- Modify: `backend/app/agent/tools/remove_from_cart.py`  
  Log remove-from-cart start/done without full cart payload.

- Modify: `backend/app/agent/troubleshoot_handler.py`  
  Log troubleshooting prep, retrieval count, synthesis stream start/done/error.

---

### Task 1: Add Loguru Dependency and Observability Helpers

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/test_observability.py`
- Modify: `backend/app/observability.py`

- [ ] **Step 1: Write failing observability tests**

Extend `backend/tests/test_observability.py` with these tests:

```python
import logging

from app.observability import (
    RequestTrace,
    get_log_settings,
    log_event,
    new_request_id,
    safe_preview,
    sanitize_fields,
    span,
    trace_request,
)


def test_log_settings_defaults(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    monkeypatch.delenv("LOG_COLOR", raising=False)
    settings = get_log_settings()
    assert settings.level == "INFO"
    assert settings.format == "pretty"
    assert settings.color is True


def test_log_settings_json_mode(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_COLOR", "false")
    settings = get_log_settings()
    assert settings.level == "DEBUG"
    assert settings.format == "json"
    assert settings.color is False


def test_safe_preview_truncates_long_values():
    assert safe_preview("abcdef", limit=4) == "a..."
    assert safe_preview(None) == ""


def test_sanitize_fields_redacts_secrets_and_summarizes_collections():
    fields = sanitize_fields({
        "api_key": "secret-value",
        "password": "pw",
        "parts": [{"ps_number": "PS1"}, {"ps_number": "PS2"}],
        "payload": {"a": 1, "b": 2},
        "message": "hello",
    })
    assert fields["api_key"] == "[redacted]"
    assert fields["password"] == "[redacted]"
    assert fields["parts"] == "list(len=2)"
    assert fields["payload"] == "dict(keys=2)"
    assert fields["message"] == "hello"


def test_log_event_emits_event_name(caplog):
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("test.observability")
    log_event(logger, "unit.test", answer=42)
    assert any("unit.test" in r.message and "answer=42" in r.message for r in caplog.records)
```

Keep the existing span and trace tests in the file.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
conda run -n instalily pytest backend/tests/test_observability.py -v
```

Expected: FAIL because the new helper functions do not exist.

- [ ] **Step 3: Add dependency**

Append this line to `backend/requirements.txt`:

```text
loguru==0.7.3
```

- [ ] **Step 4: Implement Loguru-backed observability helpers**

Replace `backend/app/observability.py` with an implementation that:

- Imports `logger as _loguru_logger` from Loguru.
- Defines `LogSettings`.
- Provides `get_log_settings()`.
- Configures Loguru at import time.
- Preserves `get_logger`, `new_request_id`, `RequestTrace`, `span`, `trace_request`.
- Adds `safe_preview`, `sanitize_fields`, and `log_event`.
- Intercepts Loguru into stdlib logging during tests so `caplog` still sees messages.

The compatibility contract:

```python
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

`log_event(logger, event, **fields)` should sanitize fields, include current request id if one is active, and emit a single readable message like:

```text
intent.classified req_id=abc intent=search model=WDT780SAEM1
```

- [ ] **Step 5: Run focused observability tests**

Run:

```bash
conda run -n instalily pytest backend/tests/test_observability.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/observability.py backend/tests/test_observability.py
git commit -m "feat: add loguru observability helpers"
```

---

### Task 2: Instrument Chat Request Lifecycle

**Files:**
- Modify: `backend/app/routers/chat.py`
- Modify: `backend/tests/test_api_integration.py`

- [ ] **Step 1: Write a focused lifecycle logging assertion**

Add assertions to `test_chat_sse_deterministic_done_event` in `backend/tests/test_api_integration.py` using `caplog`:

```python
def test_chat_sse_deterministic_done_event(client, caplog):
    import logging
    caplog.set_level(logging.INFO)
    sid = client.post("/api/session").json()["session_id"]
    with client.stream("POST", "/api/chat", json={
        "session_id": sid,
        "message": "Hi",
        "stream": True,
    }) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        chunks = list(r.iter_bytes())
    assert chunks
    payload = b"".join(chunks).decode()
    assert '"stage": "Understanding your request..."' in payload
    assert '"done": true' in payload
    assert '"text"' in payload
    assert payload.index('"stage": "Understanding your request..."') < payload.index('"done": true')
    messages = "\n".join(r.message for r in caplog.records)
    assert "chat.request.start" in messages
    assert "intent.classified" in messages
    assert "sse.stage" in messages
    assert "chat.response.done" in messages
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
conda run -n instalily env TEST_DATABASE_URL=postgresql+psycopg://partselect:partselect@localhost:5432/partselect pytest backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: FAIL because the lifecycle event names are not logged yet.

- [ ] **Step 3: Import logging helpers in chat route**

Update the observability import in `backend/app/routers/chat.py`:

```python
from app.observability import (
    get_logger,
    log_event,
    new_request_id,
    safe_preview,
    span,
    trace_request,
)
```

- [ ] **Step 4: Add response metadata helper**

Add this helper near `_track_parts`:

```python
def _payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_text": bool(payload.get("text")),
        "parts_count": len(payload.get("parts") or []),
        "installation_steps_count": len(payload.get("installation_steps") or []),
        "has_compatibility": bool(payload.get("compatibility")),
        "has_cart_update": bool(payload.get("cart_update")),
        "out_of_scope": bool(payload.get("out_of_scope")),
        "source": payload.get("source"),
    }
```

- [ ] **Step 5: Log stages and final responses**

In the streaming wrapper, before each `yield sse_stage(...)`, call:

```python
log_event(log, "sse.stage", stage="Understanding your request...")
```

In `_respond_json_or_sse`, before stage emission:

```python
if stage:
    log_event(log, "sse.stage", stage=stage)
    yield sse_stage(stage)
```

Before `yield sse_done(full)`, call:

```python
log_event(log, "chat.response.done", **_payload_metadata(full))
```

In `_stream_llm_tokens`, log `llm.stream.start`, stage, and `llm.stream.done` with token count and char count.

- [ ] **Step 6: Log request start, model resolution, branch selection**

At the top of `_chat_inner`, after `message` and `active` are computed, call:

```python
log_event(
    log,
    "chat.request.start",
    has_session=bool(req.session_id),
    stream=req.stream,
    message=safe_preview(message),
    active=safe_preview(active),
    provided_model=safe_preview(req.appliance_model),
)
```

After appliance model resolution, call:

```python
log_event(log, "chat.model.resolved", model=appliance_model or "", session_model=bool(session and session.get("appliance_model")))
```

After classification and cart reconciliation, call:

```python
log_event(
    log,
    "intent.classified",
    intent=intent.value,
    browse_all=classification.browse_all_parts,
    part_query=catalog_filter,
    ps_number=ps,
    catalog_scope=catalog_scope.value,
    model=appliance_model or "",
)
```

Before each branch return, add one `chat.branch.selected` event with the intent/branch name. At minimum log this once after `log.info("req=%s intent=...")`:

```python
log_event(log, "chat.branch.selected", branch=intent.value)
```

For out-of-scope responses, log `chat.scope.rejected`.

- [ ] **Step 7: Run focused integration test**

Run:

```bash
conda run -n instalily env TEST_DATABASE_URL=postgresql+psycopg://partselect:partselect@localhost:5432/partselect pytest backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_api_integration.py
git commit -m "feat: log chat request lifecycle"
```

---

### Task 3: Instrument Classifier and Agent Model Usage

**Files:**
- Modify: `backend/app/agent/router.py`
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/agent/troubleshoot_handler.py`

- [ ] **Step 1: Add classifier logs**

In `backend/app/agent/router.py`, import `log_event` and `safe_preview`:

```python
from app.observability import get_logger, log_event, safe_preview
from app.config import load_settings
```

At the start of `classify_intent`, load settings and log:

```python
settings = load_settings()
log_event(log, "intent.classify.start", model=settings.llm.tool_model, message=safe_preview(text))
```

After successful result, replace or supplement the existing `log.info(...)` with:

```python
log_event(
    log,
    "intent.classify.done",
    model=settings.llm.tool_model,
    intent=result.intent.value,
    browse_all=result.browse_all_parts,
    part_query=result.part_query,
    ps_number=result.ps_number,
    fallback=False,
)
```

In the exception fallback path, log:

```python
fallback = _fallback_classification(text)
log_event(log, "intent.classify.done", model=settings.llm.tool_model, intent=fallback.intent.value, fallback=True)
return fallback
```

- [ ] **Step 2: Add LangGraph agent logs**

In `backend/app/agent/graph.py`, import `load_settings`, `log_event`, and `safe_preview`.

At the start of `run_agent_streaming`, log:

```python
settings = load_settings()
log_event(
    log,
    "agent.invoke.start",
    session_id=session_id,
    model=settings.llm.synthesis_model,
    has_appliance_model=bool(appliance_model),
    message=safe_preview(message),
    history_count=len(history),
)
```

Inside the event loop, when `event.get("event")` contains a tool start/end signal, log one `agent.tool.transition` with event name and node/tool name.

Track emitted token count and char count. Before returning on success, log:

```python
log_event(log, "agent.stream.done", session_id=session_id, token_count=token_count, char_count=char_count)
```

In exception fallback paths, log `agent.stream.error` or `agent.invoke.error`.

- [ ] **Step 3: Add troubleshooting logs**

In `backend/app/agent/troubleshoot_handler.py`, add `log_event` imports. Log:

```python
log_event(log, "tool.call.start", tool="troubleshoot.prepare", message=safe_preview(message))
```

after prep:

```python
log_event(log, "tool.call.done", tool="troubleshoot.prepare", parts_count=len(parts), appliance=appliance)
```

Log `llm.stream.start` and `llm.stream.done` around troubleshooting streaming synthesis with model name from `load_settings().llm.synthesis_model`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
conda run -n instalily pytest backend/tests/test_router.py backend/tests/test_agent_graph.py backend/tests/test_troubleshoot_handler.py -v
```

Expected: Tests either PASS or skip according to existing environment gates.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/router.py backend/app/agent/graph.py backend/app/agent/troubleshoot_handler.py
git commit -m "feat: log model and agent execution"
```

---

### Task 4: Instrument Tools and Data Sources

**Files:**
- Modify: `backend/app/agent/tools/search_parts.py`
- Modify: `backend/app/agent/tools/check_compatibility.py`
- Modify: `backend/app/agent/tools/list_compatible_parts.py`
- Modify: `backend/app/agent/tools/get_installation.py`
- Modify: `backend/app/agent/tools/add_to_cart.py`
- Modify: `backend/app/agent/tools/remove_from_cart.py`
- Modify: `backend/app/agent/catalog.py`
- Modify: `backend/app/live_scrape/gateway.py`

- [ ] **Step 1: Add tool call logs to deterministic tools**

For each listed tool module, import:

```python
from app.observability import get_logger, log_event, safe_preview
```

Create a module logger such as:

```python
log = get_logger("tools.search_parts")
```

At tool entry, log `tool.call.start` with safe inputs. At each return point, log `tool.call.done` with source/count/found/success fields. In exception handlers that already exist, use `log.exception(...)` plus `log_event(log, "tool.call.error", tool="...", error_type=type(exc).__name__)` where an exception object is available.

- [ ] **Step 2: Add catalog resolver logs**

In `backend/app/agent/catalog.py`, add `log_event` calls:

```python
log_event(log, "tool.call.start", tool="resolve_compatible_parts", model=model, scope=request.scope.value, part_query=request.part_type_filter, limit=request.limit)
```

Before each packaged return, log `tool.call.done` with source, count, and full_catalog.

- [ ] **Step 3: Add live gateway logs**

In `backend/app/live_scrape/gateway.py`, log `tool.call.start`, `tool.call.done`, and existing exception paths for:

- `fetch_part`
- `fetch_model_parts`
- `fetch_installation`
- `check_compat_on_model_page`

Fields should include backend, ps/model, source/live completion, missing field count, and duration when available.

- [ ] **Step 4: Run focused tool tests**

Run:

```bash
conda run -n instalily pytest backend/tests/test_tools_unit.py backend/tests/test_catalog.py backend/tests/test_live_scrape_gateway.py -v
```

Expected: PASS for available tests; tests with existing environment gates may skip.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools/search_parts.py backend/app/agent/tools/check_compatibility.py backend/app/agent/tools/list_compatible_parts.py backend/app/agent/tools/get_installation.py backend/app/agent/tools/add_to_cart.py backend/app/agent/tools/remove_from_cart.py backend/app/agent/catalog.py backend/app/live_scrape/gateway.py
git commit -m "feat: log agent tool calls"
```

---

### Task 5: Final Verification

**Files:**
- Read-only unless verification reveals a defect.

- [ ] **Step 1: Run observability tests**

Run:

```bash
conda run -n instalily pytest backend/tests/test_observability.py -v
```

Expected: PASS.

- [ ] **Step 2: Run chat streaming test**

Run:

```bash
conda run -n instalily env TEST_DATABASE_URL=postgresql+psycopg://partselect:partselect@localhost:5432/partselect pytest backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: PASS.

- [ ] **Step 3: Run focused backend regression suite**

Run:

```bash
conda run -n instalily pytest backend/tests/test_sse.py backend/tests/test_router.py backend/tests/test_troubleshoot_handler.py backend/tests/test_tools_unit.py backend/tests/test_catalog.py backend/tests/test_live_scrape_gateway.py -v
```

Expected: PASS or documented environment-gated skips only.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git status --short
git diff -- backend/requirements.txt backend/app/observability.py backend/tests/test_observability.py backend/app/routers/chat.py backend/tests/test_api_integration.py backend/app/agent/router.py backend/app/agent/graph.py backend/app/agent/troubleshoot_handler.py backend/app/agent/tools/search_parts.py backend/app/agent/tools/check_compatibility.py backend/app/agent/tools/list_compatible_parts.py backend/app/agent/tools/get_installation.py backend/app/agent/tools/add_to_cart.py backend/app/agent/tools/remove_from_cart.py backend/app/agent/catalog.py backend/app/live_scrape/gateway.py
```

Expected: Only planned files contain logging changes. Existing unrelated dirty files remain untouched.

- [ ] **Step 5: Manual Docker log check**

With Docker already running, make one chat request through the app or API and inspect backend logs:

```bash
docker compose logs backend --tail=120
```

Expected: Logs include readable events such as `chat.request.start`, `intent.classify.start`, `intent.classified`, `sse.stage`, tool call events, model names, request id, and `trace.summary`.

---

## Self-Review

- Spec coverage: The plan covers Loguru setup, pretty/json config, safe redaction, request lifecycle logs, model logs, agent logs, tool/source logs, stage logs, timings, and verification.
- Placeholder scan: The plan uses concrete file paths, helper names, commands, expected outcomes, and code snippets.
- Type consistency: Event helper names are consistently `log_event`, `safe_preview`, `sanitize_fields`, and config is `get_log_settings`.
