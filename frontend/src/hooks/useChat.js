import { useState, useCallback, useEffect } from "react";
import { sendMessage } from "../lib/api";

const WELCOME = {
  role: "assistant",
  content: "Hi! I can help you find refrigerator and dishwasher parts, check compatibility, get installation instructions, and troubleshoot issues. How can I help you today?",
};

export function useChat({ sessionId, applianceModel, onCartUpdate, resetKey = 0, resolveSessionId }) {
  const [messages, setMessages] = useState([WELCOME]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setMessages([WELCOME]);
  }, [resetKey]);

  const addMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const send = useCallback(async (text) => {
    if (!text.trim()) return;
    const sid = sessionId || (resolveSessionId ? await resolveSessionId() : "");
    if (!sid) return;

    addMessage({ role: "user", content: text });
    setIsLoading(true);

    try {
      const res = await sendMessage({ sessionId: sid, message: text, applianceModel, stream: false });
      const data = await res.json();

      const assistantMsg = {
        role: "assistant",
        content: data.text || "",
        parts: data.parts,
        installation_steps: data.installation_steps,
        compatibility: data.compatibility,
        out_of_scope: data.out_of_scope,
      };
      addMessage(assistantMsg);

      if (data.cart_update && onCartUpdate) {
        onCartUpdate(data.cart_update);
      }
    } catch (err) {
      addMessage({ role: "assistant", content: "Sorry, something went wrong. Please try again." });
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, applianceModel, addMessage, onCartUpdate, resolveSessionId]);

  return { messages, isLoading, send };
}
