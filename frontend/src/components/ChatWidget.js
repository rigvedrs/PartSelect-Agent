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
