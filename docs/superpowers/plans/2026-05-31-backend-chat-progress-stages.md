# Backend Chat Progress Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show real, backend-triggered, non-technical progress stages in the chat popup while a response is being prepared, then hide them as soon as answer text appears.

**Architecture:** Reuse the existing `/api/chat` Server-Sent Events stream and add a `stage` event alongside `token` and `done`. The backend emits broad friendly stages at real transition points; the frontend stores the latest stage on the pending assistant message and clears it when text starts streaming.

**Tech Stack:** FastAPI, Starlette `StreamingResponse`, Python async generators, React 18, Create React App/Jest, browser `fetch` streaming.

---

## File Structure

- Modify: `backend/app/routers/sse.py`  
  Adds the `sse_stage(label: str)` helper.

- Modify: `backend/app/routers/chat.py`  
  Wraps streaming chat responses so the first `Understanding your request...` stage is emitted before backend work begins, then emits branch-specific stages through existing response helpers.

- Modify: `backend/tests/test_sse.py`  
  Covers the new SSE stage helper.

- Modify: `backend/tests/test_api_integration.py`  
  Verifies a streaming chat response includes a stage event before the final done event.

- Modify: `frontend/src/lib/api.js`  
  Parses `stage` SSE events and calls `onStage`.

- Create: `frontend/src/lib/api.test.js`  
  Tests stage event parsing without hitting the network.

- Modify: `frontend/src/hooks/useChat.js`  
  Stores and clears progress stage text on the pending assistant message.

- Modify: `frontend/src/components/TypingIndicator.js`  
  Converts the dots-only loader into a compact friendly progress indicator that accepts a label.

- Modify: `frontend/src/components/MessageBubble.js`  
  Displays the progress indicator inside the pending assistant bubble when the message is streaming and has no content.

---

### Task 1: Add Backend SSE Stage Helper

**Files:**
- Modify: `backend/tests/test_sse.py`
- Modify: `backend/app/routers/sse.py`

- [ ] **Step 1: Write the failing helper test**

Add `sse_stage` to the import and assertions in `backend/tests/test_sse.py`:

```python
def test_sse_line_format():
    from app.routers.sse import sse_line, sse_token, sse_done, sse_stage
    assert sse_line({"token": "hi"}) == b'data: {"token": "hi"}\n\n'
    assert b"token" in sse_token("x")
    assert b'"done": true' in sse_done({"session_id": "s1", "text": "ok"})
    assert sse_stage("Understanding your request...") == (
        b'data: {"stage": "Understanding your request..."}\n\n'
    )
```

- [ ] **Step 2: Run the focused backend test to verify it fails**

Run:

```bash
pytest backend/tests/test_sse.py::test_sse_line_format -v
```

Expected: FAIL with an import error or missing `sse_stage` name.

- [ ] **Step 3: Implement the SSE helper**

Add this function to `backend/app/routers/sse.py` between `sse_token` and `sse_done`:

```python
def sse_stage(label: str) -> bytes:
    return sse_line({"stage": label})
```

- [ ] **Step 4: Run the focused backend test to verify it passes**

Run:

```bash
pytest backend/tests/test_sse.py::test_sse_line_format -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/sse.py backend/tests/test_sse.py
git commit -m "feat: add chat progress stage sse event"
```

---

### Task 2: Emit Real Backend Stages From Streaming Chat

**Files:**
- Modify: `backend/tests/test_api_integration.py`
- Modify: `backend/app/routers/chat.py`

- [ ] **Step 1: Write the failing integration test**

Update `test_chat_sse_deterministic_done_event` in `backend/tests/test_api_integration.py` so it asserts a stage arrives before done:

```python
def test_chat_sse_deterministic_done_event(client):
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
```

- [ ] **Step 2: Run the focused integration test to verify it fails**

Run:

