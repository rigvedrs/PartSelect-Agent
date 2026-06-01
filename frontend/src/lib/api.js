const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const SESSION_STORAGE_KEY = "partselect_session_id";

export function getStoredSessionId() {
  try {
    return localStorage.getItem(SESSION_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function storeSessionId(sessionId) {
  try {
    if (sessionId) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {
    /* ignore */
  }
}

export async function createSession() {
  const res = await fetch(`${API_BASE}/api/session`, { method: "POST" });
  const data = await res.json();
  storeSessionId(data.session_id);
  return data;
}

export async function getChatHistory(sessionId) {
  const res = await fetch(`${API_BASE}/api/session/${sessionId}/messages`);
  if (res.status === 404) {
    return { session_id: sessionId, messages: [] };
  }
  if (!res.ok) {
    throw new Error(`Failed to load chat history (${res.status})`);
  }
  return res.json();
}

export function parseSseBlock(block) {
  const line = block.trim();
  if (!line.startsWith("data:")) return null;
  try {
    return JSON.parse(line.slice(5).trim());
  } catch {
    return null;
  }
}

/**
 * POST /api/chat with SSE. Invokes onToken for each text chunk and onDone with the final payload.
 */
export async function sendMessageStream({
  sessionId,
  message,
  applianceModel,
  onToken,
  onStage,
  onDone,
  signal,
}) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      appliance_model: applianceModel || null,
      stream: true,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("text/event-stream") || !res.body) {
    const data = await res.json();
    onDone?.(data);
    return data;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const data = parseSseBlock(part);
      if (!data) continue;
      if (data.stage) onStage?.(data.stage);
      if (data.token) onToken?.(data.token);
      if (data.done) {
        finalPayload = data;
        onDone?.(data);
      }
    }
  }

  if (buffer.trim()) {
    const data = parseSseBlock(buffer);
    if (data?.stage) onStage?.(data.stage);
    if (data?.token) onToken?.(data.token);
    if (data?.done) {
      finalPayload = data;
      onDone?.(data);
    }
  }

  return finalPayload;
}

/** @deprecated Use sendMessageStream — kept for tests */
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
