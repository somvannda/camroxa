import {
  createContext,
  createElement,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/lib/http-client';
import { clearTokens, setTokens } from '@/lib/auth';
import type { AuthContextValue, TokenPair } from '@/types/auth';

const AuthContext = createContext<AuthContextValue | null>(null);
type AdminSession = {
  email: string;
  role: string;
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [adminEmail, setAdminEmail] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchAdminSession = useCallback(async (): Promise<AdminSession | null> => {
    try {
      const response = await apiClient.get<AdminSession>('/api/v3/users/me');
      if (response.data.role !== 'admin') {
        await apiClient.post('/api/v3/auth/logout').catch(() => undefined);
        clearTokens();
        return null;
      }
      return response.data;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function initializeAuth() {
      const session = await fetchAdminSession();
      if (cancelled) return;
      setAdminEmail(session?.email ?? null);
      setIsAuthenticated(Boolean(session));
      setIsLoading(false);
    }

    void initializeAuth();

    return () => {
      cancelled = true;
    };
  }, [fetchAdminSession]);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const { data } = await apiClient.post<TokenPair>('/api/v3/auth/login', {
        email,
        password,
      });
      setTokens(data.access_token, data.refresh_token);

      const session = await fetchAdminSession();
      if (!session) {
        clearTokens();
        throw new Error('Admin access is required for this portal.');
      }
      setAdminEmail(session.email);
      setIsAuthenticated(true);
    },
    [fetchAdminSession],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiClient.post('/api/v3/auth/logout');
    } catch {
      // Best-effort: still clear local state even if logout API call fails
    }

    clearTokens();
    setAdminEmail(null);
    setIsAuthenticated(false);
    navigate('/login');
  }, [navigate]);

  const contextValue: AuthContextValue = {
    isAuthenticated,
    isLoading,
    adminEmail,
    login,
    logout,
  };

  return createElement(AuthContext.Provider, { value: contextValue }, children);
}

/**
 * Hook to access the auth context. Must be used within an AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
