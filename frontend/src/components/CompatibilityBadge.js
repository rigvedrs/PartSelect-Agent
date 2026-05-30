import React from "react";
import "./CompatibilityBadge.css";

export default function CompatibilityBadge({ result }) {
  if (!result) return null;
  return (
    <div>
      <div className={`compat-badge ${result.compatible ? "compatible" : "not-compatible"}`}>
        {result.compatible ? "✓ Compatible" : "✗ Not Compatible"}
      </div>
      {result.reason && <div className="compat-reason">{result.reason}</div>}
    </div>
  );
}
