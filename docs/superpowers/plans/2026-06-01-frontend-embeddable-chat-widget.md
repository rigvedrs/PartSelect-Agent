# Frontend Embeddable Chat Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing React chat widget easy to embed, expandable, safer for outbound links, and limited to 5 user messages per session.

**Architecture:** Reuse the existing `ChatWidget` component and CRA bundle. Add small React tests around the new behaviors, keep the current local demo mount through `App`, and render `ChatWidget` directly when a host page provides `#partselect-chat-widget`.

**Tech Stack:** React 18, Create React App, Jest, React Testing Library, `marked`, plain imported CSS.

---

## File Structure

- Modify `frontend/src/components/MessageContent.js`: post-process rendered Markdown links so they open in a new tab.
- Create `frontend/src/components/MessageContent.test.js`: focused test for outbound link attributes.
- Modify `frontend/src/components/ChatInput.js`: accept an optional `limitReached` prop and render disabled-limit copy.
- Modify `frontend/src/components/ChatHeader.js`: accept expand/collapse props and render an expand button.
- Modify `frontend/src/components/ChatWidget.js`: track expanded state, count user messages, block sends after 5, reset on new chat, pass new props to header/input, and add expanded class.
- Modify `frontend/src/components/ChatWidget.css`: add expanded desktop panel dimensions.
- Create `frontend/src/components/ChatWidget.test.js`: focused tests for message limit, reset, and expand state.
- Modify `frontend/src/index.js`: mount `ChatWidget` into `#partselect-chat-widget` when present, otherwise mount `App` into `#root`.
- Create `frontend/src/index.test.js`: verify both mount paths.
- Modify `README.md`: document the widget as embeddable and mention expand, new-tab links, and 5-message session limit.

## Task 1: Make Markdown Links Open in a New Tab

**Files:**
- Modify: `frontend/src/components/MessageContent.js`
- Create: `frontend/src/components/MessageContent.test.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/MessageContent.test.js`:

```javascript
import { render, screen } from "@testing-library/react";
import MessageContent from "./MessageContent";

test("renders markdown links to open in a new tab", () => {
  render(<MessageContent content={"Read the [guide](https://www.partselect.com/repair/)"} />);

  const link = screen.getByRole("link", { name: "guide" });
  expect(link).toHaveAttribute("href", "https://www.partselect.com/repair/");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/components/MessageContent.test.js
```

Expected: FAIL because the rendered `<a>` does not have `target` or `rel`.

- [ ] **Step 3: Implement the minimal link post-processing**

Replace `frontend/src/components/MessageContent.js` with:

```javascript
import React from "react";
import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

function addExternalLinkAttributes(html) {
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("a").forEach((link) => {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });
  return template.innerHTML;
}

export default function MessageContent({ content }) {
  if (!content) return null;
  const html = addExternalLinkAttributes(marked.parse(content));
  return (
    <div
      className="message-markdown"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/components/MessageContent.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MessageContent.js frontend/src/components/MessageContent.test.js
git commit -m "fix: open chat links in new tabs"
```

## Task 2: Add Expand Control and Five-Message Limit

**Files:**
- Modify: `frontend/src/components/ChatWidget.js`
- Modify: `frontend/src/components/ChatHeader.js`
- Modify: `frontend/src/components/ChatInput.js`
- Modify: `frontend/src/components/ChatWidget.css`
- Create: `frontend/src/components/ChatWidget.test.js`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ChatWidget.test.js`:

```javascript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatWidget from "./ChatWidget";
import { useSession } from "../hooks/useSession";
import { useChat } from "../hooks/useChat";
import { useCart } from "../hooks/useCart";

jest.mock("../hooks/useSession");
jest.mock("../hooks/useChat");
jest.mock("../hooks/useCart");

const send = jest.fn();
const startNewChat = jest.fn();

beforeEach(() => {
  send.mockClear();
  startNewChat.mockClear();
  useSession.mockReturnValue({
    sessionId: "session-1",
    applianceModel: "",
    applianceModelForApi: "",
    setApplianceModel: jest.fn(),
    ensureSession: jest.fn(),
    startNewChat,
  });
  useChat.mockReturnValue({
    messages: [{ role: "assistant", content: "Welcome" }],
    isLoading: false,
    send,
  });
  useCart.mockReturnValue({
    cart: { count: 0, items: [] },
    refreshCart: jest.fn(),
    removeItem: jest.fn(),
  });
});

function openWidget() {
  render(<ChatWidget />);
  fireEvent.click(screen.getByRole("button", { name: "Open chat" }));
}

