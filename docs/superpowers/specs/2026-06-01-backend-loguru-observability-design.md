# Backend Loguru Observability Design

## Goal

Add clear, readable, and configurable backend logging across the PartSelect agent request path so developers can understand exactly what happened during each chat turn: request lifecycle, intent classification, model usage, agent invocation, tool calls, stage emission, source selection, timings, and errors.

Success criteria:

- Local Docker logs are easy to scan with color, component names, request ids, event names, and important fields.
- Logs can switch to structured JSON-style output for production or log aggregation.
- Existing `get_logger(...)`, `span(...)`, and `trace_request(...)` call sites continue to work or require minimal targeted edits.
- Logs include model names, intent, branch, tool name, source, result counts, duration, and request id where relevant.
- Logs never expose API keys, raw environment secrets, huge payloads, or full unbounded user prompts/responses.

## Scope

This feature is backend-only. It updates the logging/observability layer and adds targeted instrumentation to the chat route, router/classifier, LangGraph agent, deterministic tools, catalog/live lookup, troubleshooting, and cart actions.

This design does not add an external observability vendor, distributed tracing backend, metrics dashboard, frontend log UI, or OpenTelemetry pipeline.

## Logging Architecture

Use Loguru as the backend logging engine while preserving the existing `app.observability` boundary.

`backend/app/observability.py` will own:

- Loguru setup and sink configuration.
- A compatibility `get_logger(name)` wrapper.
- Request id context management.
- Field-safe event helpers.
- Message/value sanitization helpers.
- Existing `span(...)` and `trace_request(...)` behavior.

Configuration comes from environment variables:

- `LOG_LEVEL`, default `INFO`.
- `LOG_FORMAT`, default `pretty`, allowed values `pretty` and `json`.
- `LOG_COLOR`, default enabled for pretty mode.

Pretty logs should be optimized for humans in Docker:

```text
12:34:56.789 | INFO  | req=abc123ef | routers.chat | intent.classified | intent=parts_for_model model=WDT780SAEM1 part_query=None
```

JSON mode should emit structured records with stable keys such as `time`, `level`, `component`, `event`, `req_id`, `intent`, `tool`, `model`, `source`, `count`, and `duration_ms`.

## Event Model

Add lightweight helper functions in `observability.py`:

- `log_event(logger, event, **fields)` for consistent event names and field formatting.
- `safe_preview(value, limit=160)` for prompt/message previews.
- `sanitize_fields(fields)` to drop or redact unsafe keys and truncate large values.

Event names should be dotted and stable:

- `chat.request.start`
- `chat.model.resolved`
- `chat.scope.rejected`
- `intent.classify.start`
- `intent.classified`
- `chat.branch.selected`
- `sse.stage`
- `tool.call.start`
- `tool.call.done`
- `agent.invoke.start`
- `agent.tool.transition`
- `agent.stream.done`
- `llm.stream.start`
- `llm.stream.done`
- `trace.summary`

## Logging Coverage

### Chat Route

Log request start with request id, session id presence, stream mode, message preview, and provided appliance model preview.

Log model resolution and route/branch selection. After classification, log intent, browse-all flag, part query, PS number, catalog scope, resolved model, and route.

Log each SSE stage emitted with request id and stage label.

Log final response metadata: whether parts, installation steps, compatibility, cart update, source, or out-of-scope fields are present; do not log full payloads.

### LLM and Intent Classifier

Log classifier start/end with the configured classifier model and whether fallback classification was used.

Log synthesis/general agent start/end with the configured synthesis model, streaming mode, token count or character count, and duration.

### Tools and Data Sources

Log deterministic tool calls around:

- `search_parts`
- `list_compatible_parts`
- `check_compatibility`
- `get_installation_guide`
- `add_to_cart`
- `remove_from_cart`
- troubleshooting retrieval/synthesis
- live scrape gateway calls

For each tool, log start/done/error with safe fields:

- Tool name.
- PS number or model number if present.
- Part query if present.
- Source (`db`, `live`, `none`) when known.
- Result count.
- Duration.

Do not log full part lists, full compatibility rows, or raw scrape payloads.

### LangGraph Agent

Log agent invocation start with request id, session id, model, and appliance model presence.

Log graph tool transitions using friendly tool names. Log stream completion with emitted token/character counts. On graph fallback or exception, log the error with request id and path.

## Safety

The sanitizer must redact fields whose names include:

- `api_key`
- `token`
- `secret`
- `password`
- `authorization`

User message and model/prompt previews should be capped. Lists and dicts should be summarized by type and size unless explicitly whitelisted.

Exceptions should include stack traces, but not unsafe field values.

## Data Flow

1. App startup configures Loguru from environment.
2. A chat request creates a request id and activates trace context.
3. Each major stage logs through `log_event(...)`; request id is included from context when available.
4. `span(...)` records timing and can log readable span completion for important blocks.
5. `trace_request(...)` logs a final `trace.summary` event.
6. In pretty mode, Docker logs stay human-readable and colored.
7. In JSON mode, the same events are emitted as structured records.

## Error Handling

Logging must never break the chat path. If Loguru configuration fails, the app should still have a working stderr logger.

Instrumentation should be best-effort. Failures in log formatting or field sanitization should fall back to a simple safe message instead of raising into request handling.

## Testing

Backend tests should verify:

- Default logging settings select pretty mode and `INFO`.
- JSON mode can be selected by environment.
- Unsafe keys are redacted.
- Long previews are truncated.
- `log_event(...)` includes event names and safe fields.
- Existing observability span/request summary tests still pass.
- Focused chat SSE tests still pass.

Manual verification should run the Docker backend and confirm logs are readable during a chat request, including request id, intent, model, stage, tool/source, and final summary lines.
