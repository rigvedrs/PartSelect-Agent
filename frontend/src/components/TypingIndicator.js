import React from "react";

export default function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 4, padding: "8px 12px", alignItems: "center" }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 8, height: 8, borderRadius: "50%",
            background: "var(--partselect-teal)",
            display: "inline-block",
            animation: `bounce 1.2s infinite ${i * 0.2}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  );
}