function sendMessage(text) {
  const input = screen.getByPlaceholderText("Ask about parts, compatibility, installation...");
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

test("disables input after 5 user messages and asks for a new chat", () => {
  openWidget();

  for (let i = 1; i <= 5; i += 1) {
    sendMessage(`message ${i}`);
  }

  expect(send).toHaveBeenCalledTimes(5);
  expect(screen.getByText("Message limit reached. Start a new chat to continue.")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("Start a new chat to continue")).toBeDisabled();

  const disabledSendButton = screen.getByRole("button", { name: "Send" });
  expect(disabledSendButton).toBeDisabled();
});

test("new chat resets the message limit", async () => {
  startNewChat.mockResolvedValue(undefined);
  openWidget();

  for (let i = 1; i <= 5; i += 1) {
    sendMessage(`message ${i}`);
  }

  fireEvent.click(screen.getByRole("button", { name: "New chat" }));

  await waitFor(() => expect(startNewChat).toHaveBeenCalledTimes(1));
  expect(screen.queryByText("Message limit reached. Start a new chat to continue.")).not.toBeInTheDocument();
  expect(screen.getByPlaceholderText("Ask about parts, compatibility, installation...")).not.toBeDisabled();
});

test("expand button toggles the expanded panel class", () => {
  openWidget();

  const panel = screen.getByRole("dialog", { name: "PartSelect chat" });
  expect(panel).not.toHaveClass("expanded");

  fireEvent.click(screen.getByRole("button", { name: "Expand chat" }));
  expect(panel).toHaveClass("expanded");

  fireEvent.click(screen.getByRole("button", { name: "Collapse chat" }));
  expect(panel).not.toHaveClass("expanded");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/components/ChatWidget.test.js
```

Expected: FAIL because the message limit, expanded class, `dialog` role, and expand button do not exist yet.

- [ ] **Step 3: Update `ChatInput` for limit copy**

Replace `frontend/src/components/ChatInput.js` with:

```javascript
import React, { useState } from "react";

export default function ChatInput({ onSend, disabled, limitReached = false }) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (value.trim() && !limitReached) {
      onSend(value);
      setValue("");
    }
  };

  const placeholder = limitReached
    ? "Start a new chat to continue"
    : "Ask about parts, compatibility, installation...";

  return (
    <div style={{
      display: "flex", gap: 8, padding: "10px 12px",
      borderTop: "1px solid var(--partselect-border)", background: "#fff",
    }}>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
        }}
        placeholder={placeholder}
        disabled={disabled || limitReached}
        style={{
          flex: 1, padding: "9px 12px", border: "1px solid var(--partselect-border)",
          borderRadius: 20, fontSize: "0.9rem", outline: "none",
        }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || limitReached || !value.trim()}
        style={{
          padding: "9px 16px", background: "var(--partselect-teal)", color: "#fff",
          border: "none", borderRadius: 20, cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
        }}
      >
        Send
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Update `ChatHeader` with expand/collapse button**

Replace `frontend/src/components/ChatHeader.js` with:

```javascript
import React from "react";

export default function ChatHeader({
  onCartClick,
  onNewChat,
  cartCount,
  expanded = false,
  onToggleExpanded,
}) {
  return (
    <div style={{
      background: "var(--partselect-teal)", color: "#fff",
      padding: "14px 16px", display: "flex", justifyContent: "space-between",
      alignItems: "center", borderRadius: "12px 12px 0 0",
    }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: "1rem" }}>PartSelect</div>
        <div style={{ fontSize: "0.75rem", opacity: 0.85 }}>AI Assistant</div>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
      {onToggleExpanded && (
        <button
          type="button"
          onClick={onToggleExpanded}
          aria-label={expanded ? "Collapse chat" : "Expand chat"}
          title={expanded ? "Collapse chat" : "Expand chat"}
          style={{
            background: "rgba(255,255,255,0.2)", border: "none", borderRadius: 8,
            color: "#fff", padding: "6px 10px", cursor: "pointer", fontSize: "0.8rem",
          }}
        >
          {expanded ? "↙" : "↗"}
        </button>
      )}
      {onNewChat && (
        <button
          type="button"
          onClick={onNewChat}
          style={{
            background: "rgba(255,255,255,0.2)", border: "none", borderRadius: 8,
            color: "#fff", padding: "6px 10px", cursor: "pointer", fontSize: "0.8rem",
          }}
        >
          New chat
        </button>
      )}
      <button
        type="button"
        onClick={onCartClick}
        style={{
          background: "rgba(255,255,255,0.2)", border: "none", borderRadius: 8,
          color: "#fff", padding: "6px 12px", cursor: "pointer", fontSize: "0.85rem",
        }}
      >
        🛒 {cartCount > 0 ? cartCount : "Cart"}
      </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Update `ChatWidget` for expanded state and message limit**

Replace `frontend/src/components/ChatWidget.js` with:

```javascript
import React, { useState, useCallback, useEffect } from "react";
import "./ChatWidget.css";
import ChatHeader from "./ChatHeader";
import MessageList from "./MessageList";
import SuggestedQueries from "./SuggestedQueries";
import ModelInput from "./ModelInput";
import ChatInput from "./ChatInput";
import CartDrawer from "./CartDrawer";
import { useSession } from "../hooks/useSession";
import { useChat } from "../hooks/useChat";
import { useCart } from "../hooks/useCart";

const MAX_USER_MESSAGES = 5;

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [userMessageCount, setUserMessageCount] = useState(0);
  const {
    sessionId,
    applianceModel,
    applianceModelForApi,
    setApplianceModel,
    ensureSession,
    startNewChat,
  } = useSession();
  const { cart, refreshCart, removeItem } = useCart(sessionId);
  const [chatResetKey, setChatResetKey] = useState(0);

  const handleCartUpdate = useCallback(() => {
    refreshCart();
  }, [refreshCart]);

  const { messages, isLoading, send } = useChat({
    sessionId,
    applianceModel: applianceModelForApi,
    onCartUpdate: handleCartUpdate,
    resetKey: chatResetKey,
    resolveSessionId: ensureSession,
  });

  const [showSuggestions, setShowSuggestions] = useState(true);
  const limitReached = userMessageCount >= MAX_USER_MESSAGES;

  useEffect(() => {
    ensureSession();
  }, [ensureSession]);

  const handleNewChat = useCallback(async () => {
    await startNewChat();
    setChatResetKey((k) => k + 1);
    setShowSuggestions(true);
    setUserMessageCount(0);
    refreshCart();
  }, [startNewChat, refreshCart]);

  const handleSend = useCallback((text) => {
    if (limitReached) return;
    setShowSuggestions(false);
    setUserMessageCount((count) => count + 1);
    send(text);
  }, [limitReached, send]);

  const handleAddToCart = useCallback(async (psNumber) => {
    if (!sessionId) return;
    await send(`add ${psNumber} to cart`);
    refreshCart();
  }, [sessionId, send, refreshCart]);

  return (
    <>
      <button className="chat-fab" onClick={() => setOpen((o) => !o)} aria-label="Open chat">
        {open ? "✕" : "💬"}
      </button>

      {open && (
        <div
          className={`chat-panel${expanded ? " expanded" : ""}`}
          role="dialog"
          aria-label="PartSelect chat"
        >
          <ChatHeader
            onCartClick={() => { setCartOpen(true); refreshCart(); }}
            onNewChat={handleNewChat}
            cartCount={cart.count}
            expanded={expanded}
            onToggleExpanded={() => setExpanded((value) => !value)}
          />

          <MessageList
            messages={messages}
            isLoading={isLoading}
            onAddToCart={handleAddToCart}
          />

          {showSuggestions && messages.length <= 1 && !limitReached && (
            <SuggestedQueries onSelect={handleSend} />
          )}

          {limitReached && (
            <div className="chat-limit-notice">
              Message limit reached. Start a new chat to continue.
            </div>
          )}

          <ModelInput value={applianceModel} onChange={setApplianceModel} />

          <ChatInput onSend={handleSend} disabled={isLoading} limitReached={limitReached} />
        </div>
      )}

      {cartOpen && (
        <CartDrawer
          cart={cart}
          onClose={() => setCartOpen(false)}
          onRemove={async (ps) => { await removeItem(ps); }}
        />
      )}
    </>
  );
}
```

- [ ] **Step 6: Add CSS for expanded panel and limit notice**

Modify `frontend/src/components/ChatWidget.css` so it contains the existing rules plus these additions after `.chat-panel`:

```css
.chat-panel.expanded {
  width: min(760px, calc(100vw - 56px));
  height: min(760px, calc(100vh - 128px));
}

