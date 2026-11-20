import { create } from "zustand";
import type {
  BootstrapDestination,
  BootstrapResult,
  SessionSummary,
} from "../../electron/shared/types";

type SessionStatus = "loading" | "anonymous" | "authenticated";

export interface SessionNotice {
  message?: string;
  code?: string;
  portalUrl?: string;
}

interface SessionState {
  status: SessionStatus;
  session: SessionSummary | null;
  destination: BootstrapDestination | null;
  notice: SessionNotice | null;
  applyBootstrap: (result: BootstrapResult) => void;
  setSession: (session: SessionSummary) => void;
  setNotice: (notice: SessionNotice | null) => void;
  clear: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  status: "loading",
  session: null,
  destination: null,
  notice: null,

  applyBootstrap: (result) => {
    const notice: SessionNotice = {
      message: result.message,
      code: result.code,
      portalUrl: result.portalUrl,
    };
    if (result.destination === "login" || !result.session) {
      set({
        status: "anonymous",
        session: null,
        destination: "login",
        notice,
      });
      return;
    }
    set({
      status: "authenticated",
      session: result.session,
      destination: result.destination,
      notice,
    });
  },

  setSession: (session) =>
    set({
      status: "authenticated",
      session,
      destination: "app",
      notice: null,
    }),

  setNotice: (notice) => set({ notice }),

  clear: () =>
    set({
      status: "anonymous",
      session: null,
      destination: "login",
      notice: null,
    }),
}));
