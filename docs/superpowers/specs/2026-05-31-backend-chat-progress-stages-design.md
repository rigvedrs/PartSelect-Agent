# Backend Chat Progress Stages Design

## Goal

Improve the chat popup waiting experience by showing simple, live backend progress stages while the user is waiting for a response. The stages should be real backend-triggered events, but the labels must stay non-technical and customer-friendly.

Success criteria:

- The chat popup shows progress text during backend processing before answer text appears.
- The progress text disappears as soon as the first answer token or final assistant response arrives.
- Progress labels reflect actual backend transitions, not a purely frontend timer.
- Existing streaming response behavior continues to work.
- Non-streaming chat behavior remains unchanged.

## Scope

This feature uses the existing Server-Sent Events chat stream. The backend will add a new `stage` event type alongside the existing `token` and `done` events. The frontend will parse these events and show the latest stage on the assistant placeholder bubble.

This design does not add a progress bar, percentage estimate, separate polling endpoint, or deeply technical tool-by-tool UI.

## Backend Design

Add an SSE helper:

```json
{ "stage": "Understanding your request..." }
```

The chat route emits stage events only when `stream: true`. For non-streaming requests, the response shape stays the same.

Stage labels are broad and user-facing:

- `Understanding your request...` before intent classification.
- `Checking matching parts...` before part search, compatible-parts lookup, and live catalog lookup branches.
- `Checking compatibility...` before compatibility checks.
- `Finding installation steps...` before installation guide lookup.
- `Updating your cart...` before add/remove cart actions.
- `Reviewing repair guidance...` before troubleshooting preparation.
- `Putting the answer together...` before LLM synthesis or final answer generation.

For the general LangGraph path, emit `Putting the answer together...` before agent synthesis begins. If graph tool events are already available without changing tool internals, map the first tool-use transition to `Checking available information...`. The UI should never expose implementation names such as LangGraph, classifier, database, or scraper.

## Frontend Design

Update the SSE parser to call an `onStage` callback when a `stage` event arrives.

`useChat` will store the latest stage on the streaming assistant placeholder message. When a token arrives, the hook clears the stage and appends streamed content. When a final `done` event arrives without tokens, the final assistant payload replaces the placeholder, so no progress text remains.

The current loading dots should be replaced or extended with a compact progress component that displays the stage label in the assistant bubble. If no stage has arrived yet, it can show a neutral fallback such as `Working on it...` while the request is active.

## Data Flow

1. User sends a message.
2. Frontend appends the user message and an empty streaming assistant placeholder.
3. Backend begins processing and emits stage SSE events at real transition points.
4. Frontend updates the placeholder with the latest stage.
5. Backend emits the first token or final done event.
6. Frontend removes the stage display and shows the assistant response.

## Error Handling

If the request fails, the existing error response remains: `Sorry, something went wrong. Please try again.`

If a malformed stage event is received, the frontend ignores it. If no stage is received, the UI still shows the fallback waiting message while loading.

## Testing

Backend tests should verify:

- `sse_stage` emits a valid SSE JSON event.
- A streaming deterministic chat request includes at least one `stage` event before the `done` event.

Frontend verification should cover:

- Stage events update the pending assistant message.
- Token events clear the stage display.
- The production build succeeds.

Manual verification should confirm the chat popup displays stage text while waiting and removes it as soon as the response text appears.
