import { logger } from "./logger";
import { sessionStore } from "./session";
import type { ApiRequest, ApiResponse, AuthTokens, SessionSummary } from "../shared/types";

const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly detail?: unknown,
    public readonly requestId?: string,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

function apiBaseUrl(): string {
  return (
    process.env.CAMXORA_API_BASE_URL?.replace(/\/+$/, "") ??
    "http://127.0.0.1:8000/api/v1"
  );
}

function buildUrl(request: ApiRequest): string {
  const path = request.path.startsWith("/") ? request.path : `/${request.path}`;
  const url = new URL(`${apiBaseUrl()}${path}`);
  for (const [key, value] of Object.entries(request.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  return url.toString();
}

function parseBody(text: string, contentType: string | null): unknown {
  if (!text) return null;
  if (contentType?.includes("application/json")) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return text;
}

function headersFor(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Camxora-Client": "desktop",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const tokens = sessionStore.load();
  if (!tokens?.refreshToken) return false;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${apiBaseUrl()}/auth/refresh`, {
        method: "POST",
        headers: {
          ...headersFor(null),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: tokens.refreshToken }),
        signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
      });
      if (!response.ok) {
        logger.warn("session refresh rejected", { status: response.status });
        return false;
      }
      const data = (await response.json()) as {
        access_token?: string;
        refresh_token?: string;
        expires_in?: number;
      };
      if (!data.access_token || !data.refresh_token) return false;
      sessionStore.save({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        expiresAt: Date.now() + (data.expires_in ?? 3600) * 1000,
      });
      logger.info("session refreshed");
      return true;
    } catch (error) {
      logger.warn("session refresh failed", { error: String(error) });
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function send(request: ApiRequest, token: string | null): Promise<Response> {
  const timeout = request.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  return fetch(buildUrl(request), {
    method: request.method,
    headers: {
      ...headersFor(token),
      ...(request.body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: request.body === undefined ? undefined : JSON.stringify(request.body),
    signal: AbortSignal.timeout(timeout),
  });
}

export async function apiRequest(request: ApiRequest): Promise<ApiResponse> {
  const requiresAuth = request.auth !== false;
  let tokens = requiresAuth ? sessionStore.load() : null;

  if (requiresAuth && !tokens?.accessToken) {
    throw new ApiClientError(401, "UNAUTHORIZED", "Sign in to continue.", undefined, undefined, false);
  }

  let response: Response;
  try {
    response = await send(request, tokens?.accessToken ?? null);
    if (response.status === 401 && requiresAuth && request.method === "GET") {
      const refreshed = await refreshSession();
      if (refreshed) {
        tokens = sessionStore.load();
        response = await send(request, tokens?.accessToken ?? null);
      }
    }
  } catch (error) {
    throw new ApiClientError(
      0,
      "NETWORK_ERROR",
      "Cannot reach Camxora. Check your connection.",
      String(error),
      undefined,
      true,
    );
  }

  const text = await response.text();
  const contentType = response.headers.get("content-type");
  const data = parseBody(text, contentType);

  if (!response.ok) {
    const envelope = (data ?? {}) as Record<string, unknown>;
    const detail =
      (envelope.detail as unknown) ??
      (envelope.error as unknown) ??
      (envelope.message as unknown) ??
      data;
    throw new ApiClientError(
      response.status,
      typeof envelope.code === "string" ? envelope.code : `HTTP_${response.status}`,
      typeof envelope.message === "string"
        ? envelope.message
        : typeof envelope.detail === "string"
          ? envelope.detail
          : `Request failed (${response.status}).`,
      detail,
      typeof envelope.request_id === "string" ? envelope.request_id : undefined,
      response.status >= 500 || response.status === 429,
    );
  }

  const headers: Record<string, string> = {};
  response.headers.forEach((value, key) => {
    headers[key] = value;
  });

  return { status: response.status, data, headers };
}

export async function login(
  email: string,
  password: string,
  remember = true,
): Promise<SessionSummary> {
  const response = await fetch(`${apiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { ...headersFor(null), "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  });

  const text = await response.text();
  const data = parseBody(text, response.headers.get("content-type"));
  if (!response.ok) {
    const envelope = (data ?? {}) as Record<string, unknown>;
    throw new ApiClientError(
      response.status,
      typeof envelope.code === "string" ? envelope.code : `HTTP_${response.status}`,
      typeof envelope.detail === "string"
        ? envelope.detail
        : "Unable to sign in with those details.",
      data,
    );
  }

  const tokenResponse = data as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  };
  if (!tokenResponse.access_token || !tokenResponse.refresh_token) {
    throw new ApiClientError(500, "INVALID_TOKEN_RESPONSE", "Sign-in returned an invalid session.");
  }

  const tokens: AuthTokens = {
    accessToken: tokenResponse.access_token,
    refreshToken: tokenResponse.refresh_token,
    expiresAt: Date.now() + (tokenResponse.expires_in ?? 3600) * 1000,
  };
  const displayName = email.split("@")[0] ?? email;
  sessionStore.save(
    tokens,
    {
      userId: "",
      email,
      displayName,
      lastUsedAt: Date.now(),
    },
    remember,
  );
  logger.info("user signed in", { email });
  return {
    userId: "",
    email,
    displayName,
    accessExpiresAt: tokens.expiresAt,
  };
}

export function restoreSession(): SessionSummary | null {
  const tokens = sessionStore.load();
  if (!tokens) return null;
  const account = sessionStore.accountSummary();
  return {
    userId: account?.userId ?? "",
    email: account?.email ?? "",
    displayName: account?.displayName ?? "Camxora user",
    accessExpiresAt: tokens.expiresAt,
  };
}