```bash
pytest backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: FAIL because no `stage` event is emitted.

- [ ] **Step 3: Import the stage helper**

Change the SSE import near the top of `backend/app/routers/chat.py`:

```python
from app.routers.sse import sse_done, sse_stage, sse_token
```

- [ ] **Step 4: Add a streaming wrapper that emits the first stage before backend work**

Replace the existing `chat` function in `backend/app/routers/chat.py` with:

```python
@router.post("/chat")
async def chat(req: ChatRequest):
    rid = new_request_id()
    if req.stream:
        async def _gen() -> AsyncIterator[bytes]:
            with trace_request(rid, route="chat") as trace:
                yield sse_stage("Understanding your request...")
                result = await _chat_inner(req, rid, trace)
                if isinstance(result, StreamingResponse):
                    async for chunk in result.body_iterator:
                        yield chunk
                    return
                yield sse_done(result)

        return _sse_response(_gen())

    with trace_request(rid, route="chat") as trace:
        return await _chat_inner(req, rid, trace)
```

This keeps non-streaming behavior unchanged and starts the SSE response before classification, routing, lookup, or generation work happens.

- [ ] **Step 5: Add optional stage support to deterministic response helper**

Change `_respond_json_or_sse` in `backend/app/routers/chat.py` to accept a stage label and emit it inside the existing generator:

```python
async def _respond_json_or_sse(
    req: ChatRequest,
    session_id: str,
    user_message: str,
    payload: dict[str, Any],
    stage: str | None = None,
) -> dict[str, Any] | StreamingResponse:
    if req.stream:
        full = {"session_id": session_id, **payload}

        async def _gen() -> AsyncIterator[bytes]:
            if stage:
                yield sse_stage(stage)
            _track_parts(session_id, full.get("parts"))
            record_assistant_response(session_id, user_message, full)
            yield sse_done(full)

        return _sse_response(_gen())
    return _finalize(session_id, user_message, payload)
```

- [ ] **Step 6: Add optional stage support to token streaming helper**

Change `_stream_llm_tokens` to accept and emit an initial stage:

```python
async def _stream_llm_tokens(
    req: ChatRequest,
    session_id: str,
    user_message: str,
    token_source: AsyncIterator[str],
    extra: dict[str, Any] | None = None,
    stage: str | None = None,
) -> StreamingResponse:
    async def _gen() -> AsyncIterator[bytes]:
        if stage:
            yield sse_stage(stage)
        text_parts: list[str] = []
        async for token in token_source:
            text_parts.append(token)
            yield sse_token(token)
        full_text = "".join(text_parts).strip()
        if not full_text:
            full_text = "I couldn't complete that request. Please try again or rephrase your question."
        payload: dict[str, Any] = {"session_id": session_id, "text": full_text, **(extra or {})}
        _track_parts(session_id, payload.get("parts"))
        record_assistant_response(session_id, user_message, payload)
        yield sse_done(payload)

    return _sse_response(_gen())
```

- [ ] **Step 7: Pass friendly branch stages at existing return points**

Update branch returns in `backend/app/routers/chat.py` by passing the stage argument shown here:

```python
return await _respond_json_or_sse(req, session_id, message, {"text": greet}, "Putting the answer together...")
```

```python
return await _respond_json_or_sse(req, session_id, message, {
    "text": result["reason"],
    "parts": result["parts"],
}, "Checking matching parts...")
```

```python
return await _respond_json_or_sse(req, session_id, message, {
    "text": result["reason"],
    "parts": result["parts"],
    "source": result.get("source"),
}, "Checking matching parts...")
```

```python
return await _respond_json_or_sse(req, session_id, message, {"text": text}, "Putting the answer together...")
```

```python
return await _respond_json_or_sse(req, session_id, message, {
    "text": result["reason"],
    "compatibility": result,
}, "Checking compatibility...")
```

```python
return await _respond_json_or_sse(req, session_id, message, {
    "text": text,
    "installation_steps": guide.get("steps", []),
    "parts": [{"ps_number": guide["ps_number"], "name": guide.get("part_name"),
                "image_url": guide.get("image_url"), "product_url": guide.get("product_url")}]
             if guide.get("found") else [],
}, "Finding installation steps...")
```

```python
return await _respond_json_or_sse(req, session_id, message, {
    "text": text,
    "cart_update": result,
}, "Updating your cart...")
```

For `_stream_troubleshoot`, pass the synthesis stage:

```python
return await _stream_llm_tokens(
    req,
    session_id,
    user_message,
    _tokens(),
    extra=extra,
    stage="Reviewing repair guidance...",
)
```

For the general streaming agent path, pass:

```python
return await _stream_llm_tokens(
    req,
    session_id,
    message,
    run_agent_streaming(session_id, message, appliance_model or None, history),
    stage="Putting the answer together...",
)
```

Use the same labels for similar branches. Do not add technical labels such as database, classifier, LangGraph, or scraper.

- [ ] **Step 8: Run the focused integration test to verify it passes**

Run:

```bash
pytest backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: PASS.

