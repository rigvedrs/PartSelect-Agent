import React from "react";
import "./InstallationGuide.css";

export default function InstallationGuide({ steps }) {
  if (!steps || steps.length === 0) return null;
  return (
    <div className="install-guide">
      <h4>Installation Steps</h4>
      <ol className="install-steps">
        {steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
    </div>
  );
}