.chat-limit-notice {
  margin: 8px 12px;
  padding: 9px 12px;
  border: 1px solid var(--partselect-border);
  border-radius: 8px;
  background: #fff;
  color: #4b5563;
  font-size: 0.85rem;
  text-align: center;
}
```

Keep the existing mobile media query. The full-screen mobile panel should override both normal and expanded desktop dimensions.

- [ ] **Step 7: Run the tests to verify they pass**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/components/ChatWidget.test.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/ChatWidget.js frontend/src/components/ChatHeader.js frontend/src/components/ChatInput.js frontend/src/components/ChatWidget.css frontend/src/components/ChatWidget.test.js
git commit -m "feat: add expandable chat session limit"
```

## Task 3: Support Embeddable Mounting

**Files:**
- Modify: `frontend/src/index.js`
- Create: `frontend/src/index.test.js`

- [ ] **Step 1: Write the failing mount tests**

Create `frontend/src/index.test.js`:

```javascript
import ReactDOM from "react-dom/client";

jest.mock("react-dom/client", () => ({
  createRoot: jest.fn(() => ({ render: jest.fn() })),
}));

jest.mock("./reportWebVitals", () => jest.fn());
jest.mock("./App", () => function MockApp() { return <div>App demo</div>; });
jest.mock("./components/ChatWidget", () => function MockChatWidget() { return <div>Widget</div>; });

function loadIndexWithHtml(html) {
  document.body.innerHTML = html;
  jest.isolateModules(() => {
    require("./index");
  });
}

beforeEach(() => {
  ReactDOM.createRoot.mockClear();
});

test("mounts ChatWidget when an embed mount node is present", () => {
  loadIndexWithHtml('<div id="partselect-chat-widget"></div>');

  expect(ReactDOM.createRoot).toHaveBeenCalledWith(
    document.getElementById("partselect-chat-widget")
  );
});

test("falls back to the demo app root when no embed mount node is present", () => {
  loadIndexWithHtml('<div id="root"></div>');

  expect(ReactDOM.createRoot).toHaveBeenCalledWith(
    document.getElementById("root")
  );
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/index.test.js
```

