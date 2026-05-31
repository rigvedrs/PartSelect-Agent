import React, { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import "./MessageBubble.css";

export default function MessageList({ messages, isLoading, onAddToCart }) {
  const endRef = useRef(null);
  const lastMsg = messages[messages.length - 1];
  const showTyping = isLoading && !(lastMsg?.streaming);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isLoading]);

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "12px 12px 0" }}>
      {messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} onAddToCart={onAddToCart} />
      ))}
      {showTyping && (
        <div className="bubble-row assistant">
          <div className="bubble assistant">
            <TypingIndicator />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
