"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import AuthModal from "@/components/auth-modal";

type AuthMode = "login" | "signup";

interface AuthModalContextValue {
  open: boolean;
  mode: AuthMode;
  openAuthModal: (mode?: AuthMode) => void;
  closeAuthModal: () => void;
  setMode: (m: AuthMode) => void;
}

const AuthModalContext = createContext<AuthModalContextValue | null>(null);

export function AuthModalProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<AuthMode>("login");

  const openAuthModal = useCallback((m: AuthMode = "login") => {
    setMode(m);
    setOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => setOpen(false), []);

  const value = useMemo<AuthModalContextValue>(
    () => ({ open, mode, openAuthModal, closeAuthModal, setMode }),
    [open, mode, openAuthModal, closeAuthModal],
  );

  return (
    <AuthModalContext.Provider value={value}>
      {children}
      <AuthModal
        open={open}
        mode={mode}
        onClose={closeAuthModal}
        onModeChange={setMode}
      />
    </AuthModalContext.Provider>
  );
}

export function useAuthModal(): AuthModalContextValue {
  const ctx = useContext(AuthModalContext);
  if (!ctx) {
    return {
      open: false,
      mode: "login",
      openAuthModal: () => {},
      closeAuthModal: () => {},
      setMode: () => {},
    };
  }
  return ctx;
}
