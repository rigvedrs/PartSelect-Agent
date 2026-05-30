import React from "react";
import "./MessageBubble.css";
import ProductCard from "./ProductCard";
import InstallationGuide from "./InstallationGuide";
import CompatibilityBadge from "./CompatibilityBadge";

export default function MessageBubble({ message, onAddToCart }) {
  const { role, content, parts, installation_steps, compatibility, out_of_scope } = message;

  return (
    <div className={`bubble-row ${role}`}>
      <div className={`bubble ${role}`}>
        {content && <div>{content}</div>}

        {compatibility && <CompatibilityBadge result={compatibility} />}

        {installation_steps && installation_steps.length > 0 && (
          <InstallationGuide steps={installation_steps} />
        )}

        {parts && parts.length > 0 && (
          <div className="bubble-cards">
            {parts.map((p) => (
              <ProductCard key={p.ps_number} part={p} onAddToCart={onAddToCart} />
            ))}
          </div>
        )}

        {out_of_scope && (
          <div style={{ fontSize: "0.8rem", color: "#888", marginTop: 4, fontStyle: "italic" }}>
            Out of scope
          </div>
        )}
      </div>
    </div>
  );
}
