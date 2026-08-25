import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios';
import { resolveApiBaseUrl } from '@/lib/api-base';
import { clearTokens, getAccessToken, setTokens } from '@/lib/auth';

const apiClient = axios.create({
  baseURL: resolveApiBaseUrl(),
  withCredentials: true,
});

const ADMIN_HEADERS = {
  'X-Portal-Context': 'admin',
} as const;

/** Endpoints that should NOT receive the Authorization header. */
const PUBLIC_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/register'];

function isPublicEndpoint(url: string | undefined): boolean {
  if (!url) return false;
  return PUBLIC_ENDPOINTS.some((ep) => url.includes(ep));
}

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    config.withCredentials = true;
    const headers = config.headers ?? new axios.AxiosHeaders();
    if (typeof headers.set === 'function') {
      headers.set('X-Portal-Context', 'admin');
      const token = getAccessToken();
      if (token && !isPublicEndpoint(config.url)) {
        headers.set('Authorization', `Bearer ${token}`);
      }
    } else {
      config.headers = new axios.AxiosHeaders({
        ...(config.headers ?? {}),
        ...ADMIN_HEADERS,
      });
    }
    config.headers = headers;
    return config;
  },
  (error: AxiosError) => Promise.reject(error),
);

let isRefreshing = false;
let pendingRequests: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processPendingRequests(token: string | null, error?: unknown): void {
  pendingRequests.forEach(({ resolve, reject }) => {
    if (token) {
      resolve(token);
    } else {
      reject(error);
    }
  });
  pendingRequests = [];
}

async function refreshAccessToken(): Promise<string> {
  if (isRefreshing) {
    return new Promise<string>((resolve, reject) => {
      pendingRequests.push({ resolve, reject });
    });
  }

  isRefreshing = true;
  try {
    const { data } = await apiClient.post<{
      access_token: string;
      refresh_token: string;
    }>('/api/v3/auth/refresh', {});

    setTokens(data.access_token, data.refresh_token);
    processPendingRequests(data.access_token);
    return data.access_token;
  } catch (refreshError) {
    processPendingRequests(null, refreshError);
    clearTokens();
    window.location.href = '/login';
    throw refreshError;
  } finally {
    isRefreshing = false;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    if (error.response?.status === 403 && originalRequest?.url?.includes('/api/v3/admin/')) {
      clearTokens();
      window.location.href = '/login';
      return Promise.reject(error);
    }

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      isPublicEndpoint(originalRequest.url)
    ) {
      return Promise.reject(error);
    }

    // No session yet (login page bootstrap): do not spam /auth/refresh.
    if (!getAccessToken()) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      await refreshAccessToken();
      return apiClient(originalRequest);
    } catch (refreshError) {
      return Promise.reject(refreshError);
    }
  },
);

export interface HttpClient {
  get<T>(url: string, params?: Record<string, unknown>): Promise<T>;
  post<T>(url: string, data?: unknown): Promise<T>;
  put<T>(url: string, data?: unknown): Promise<T>;
  patch<T>(url: string, data?: unknown): Promise<T>;
  delete<T>(url: string): Promise<T>;
}

async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await apiClient.get<T>(url, { params });
  return response.data;
}

async function post<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.post<T>(url, data);
  return response.data;
}

async function put<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.put<T>(url, data);
  return response.data;
}

async function patch<T>(url: string, data?: unknown): Promise<T> {
  const response = await apiClient.patch<T>(url, data);
  return response.data;
}

async function del<T>(url: string): Promise<T> {
  const response = await apiClient.delete<T>(url);
  return response.data;
}

const httpClient: HttpClient = { get, post, put, patch, delete: del };

export default httpClient;

export { apiClient };

export function _resetRefreshState(): void {
  isRefreshing = false;
  pendingRequests = [];
}
