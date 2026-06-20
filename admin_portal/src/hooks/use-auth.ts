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
import axios from 'axios';
import {
  getAccessToken,
  getRefreshToken,
  setTokens as storeTokens,
  clearTokens,
  decodeJwtPayload,
} from '@/lib/auth';
import type { AuthContextValue, TokenPair } from '@/types/auth';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Extract admin email from a JWT access token payload.
 */
function extractEmail(token: string): string | null {
  const payload = decodeJwtPayload(token);
  if (!payload) return null;
  // Try common JWT claims for email
  if (typeof payload.email === 'string') return payload.email;
  if (typeof payload.sub === 'string' && payload.sub.includes('@')) return payload.sub;
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [adminEmail, setAdminEmail] = useState<string | null>(null);
  const navigate = useNavigate();

  // On mount, check if we have a valid token already in memory
  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      const email = extractEmail(token);
      setAdminEmail(email);
      setIsAuthenticated(true);
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const response = await axios.post<TokenPair>(
        `${API_BASE}/api/v1/auth/login`,
        { email, password },
      );

      const { access_token, refresh_token } = response.data;
      storeTokens(access_token, refresh_token);

      const decoded = extractEmail(access_token);
      setAdminEmail(decoded);
      setIsAuthenticated(true);
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    const token = getAccessToken();
    try {
      await axios.post(
        `${API_BASE}/api/v1/auth/logout`,
        null,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        },
      );
    } catch {
      // Best-effort: still clear local state even if logout API call fails
    }

    clearTokens();
    setAdminEmail(null);
    setIsAuthenticated(false);
    navigate('/login');
  }, [navigate]);

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    const currentRefresh = getRefreshToken();
    if (!currentRefresh) return null;

    try {
      const response = await axios.post<TokenPair>(
        `${API_BASE}/api/v1/auth/refresh`,
        { refresh_token: currentRefresh },
      );

      const { access_token, refresh_token } = response.data;
      storeTokens(access_token, refresh_token);

      const email = extractEmail(access_token);
      setAdminEmail(email);
      setIsAuthenticated(true);

      return access_token;
    } catch {
      // Refresh failed — clear state and redirect to login
      clearTokens();
      setAdminEmail(null);
      setIsAuthenticated(false);
      navigate('/login');
      return null;
    }
  }, [navigate]);

  // Expose refreshAccessToken on the module for the HTTP client interceptor to use
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__authRefresh = refreshAccessToken;
    return () => {
      delete (window as unknown as Record<string, unknown>).__authRefresh;
    };
  }, [refreshAccessToken]);

  const contextValue: AuthContextValue = {
    isAuthenticated,
    isLoading,
    adminEmail,
    login,
    logout,
    getAccessToken,
    setTokens: storeTokens,
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
