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

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
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

  useEffect(() => {
    ensureSession();
  }, [ensureSession]);

  const handleNewChat = useCallback(async () => {
    await startNewChat();
    setChatResetKey((k) => k + 1);
    setShowSuggestions(true);
    refreshCart();
  }, [startNewChat, refreshCart]);

  const handleSend = useCallback((text) => {
    setShowSuggestions(false);
    send(text);
  }, [send]);

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
        <div className="chat-panel">
          <ChatHeader
            onCartClick={() => { setCartOpen(true); refreshCart(); }}
            onNewChat={handleNewChat}
            cartCount={cart.count}
          />

          <MessageList
            messages={messages}
            isLoading={isLoading}
            onAddToCart={handleAddToCart}
          />

          {showSuggestions && messages.length <= 1 && (
            <SuggestedQueries onSelect={handleSend} />
          )}

          <ModelInput value={applianceModel} onChange={setApplianceModel} />

          <ChatInput onSend={handleSend} disabled={isLoading} />
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
