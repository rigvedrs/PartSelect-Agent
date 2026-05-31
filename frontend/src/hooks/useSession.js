import { useState, useCallback, useEffect } from "react";
import { createSession, getStoredSessionId, storeSessionId } from "../lib/api";

export function useSession() {
  const [sessionId, setSessionIdState] = useState(() => getStoredSessionId());
  const [applianceModel, setApplianceModelState] = useState("");
  const [modelTouched, setModelTouched] = useState(false);

  const setSessionId = useCallback((id) => {
    setSessionIdState(id);
    storeSessionId(id);
  }, []);

  const ensureSession = useCallback(async () => {
    if (sessionId) return sessionId;
    const { session_id } = await createSession();
    setSessionId(session_id);
    return session_id;
  }, [sessionId, setSessionId]);

  const startNewChat = useCallback(async () => {
    const { session_id } = await createSession();
    setSessionId(session_id);
    setApplianceModelState("");
    setModelTouched(false);
    return session_id;
  }, [setSessionId]);

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
