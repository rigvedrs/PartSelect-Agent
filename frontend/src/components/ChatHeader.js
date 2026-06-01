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
