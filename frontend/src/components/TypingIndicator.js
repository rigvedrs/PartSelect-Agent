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
