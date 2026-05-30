import { useState, useEffect } from "react";
import { createSession } from "../lib/api";

export function useSession() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem("ps_session_id") || "");
  const [applianceModel, setApplianceModelState] = useState(
    () => localStorage.getItem("ps_appliance_model") || ""
  );

  useEffect(() => {
    if (!sessionId) {
      createSession().then(({ session_id }) => {
        setSessionId(session_id);
        localStorage.setItem("ps_session_id", session_id);
      });
    }
  }, [sessionId]);

  const setApplianceModel = (model) => {
    setApplianceModelState(model);
    localStorage.setItem("ps_appliance_model", model);
  };

  return { sessionId, applianceModel, setApplianceModel };
}