- [ ] **Step 9: Run backend SSE tests**

Run:

```bash
pytest backend/tests/test_sse.py backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_api_integration.py
git commit -m "feat: emit chat progress stages"
```

---

### Task 3: Parse Stage Events in the Frontend API Client

**Files:**
- Create: `frontend/src/lib/api.test.js`
- Modify: `frontend/src/lib/api.js`

- [ ] **Step 1: Export the parser and write the failing parser tests**

Create `frontend/src/lib/api.test.js`:

```javascript
import { parseSseBlock } from "./api";

test("parseSseBlock parses stage events", () => {
  expect(parseSseBlock('data: {"stage":"Understanding your request..."}')).toEqual({
    stage: "Understanding your request...",
  });
});

test("parseSseBlock ignores malformed events", () => {
  expect(parseSseBlock("event: ping")).toBeNull();
  expect(parseSseBlock("data: not-json")).toBeNull();
});
```

Change the parser declaration in `frontend/src/lib/api.js` so the test can import it:

```javascript
export function parseSseBlock(block) {
```

- [ ] **Step 2: Run the focused frontend test to verify the current parser export works**

Run:

```bash
CI=true npm test -- --runInBand src/lib/api.test.js
```

Expected: PASS after exporting `parseSseBlock`.

- [ ] **Step 3: Add `onStage` support to the streaming API**

Update the `sendMessageStream` signature in `frontend/src/lib/api.js`:

```javascript
export async function sendMessageStream({
  sessionId,
  message,
  applianceModel,
  onToken,
  onStage,
  onDone,
  signal,
}) {
```

In both places that parse an SSE block, add stage handling before token handling:

```javascript
if (data.stage) onStage?.(data.stage);
if (data.token) onToken?.(data.token);
if (data.done) {
  finalPayload = data;
  onDone?.(data);
}
```

The same three lines must be present in the main loop and the final buffer handling block.

- [ ] **Step 4: Run the focused frontend test**

Run:

```bash
CI=true npm test -- --runInBand src/lib/api.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.js frontend/src/lib/api.test.js
git commit -m "feat: parse chat progress stage events"
```

---

### Task 4: Store and Clear Stage Text in Chat State

**Files:**
- Modify: `frontend/src/hooks/useChat.js`

- [ ] **Step 1: Add stage state to the assistant placeholder**

In `frontend/src/hooks/useChat.js`, update the placeholder assistant message created in `send`:

```javascript
setMessages((prev) => [
  ...prev,
  { role: "user", content: text },
  { role: "assistant", content: "", streaming: true, stage: "Working on it..." },
]);
```

- [ ] **Step 2: Add `onStage` handling**

Inside the `sendMessageStream` call in `useChat.js`, add this callback before `onToken`:

```javascript
onStage: (stage) => {
  setMessages((prev) => {
    if (prev.length === 0) return prev;
    const next = [...prev];
    const idx = next.length - 1;
    next[idx] = {
      ...next[idx],
      stage,
      streaming: true,
    };
    return next;
  });
},
```

- [ ] **Step 3: Clear stage text as soon as answer text starts**

Update the `onToken` message replacement in `useChat.js`:

```javascript
next[idx] = {
  ...next[idx],
  content: (next[idx].content || "") + token,
  stage: "",
  streaming: true,
};
```

- [ ] **Step 4: Ensure final assistant payloads never keep stale stage text**

Add `stage: ""` to `assistantFromPayload`:

```javascript
function assistantFromPayload(data) {
  return {
    role: "assistant",
    content: data.text || "",
    parts: data.parts,
    installation_steps: data.installation_steps,
    compatibility: data.compatibility,
    out_of_scope: data.out_of_scope,
    source: data.source,
    streaming: false,
    stage: "",
  };
}
```

- [ ] **Step 5: Run the frontend parser test**

Run:

