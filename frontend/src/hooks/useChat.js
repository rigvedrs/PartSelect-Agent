import { useState, useCallback } from "react";
import { sendMessage } from "../lib/api";

export function useChat({ sessionId, applianceModel, onCartUpdate }) {
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Hi! I can help you find refrigerator and dishwasher parts, check compatibility, get installation instructions, and troubleshoot issues. How can I help you today?",
  }]);
  const [isLoading, setIsLoading] = useState(false);

  const addMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const send = useCallback(async (text) => {
    if (!text.trim() || !sessionId) return;

    addMessage({ role: "user", content: text });
    setIsLoading(true);

    try {
      const res = await sendMessage({ sessionId, message: text, applianceModel, stream: false });
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
  }, [sessionId, applianceModel, addMessage, onCartUpdate]);

  return { messages, isLoading, send };
}
