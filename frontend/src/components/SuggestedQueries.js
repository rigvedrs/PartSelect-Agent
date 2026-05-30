import React from "react";

const SUGGESTIONS = [
  "How do I install PS11752778?",
  "Is PS11752778 compatible with WDT780SAEM1?",
  "My ice maker is not working",
  "Dishwasher not draining",
  "Find water filter for my fridge",
];

export default function SuggestedQueries({ onSelect }) {
  return (
    <div style={{ padding: "8px 12px", display: "flex", flexWrap: "wrap", gap: 6 }}>
      {SUGGESTIONS.map((q) => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          style={{
            padding: "4px 10px", borderRadius: 16, border: "1px solid var(--partselect-teal)",
            background: "var(--partselect-teal-light)", color: "var(--partselect-teal)",
            cursor: "pointer", fontSize: "0.78rem", fontWeight: 500,
          }}
        >
          {q}
        </button>
      ))}
    </div>
  );
}
