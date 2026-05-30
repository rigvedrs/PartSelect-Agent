import React from "react";
import "./CartDrawer.css";

export default function CartDrawer({ cart, onClose, onRemove }) {
  return (
    <div className="cart-overlay" onClick={onClose}>
      <div className="cart-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="cart-drawer-header">
          <span>🛒 Your Cart ({cart.count})</span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#fff", fontSize: "1.2rem", cursor: "pointer" }}>✕</button>
        </div>
        <div className="cart-items">
          {cart.items.length === 0 ? (
            <p style={{ color: "#888", textAlign: "center", marginTop: 32 }}>Your cart is empty</p>
          ) : (
            cart.items.map((item) => (
              <div key={item.ps_number} className="cart-item">
                <div>
                  <div style={{ fontWeight: 600 }}>{item.name}</div>
                  <div style={{ color: "#888" }}>PS# {item.ps_number} × {item.quantity}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 700, color: "var(--partselect-teal)" }}>
                    ${((item.price || 0) * item.quantity).toFixed(2)}
                  </span>
                  <button
                    onClick={() => onRemove(item.ps_number)}
                    style={{ background: "none", border: "none", color: "#e53935", cursor: "pointer", fontSize: "1rem" }}
                  >✕</button>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="cart-footer">
          <div className="cart-total">Total: ${cart.total.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}
