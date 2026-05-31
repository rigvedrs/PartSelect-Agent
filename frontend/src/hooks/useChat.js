import { useState, useCallback, useEffect, useRef } from "react";
import { sendMessageStream, getChatHistory } from "../lib/api";

export const WELCOME = {
  role: "assistant",
  content: "Hi! I can help you find refrigerator and dishwasher parts, check compatibility, get installation instructions, and troubleshoot issues. How can I help you today?",
};

function assistantFromPayload(data) {
  return {
    role: "assistant",
    content: data.text || "",
    parts: data.parts,
    installation_steps: data.installation_steps,
    compatibility: data.compatibility,
    out_of_scope: data.out_of_scope,
    source: data.source,
    streaming: false,
  };
}

export function useChat({ sessionId, applianceModel, onCartUpdate, resetKey = 0, resolveSessionId }) {
  const [messages, setMessages] = useState([WELCOME]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const abortRef = useRef(null);

  useEffect(() => {
    if (resetKey === 0) return;
    setMessages([WELCOME]);
    setHistoryLoaded(false);
  }, [resetKey]);

  useEffect(() => {
    if (!sessionId) {
      setHistoryLoaded(true);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const { messages: stored } = await getChatHistory(sessionId);
        if (cancelled) return;
        if (stored && stored.length > 0) {
          setMessages(stored.map((m) => ({ ...m, streaming: false })));
        } else {
          setMessages([WELCOME]);
        }
      } catch {
        if (!cancelled) setMessages([WELCOME]);
      } finally {
        if (!cancelled) setHistoryLoaded(true);
      }
    })();

    return () => { cancelled = true; };
  }, [sessionId, resetKey]);

  const send = useCallback(async (text) => {
    if (!text.trim()) return;
    const sid = sessionId || (resolveSessionId ? await resolveSessionId() : "");
    if (!sid) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", streaming: true },
    ]);
    setIsLoading(true);

    try {
      await sendMessageStream({
        sessionId: sid,
        message: text,
        applianceModel,
        signal: controller.signal,
        onToken: (token) => {
          setIsLoading(false);
          setMessages((prev) => {
            if (prev.length === 0) return prev;
            const next = [...prev];
            const idx = next.length - 1;
            next[idx] = {
              ...next[idx],
              content: (next[idx].content || "") + token,
              streaming: true,
            };
            return next;
          });
        },
        onDone: (data) => {
          setMessages((prev) => {
            if (prev.length === 0) return prev;
            const next = [...prev];
            next[next.length - 1] = assistantFromPayload(data);
            return next;
          });
          if (data.cart_update && onCartUpdate) {
            onCartUpdate(data.cart_update);
          }
        },
      });
    } catch (err) {
      if (err.name === "AbortError") return;
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          streaming: false,
        };
        return next;
      });
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  }, [sessionId, applianceModel, onCartUpdate, resolveSessionId]);

  return { messages, isLoading, send, historyLoaded };
}