Expected: the embed mount test FAILS because `index.js` only mounts `#root`.

- [ ] **Step 3: Update `index.js` with mount-node selection**

Replace `frontend/src/index.js` with:

```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ChatWidget from './components/ChatWidget';
import reportWebVitals from './reportWebVitals';

const embedRoot = document.getElementById('partselect-chat-widget');
const appRoot = document.getElementById('root');
const rootElement = embedRoot || appRoot;

if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      {embedRoot ? <ChatWidget /> : <App />}
    </React.StrictMode>
  );
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/index.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.js frontend/src/index.test.js
git commit -m "feat: support embeddable chat mount"
```

## Task 4: Document Widget Integration

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README documentation**

Add this section after the Architecture section and before Request flow in `README.md`:

````markdown
## Embeddable chat widget

The frontend is a floating chat widget that can run as the standalone local demo or be embedded into another web page.

For the local demo, open the normal React app at `http://localhost:3000`.

For an embedded page, include the built frontend CSS and JS assets from `frontend/build/asset-manifest.json` and add this mount point:

```html
<div id="partselect-chat-widget"></div>
<link rel="stylesheet" href="/static/css/main.<hash>.css">
<script defer src="/static/js/main.<hash>.js"></script>
```

When `#partselect-chat-widget` exists, the bundle mounts only the chat widget. When it is absent, the bundle uses the normal `#root` demo app mount.

The widget:

- Opens as a floating chat bubble.
- Includes an expand/collapse control for a larger desktop panel.
- Opens links from chat responses in a new tab.
- Allows up to 5 user messages per session, then asks the user to start a new chat.

Set `REACT_APP_API_URL` at build time if the backend is not available at `http://localhost:8000`.
````

- [ ] **Step 2: Review README diff**

Run:

```bash
git diff -- README.md
```

Expected: the diff only adds the embeddable widget documentation and does not rewrite unrelated README sections.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document embeddable chat widget"
```

## Task 5: Final Verification

**Files:**
- Verify frontend test and build behavior.

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false src/components/MessageContent.test.js src/components/ChatWidget.test.js src/index.test.js
```

Expected: all focused tests PASS.

- [ ] **Step 2: Run existing frontend tests**

Run:

```bash
cd frontend
npm test -- --runInBand --watchAll=false
```

Expected: all frontend tests PASS, including `src/lib/api.test.js`.

- [ ] **Step 3: Run production build**

Run:

```bash
cd frontend
npm run build
```

Expected: build completes successfully and produces `frontend/build`.

- [ ] **Step 4: Inspect final git status**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated worktree changes remain, or the working tree is clean if those were resolved separately. Do not revert unrelated changes.

- [ ] **Step 5: Commit any verification-only snapshot changes if needed**

If `npm run build` updates tracked build artifacts under `frontend/build`, commit only those build artifact changes:

```bash
git add frontend/build
git commit -m "build: update frontend widget assets"
```

If `frontend/build` has no tracked changes, skip this commit.
