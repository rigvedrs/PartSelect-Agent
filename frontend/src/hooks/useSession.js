import { useState, useCallback } from "react";
import { createSession } from "../lib/api";

export function useSession() {
  const [sessionId, setSessionId] = useState("");
  const [applianceModel, setApplianceModelState] = useState("");
  const [modelTouched, setModelTouched] = useState(false);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const { session_id } = await createSession();
    setSessionId(session_id);
    return session_id;
  }, [sessionId]);

  const startNewChat = useCallback(async () => {
    const { session_id } = await createSession();
    setSessionId(session_id);
    setApplianceModelState("");
    setModelTouched(false);
    return session_id;
  }, []);

  const setApplianceModel = useCallback((model) => {
    setApplianceModelState(model);
    setModelTouched(true);
  }, []);

  /** Only send model to API when user typed in the model field */
  const applianceModelForApi = modelTouched && applianceModel.trim()
    ? applianceModel.trim()
    : null;

  return {
    sessionId,
    applianceModel,
    applianceModelForApi,
    setApplianceModel,
    ensureSession,
    startNewChat,
  };
}
