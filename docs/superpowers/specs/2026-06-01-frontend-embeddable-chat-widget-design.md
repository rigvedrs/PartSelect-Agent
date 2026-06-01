# Frontend Embeddable Chat Widget Design

## Goal

Make the existing PartSelect chat frontend simple to integrate into another web page as a floating chat widget, while keeping the implementation small and easy to explain.

Success means:

- A host page can embed the chat widget with a short documented snippet.
- The widget can expand on desktop so messages are easier to read.
- Links rendered in chat messages open in a new browser tab.
- A user can send at most 5 messages in one chat session, then is asked to start a new chat.
- Existing local demo behavior remains available.

## Current Context

The frontend already has a floating React widget in `frontend/src/components/ChatWidget.js`. It is mounted by `frontend/src/App.js` for the local demo page and uses:

- `useSession` for `localStorage` session persistence.
- `useChat` for streaming chat requests and chat history.
- `MessageContent` with `marked` for Markdown rendering.
- `ChatHeader`, `MessageList`, `ModelInput`, `ChatInput`, and `CartDrawer` for the widget UI.

The app is a Create React App project, so the lowest-risk embed path is to keep the single existing build bundle and make the mount logic choose between the standalone demo app and the embeddable widget.

## Recommended Approach

Update the existing React mount logic so the built frontend bundle can mount `ChatWidget` directly into a host page element. The README should describe the widget as embeddable by including the built frontend assets and adding a mount node such as:

```html
<div id="partselect-chat-widget"></div>
```

The bundle should render `ChatWidget` into `#partselect-chat-widget` when that element exists. Otherwise it should keep the current local demo behavior by rendering `App` into `#root`. This keeps integration simple and avoids a larger SDK-style API unless future requirements need it.

## Components and Behavior

### Embed Mounting

Update `frontend/src/index.js` with one responsibility added: choose the mount target.

If `#partselect-chat-widget` exists, render `<ChatWidget />` there. If not, render the existing `<App />` into `#root`. The documented integration surface is the host page mount node plus the built JS/CSS assets.

### Expand Button

Add `expanded` state to `ChatWidget`.

The chat header receives an expand/collapse handler and shows a compact control. Default desktop dimensions remain close to the current widget size. Expanded mode uses a larger desktop panel so long messages and product cards are easier to read. On small screens, the existing full-screen mobile behavior remains the same.

### Links Open in a New Tab

Update Markdown rendering in `MessageContent` so generated links use:

```html
target="_blank" rel="noopener noreferrer"
```

This applies to links supplied by the agent in assistant messages and prevents the host page from being replaced by a PartSelect or resource link.

### Five-Message Session Limit

Count user-sent messages in the current frontend chat session. A user message is any message sent through the visible input or suggested query flow.

When the count reaches 5:

- Disable the chat input.
- Show a short notice asking the user to start a new chat.
- Keep the "New chat" control available.

Starting a new chat resets the counter because it creates a fresh frontend session. Existing restored history may contain more than 5 messages from older sessions, but the limit applies to the active session after this change.

## Data Flow

Embedding only changes how the widget is mounted. Once mounted, chat requests continue through the existing flow:

1. `ChatWidget` ensures a session.
2. `useChat.send()` posts the message to `POST /api/chat`.
3. Streaming stage/token/done events update the assistant bubble.
4. Cart updates refresh the cart drawer.

The message limit is enforced in the frontend before calling `send`, so no backend contract change is required.

## Error Handling

If the embed mount node is absent, the bundle falls back to the current demo app mount. If the backend request fails, existing `useChat` error behavior remains unchanged.

If a user reaches the message limit, the UI should not call the backend. It should present the new-chat notice instead.

## Testing

Add focused frontend tests where the existing Jest setup supports them:

- Markdown links render with `target="_blank"` and `rel="noopener noreferrer"`.
- Sending 5 user messages disables further input and shows the new-chat notice.
- Starting a new chat resets the message limit state.
- The expand control toggles the expanded panel class/state.

Run the frontend test command and build command as verification.

## Scope Boundaries

This design does not add a published npm package, a configurable SDK object, iframe isolation, cross-origin theming, or backend-side session enforcement. Those are useful only if the widget needs to become a public third-party integration surface later.
