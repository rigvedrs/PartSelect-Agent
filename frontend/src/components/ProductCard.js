import React from "react";
import "./ProductCard.css";

export default function ProductCard({ part, onAddToCart }) {
  if (!part) return null;
  return (
    <div className="product-card">
      {part.image_url && (
        <img
          src={part.image_url}
          alt={part.name}
          onError={(e) => { e.currentTarget.style.display = "none"; }}
        />
      )}
      <div className="part-name">{part.name}</div>
      <div className="part-meta">PS# {part.ps_number}{part.brand ? ` · ${part.brand}` : ""}</div>
      {part.price != null && (
        <div className="part-price">${Number(part.price).toFixed(2)}</div>
      )}
      {part.stock_status && (
        <span className="stock-badge">{part.stock_status}</span>
      )}
      {onAddToCart && (
        <button className="add-to-cart-btn" onClick={() => onAddToCart(part.ps_number)}>
          Add to Cart
        </button>
      )}
      {part.product_url && (
        <a className="view-link" href={part.product_url} target="_blank" rel="noreferrer">
          View on PartSelect ↗
        </a>
      )}
    </div>
  );
}