```bash
CI=true npm test -- --runInBand src/lib/api.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useChat.js
git commit -m "feat: track chat progress stages"
```

---

### Task 5: Display Stage Text in the Assistant Bubble

**Files:**
- Modify: `frontend/src/components/TypingIndicator.js`
- Modify: `frontend/src/components/MessageBubble.js`

- [ ] **Step 1: Update the progress indicator component**

Replace `frontend/src/components/TypingIndicator.js` with:

```javascript
import React from "react";

export default function TypingIndicator({ label = "Working on it..." }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        padding: "6px 0",
        alignItems: "center",
        color: "var(--chat-bubble-assistant-text)",
        fontSize: "0.86rem",
      }}
      role="status"
      aria-live="polite"
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: "var(--partselect-teal)",
          display: "inline-block",
          animation: "pulse 1.2s ease-in-out infinite",
          flex: "0 0 auto",
        }}
        aria-hidden="true"
      />
      <span>{label}</span>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.35; transform: scale(0.85); }
          50% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
```

- [ ] **Step 2: Render the stage indicator from pending assistant messages**

Update `frontend/src/components/MessageBubble.js` imports:

```javascript
import TypingIndicator from "./TypingIndicator";
```

Update the message destructuring:

```javascript
const { role, content, parts, installation_steps, compatibility, out_of_scope, streaming, stage } = message;
```

Replace the current empty streaming cursor block:

```javascript
{streaming && !content && (
  <span className="stream-cursor" aria-hidden="true">▍</span>
)}
```

with:

```javascript
{streaming && !content && (
  <TypingIndicator label={stage || "Working on it..."} />
)}
```

- [ ] **Step 3: Run the frontend test and build**

Run:

```bash
CI=true npm test -- --runInBand src/lib/api.test.js
npm run build
```

Expected: Both commands PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TypingIndicator.js frontend/src/components/MessageBubble.js
git commit -m "feat: show chat progress stages"
```

---

### Task 6: Final Verification

**Files:**
- Read-only verification unless a previous task reveals a defect.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
pytest backend/tests/test_sse.py backend/tests/test_api_integration.py::test_chat_sse_deterministic_done_event -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused tests**

Run:

```bash
CI=true npm test -- --runInBand src/lib/api.test.js
```

Expected: PASS.

- [ ] **Step 3: Build frontend**

Run:

```bash
npm run build
```

Expected: PASS and `frontend/build` updates or is regenerated according to the existing project behavior.

- [ ] **Step 4: Manual browser verification**

Start the app using the project’s normal local development flow. Open the chat popup, send a message, and confirm:

- A stage such as `Understanding your request...` appears while waiting.
- Branch stages such as `Checking matching parts...` or `Putting the answer together...` can appear when relevant.
- The stage disappears as soon as answer text appears.
- Final product cards, installation steps, compatibility badges, and cart updates still render.

- [ ] **Step 5: Inspect changed files**

Run:

```bash
git status --short
git diff -- backend/app/routers/sse.py backend/app/routers/chat.py backend/tests/test_sse.py backend/tests/test_api_integration.py frontend/src/lib/api.js frontend/src/lib/api.test.js frontend/src/hooks/useChat.js frontend/src/components/TypingIndicator.js frontend/src/components/MessageBubble.js
```

Expected: Only the planned files contain feature-related changes.

- [ ] **Step 6: Final commit if verification required fixes**

If Task 6 required additional fixes, commit only those fixes:

```bash
git add backend/app/routers/sse.py backend/app/routers/chat.py backend/tests/test_sse.py backend/tests/test_api_integration.py frontend/src/lib/api.js frontend/src/lib/api.test.js frontend/src/hooks/useChat.js frontend/src/components/TypingIndicator.js frontend/src/components/MessageBubble.js
git commit -m "fix: verify chat progress stages"
```

If Task 6 required no code changes, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan adds real backend `stage` SSE events, displays the latest stage in the chat popup, clears stages on the first token/final response, preserves non-streaming behavior, and includes backend/frontend verification.
- Placeholder scan: The plan contains concrete file paths, code snippets, commands, and expected results.
- Type consistency: The event property is consistently named `stage`; the frontend callback is consistently named `onStage`; final assistant messages clear `stage` with an empty string.
