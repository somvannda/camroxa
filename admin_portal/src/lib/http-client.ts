import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios';
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
} from '@/lib/auth';

// --- Axios instance ---

const apiClient = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000',
});

// --- Helpers ---

/** Endpoints that should NOT receive the Authorization header. */
const PUBLIC_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/register'];

function isPublicEndpoint(url: string | undefined): boolean {
  if (!url) return false;
  return PUBLIC_ENDPOINTS.some((ep) => url.includes(ep));
}

// --- Request interceptor ---

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!isPublicEndpoint(config.url)) {
      const token = getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error),
);

// --- Response interceptor (401 refresh logic) ---

/** Flag to prevent infinite refresh loops. */
let isRefreshing = false;

/**
 * Queue of requests that arrived while a token refresh was in progress.
 * They will be retried (or rejected) once the refresh completes.
 */
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

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    // Only handle 401 and avoid retrying public or already-retried requests
    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      isPublicEndpoint(originalRequest.url)
    ) {
      return Promise.reject(error);
    }

    // If a refresh is already in flight, queue this request
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingRequests.push({ resolve, reject });
      }).then((newToken) => {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const refresh = getRefreshToken();
      if (!refresh) {
        throw new Error('No refresh token available');
      }

      const { data } = await apiClient.post<{
        access_token: string;
        refresh_token: string;
      }>('/api/v1/auth/refresh', { refresh_token: refresh });

      setTokens(data.access_token, data.refresh_token);
      processPendingRequests(data.access_token);

      // Retry the original request with the new token
      originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      processPendingRequests(null, refreshError);
      clearTokens();
      // Redirect to login page
      window.location.href = '/login';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

// --- Typed HTTP client methods ---

export interface HttpClient {
  get<T>(url: string, params?: Record<string, unknown>): Promise<T>;
  post<T>(url: string, data?: unknown): Promise<T>;
  put<T>(url: string, data?: unknown): Promise<T>;
  patch<T>(url: string, data?: unknown): Promise<T>;
  delete<T>(url: string): Promise<T>;
}

async function get<T>(
  url: string,
  params?: Record<string, unknown>,
): Promise<T> {
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

/** Export the raw Axios instance for advanced use cases (e.g., file uploads). */
export { apiClient };

/**
 * Reset interceptor state — useful for testing.
 * @internal
 */
export function _resetRefreshState(): void {
  isRefreshing = false;
  pendingRequests = [];
}
