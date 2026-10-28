"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  fetchCreditSummary,
  fetchMusicUser,
  loginMusicUser,
  logoutMusicUser,
  registerMusicUser,
  type MusicUser,
} from "@/lib/auth-api";

type AuthState = {
  user: MusicUser | null;
  credits: number | null;
  creditExpiry: string | null;
  creditAllowance: number | null;
  creditIsFree: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (
    email: string,
    password: string,
    turnstileToken?: string,
    remember?: boolean
  ) => Promise<MusicUser | null>;
  register: (input: {
    email: string;
    password: string;
    display_name: string;
    invitation_code?: string;
    referral_code?: string;
    cf_turnstile_response?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MusicUser | null>(null);
  const [credits, setCredits] = useState<number | null>(null);
  const [creditExpiry, setCreditExpiry] = useState<string | null>(null);
  const [creditAllowance, setCreditAllowance] = useState<number | null>(null);
  const [creditIsFree, setCreditIsFree] = useState(true);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const nextUser = await fetchMusicUser();
      setUser(nextUser);
      if (nextUser) {
        const summary = await fetchCreditSummary();
        setCredits(summary?.total ?? nextUser.credit_balance ?? null);
        setCreditExpiry(summary?.expiresAt ?? null);
        setCreditAllowance(summary?.monthlyCredits ?? null);
        setCreditIsFree(summary?.isFree ?? true);
      } else {
        setCredits(null);
        setCreditExpiry(null);
        setCreditAllowance(null);
        setCreditIsFree(true);
      }
    } catch {
      // Keep the last known state on transient network/5xx failures.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    document.body.dataset.auth = user ? "in" : "out";
  }, [user]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      credits,
      creditExpiry,
      creditAllowance,
      creditIsFree,
      loading,
      refresh,
      async login(email, password, turnstileToken, remember = false) {
        await loginMusicUser({
          email,
          password,
          remember,
          cf_turnstile_response: turnstileToken,
        });
        const nextUser = await fetchMusicUser();
        setUser(nextUser);
        if (nextUser) {
          const summary = await fetchCreditSummary();
          setCredits(summary?.total ?? nextUser.credit_balance ?? null);
          setCreditExpiry(summary?.expiresAt ?? null);
          setCreditAllowance(summary?.monthlyCredits ?? null);
          setCreditIsFree(summary?.isFree ?? true);
        } else {
          setCredits(null);
          setCreditExpiry(null);
          setCreditAllowance(null);
          setCreditIsFree(true);
        }
        return nextUser;
      },
      async register(input) {
        await registerMusicUser(input);
        await refresh();
      },
      async logout() {
        try {
          await logoutMusicUser();
        } finally {
          setUser(null);
          setCredits(null);
          setCreditExpiry(null);
          setCreditAllowance(null);
          setCreditIsFree(true);
          document.body.dataset.auth = "out";
        }
      },
    }),
    [user, credits, creditExpiry, creditAllowance, creditIsFree, loading, refresh]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
