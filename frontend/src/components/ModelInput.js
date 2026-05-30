import React from "react";

export default function ModelInput({ value, onChange }) {
  return (
    <div style={{ padding: "8px 12px", borderTop: "1px solid var(--partselect-border)", background: "#fafafa" }}>
      <label style={{ fontSize: "0.75rem", color: "#666", display: "block", marginBottom: 4 }}>
        Your appliance model (optional):
      </label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. WDT780SAEM1"
        style={{
          width: "100%", padding: "6px 10px", border: "1px solid var(--partselect-border)",
          borderRadius: 6, fontSize: "0.85rem", outline: "none",
        }}
      />
    </div>
  );
}
