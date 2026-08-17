'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import {
  fetchMusicUser,
  loginMusicUser,
  logoutMusicUser,
  registerMusicUser,
  type MusicUser,
} from '@/lib/auth-api';

type AuthState = {
  user: MusicUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string, turnstileToken?: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    display_name: string;
    cf_turnstile_response?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MusicUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await fetchMusicUser());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      refresh,
      async login(email, password, turnstileToken) {
        await loginMusicUser({ email, password, cf_turnstile_response: turnstileToken });
        await refresh();
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
        }
      },
    }),
    [user, loading, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
