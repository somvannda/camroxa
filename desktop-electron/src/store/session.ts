import { create } from "zustand";
import type { SessionSummary } from "../../electron/shared/types";

type SessionStatus = "loading" | "anonymous" | "authenticated";

interface SessionState {
  status: SessionStatus;
  session: SessionSummary | null;
  setSession: (session: SessionSummary) => void;
  clear: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  status: "loading",
  session: null,
  setSession: (session) => set({ status: "authenticated", session }),
  clear: () => set({ status: "anonymous", session: null }),
}));
