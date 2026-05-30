const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

export async function createSession() {
  const res = await fetch(`${API_BASE}/api/session`, { method: "POST" });
  return res.json();
}

export async function sendMessage({ sessionId, message, applianceModel, stream = false }) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      appliance_model: applianceModel || null,
      stream,
    }),
  });
  return res;
}

export async function getCart(sessionId) {
  const res = await fetch(`${API_BASE}/api/cart/${sessionId}`);
  return res.json();
}

export async function removeCartItem(sessionId, psNumber) {
  const res = await fetch(`${API_BASE}/api/cart/${sessionId}/item/${psNumber}`, {
    method: "DELETE",
  });
  return res.json();
}
