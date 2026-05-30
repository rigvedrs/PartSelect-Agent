import React, { useState } from "react";

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (value.trim()) {
      onSend(value);
      setValue("");
    }
  };

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
        placeholder="Ask about parts, compatibility, installation..."
        disabled={disabled}
        style={{
          flex: 1, padding: "9px 12px", border: "1px solid var(--partselect-border)",
          borderRadius: 20, fontSize: "0.9rem", outline: "none",
        }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
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
