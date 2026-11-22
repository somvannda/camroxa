import { logger } from "./logger";
import { resolveApiBaseUrl, resolvePortalBaseUrl } from "./endpoints";
import { sessionStore } from "./session";
import {
  DESKTOP_PLAN_REQUIRED_CODE,
  DESKTOP_PLAN_REQUIRED_MESSAGE,
  resolveBootstrapDestination,
} from "./entitlement";
import type {
  ApiRequest,
  ApiResponse,
  AuthTokens,
  BootstrapResult,
  SessionSummary,
  UserMe,
} from "../shared/types";

const DEFAULT_TIMEOUT_MS = 30_000;

export const NETWORK_ERROR_MESSAGE = "Cannot reach Camxora. Check your connection.";
export const SERVER_UNREACHABLE_MESSAGE =
  "Cannot reach Camxora servers right now. Your sign-in is saved — try again.";
export const SESSION_EXPIRED_MESSAGE = "Session expired. Please sign in again.";

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
  return resolveApiBaseUrl();
}

/** Swap the trailing `/api/vN` when a route only exists on another surface. */
function apiBaseUrlFor(version: ApiRequest["apiVersion"]): string {
  const base = apiBaseUrl();
  if (!version) return base;
  return base.replace(/\/api\/v\d+$/, `/api/${version}`);
}

/** Public API origin used by update checks and other unauthenticated clients. */
export function getApiBaseUrl(): string {
  return apiBaseUrl();
}

export function portalBaseUrl(): string {
  return resolvePortalBaseUrl();
}

function buildUrl(request: ApiRequest): string {
  const path = request.path.startsWith("/") ? request.path : `/${request.path}`;
  const url = new URL(`${apiBaseUrlFor(request.apiVersion)}${path}`);
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

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

interface ErrorEnvelope {
  code?: string;
  message?: string;
  detail?: unknown;
}

/** Reads both the platform envelope `{ error: { code, message } }` and flat shapes. */
function parseErrorEnvelope(data: unknown): ErrorEnvelope {
  const root = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const nested = root.error;
  if (nested && typeof nested === "object") {
    const error = nested as Record<string, unknown>;
    return {
      code: stringValue(error.code),
      message: stringValue(error.message),
      detail: error.details ?? error.detail ?? data,
    };
  }
  return {
    code: stringValue(root.code),
    message: stringValue(root.message) ?? stringValue(root.detail),
    detail: root.detail ?? data,
  };
}

function isRetryableStatus(status: number): boolean {
  return status === 0 || status === 408 || status === 429 || status >= 500;
}

function errorFromResponse(response: Response, data: unknown, fallback: string): ApiClientError {
  const envelope = parseErrorEnvelope(data);
  return new ApiClientError(
    response.status,
    envelope.code ?? `HTTP_${response.status}`,
    envelope.message ?? fallback,
    envelope.detail,
    undefined,
    isRetryableStatus(response.status),
  );
}

function tokensFromResponse(data: unknown): AuthTokens | null {
  const payload = (data && typeof data === "object" ? data : {}) as {
    access_token?: unknown;
    refresh_token?: unknown;
    expires_in?: unknown;
  };
  if (typeof payload.access_token !== "string" || typeof payload.refresh_token !== "string") {
    return null;
  }
  const expiresIn = typeof payload.expires_in === "number" ? payload.expires_in : 3600;
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresAt: Date.now() + expiresIn * 1000,
  };
}

type RefreshOutcome = "ok" | "rejected" | "plan_required" | "transient";

let refreshInFlight: Promise<RefreshOutcome> | null = null;

/**
 * Single-flight token refresh. `rejected` means the server refused the refresh
 * token (sign in again); `transient` means the server was unreachable, so the
 * stored session must be kept for the next launch or retry.
 */
async function refreshSession(): Promise<RefreshOutcome> {
  if (refreshInFlight) return refreshInFlight;
  const tokens = sessionStore.load();
  if (!tokens?.refreshToken) return "rejected";

  refreshInFlight = (async (): Promise<RefreshOutcome> => {
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
        if (response.status === 400 || response.status === 401 || response.status === 403) {
          let code: string | undefined;
          try {
            code = parseErrorEnvelope(await response.json()).code;
          } catch {
            code = undefined;
          }
          if (code === DESKTOP_PLAN_REQUIRED_CODE) {
            logger.warn("session refresh rejected", { status: response.status, code });
            return "plan_required";
          }
          logger.warn("session refresh rejected", { status: response.status });
          return "rejected";
        }
        logger.warn("session refresh unavailable", { status: response.status });
        return "transient";
      }
      const data = (await response.json()) as unknown;
      const refreshed = tokensFromResponse(data);
      if (!refreshed) return "transient";
      sessionStore.save(refreshed);
      logger.info("session refreshed");
      return "ok";
    } catch (error) {
      logger.warn("session refresh failed", { error: String(error) });
      return "transient";
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
      if (refreshed === "plan_required") {
        throw new ApiClientError(
          403,
          DESKTOP_PLAN_REQUIRED_CODE,
          DESKTOP_PLAN_REQUIRED_MESSAGE,
          undefined,
          undefined,
          false,
        );
      }
      if (refreshed === "ok") {
        tokens = sessionStore.load();
        response = await send(request, tokens?.accessToken ?? null);
      }
    }
  } catch (error) {
    if (error instanceof ApiClientError) throw error;
    throw new ApiClientError(
      0,
      "NETWORK_ERROR",
      NETWORK_ERROR_MESSAGE,
      String(error),
      undefined,
      true,
    );
  }

  const text = await response.text();
  const contentType = response.headers.get("content-type");
  const data = parseBody(text, contentType);

  if (!response.ok) {
    throw errorFromResponse(response, data, `Request failed (${response.status}).`);
  }

  const headers: Record<string, string> = {};
  response.headers.forEach((value, key) => {
    headers[key] = value;
  });

  return { status: response.status, data, headers };
}

async function requestTokenPair(
  path: string,
  body: Record<string, unknown>,
  fallbackMessage: string,
): Promise<AuthTokens> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: { ...headersFor(null), "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof ApiClientError) throw error;
    throw new ApiClientError(
      0,
      "NETWORK_ERROR",
      NETWORK_ERROR_MESSAGE,
      String(error),
      undefined,
      true,
    );
  }

  const text = await response.text();
  const data = parseBody(text, response.headers.get("content-type"));
  if (!response.ok) {
    throw errorFromResponse(response, data, fallbackMessage);
  }

  const tokens = tokensFromResponse(data);
  if (!tokens) {
    throw new ApiClientError(502, "INVALID_TOKEN_RESPONSE", "Sign-in returned an invalid session.");
  }
  return tokens;
}

function displayNameFor(email: string): string {
  return email.split("@")[0]?.trim() || email;
}

function loginResult(message = "", code?: string, portalUrl?: string): BootstrapResult {
  return { destination: "login", session: null, message, code, portalUrl };
}

function isPaidGateError(error: ApiClientError): boolean {
  if (error.code === DESKTOP_PLAN_REQUIRED_CODE) return true;
  if (error.status !== 403) return false;
  return /desktop studio requires a paid plan/i.test(error.message) ||
    /no active desktop studio credits/i.test(error.message);
}

function handleBootstrapError(error: unknown, portalUrl: string): BootstrapResult {
  if (error instanceof ApiClientError) {
    if (isPaidGateError(error)) {
      sessionStore.clear();
      logger.warn("desktop entitlement rejected");
      return loginResult(DESKTOP_PLAN_REQUIRED_MESSAGE, DESKTOP_PLAN_REQUIRED_CODE, portalUrl);
    }
    if (error.status === 401) {
      sessionStore.clear();
      logger.warn("session rejected during bootstrap");
      return loginResult(SESSION_EXPIRED_MESSAGE, "SESSION_EXPIRED", portalUrl);
    }
    if (isRetryableStatus(error.status)) {
      // Transient outage: keep the tokens so the next retry or launch can resume.
      logger.warn("bootstrap check unavailable", { status: error.status });
      return loginResult(SERVER_UNREACHABLE_MESSAGE, "NETWORK_ERROR", portalUrl);
    }
    logger.warn("bootstrap check failed", { status: error.status, code: error.code });
    return loginResult(
      "Unable to verify your account. Please sign in again.",
      error.code,
      portalUrl,
    );
  }

  logger.warn("bootstrap check failed");
  return loginResult(
    "Unable to verify your account right now. Please try again.",
    "BOOTSTRAP_FAILED",
    portalUrl,
  );
}

function sessionSummary(me: UserMe, tokens: AuthTokens): SessionSummary {
  return {
    userId: me.id,
    email: me.email,
    displayName: me.display_name?.trim() || displayNameFor(me.email),
    accessExpiresAt: tokens.expiresAt,
  };
}

/**
 * Resolves where the app should go after a login, Google sign-in or restore.
 *
 * Order: entitlement (paid gate) -> email confirmation -> channel profiles -> app.
 * Only a 401 or a paid-gate rejection clears the stored tokens; a transient
 * outage keeps the saved session.
 */
export async function bootstrapSession(): Promise<BootstrapResult> {
  const portalUrl = portalBaseUrl();
  let tokens = sessionStore.load();

  if (!tokens?.accessToken || !tokens.refreshToken) {
    return loginResult("", undefined, portalUrl);
  }

  if (tokens.expiresAt - 30_000 <= Date.now()) {
    const outcome = await refreshSession();
    if (outcome === "rejected") {
      sessionStore.clear();
      logger.warn("session expired during bootstrap");
      return loginResult(SESSION_EXPIRED_MESSAGE, "SESSION_EXPIRED", portalUrl);
    }
    if (outcome === "plan_required") {
      sessionStore.clear();
      logger.warn("desktop entitlement rejected");
      return loginResult(DESKTOP_PLAN_REQUIRED_MESSAGE, DESKTOP_PLAN_REQUIRED_CODE, portalUrl);
    }
    if (outcome === "transient") {
      return loginResult(SERVER_UNREACHABLE_MESSAGE, "NETWORK_ERROR", portalUrl);
    }
    tokens = sessionStore.load() ?? tokens;
  }

  let me: UserMe;
  try {
    const response = await apiRequest({ method: "GET", path: "/users/me" });
    const payload = response.data;
    if (!payload || typeof payload !== "object") {
      return loginResult(
        "Unable to verify your account right now. Please try again.",
        "BOOTSTRAP_FAILED",
        portalUrl,
      );
    }
    me = payload as UserMe;
  } catch (error) {
    return handleBootstrapError(error, portalUrl);
  }

  if (typeof me.id !== "string" || typeof me.email !== "string") {
    return loginResult(
      "Unable to verify your account right now. Please try again.",
      "BOOTSTRAP_FAILED",
      portalUrl,
    );
  }

  const route = resolveBootstrapDestination(me);
  if (route.destination === "login") {
    sessionStore.clear();
    logger.warn("desktop entitlement rejected");
    return loginResult(DESKTOP_PLAN_REQUIRED_MESSAGE, DESKTOP_PLAN_REQUIRED_CODE, portalUrl);
  }

  const session = sessionSummary(me, tokens);
  sessionStore.updateAccount({
    userId: session.userId,
    email: session.email,
    displayName: session.displayName,
    lastUsedAt: Date.now(),
  });

  if (route.destination === "confirm_email") {
    logger.info("bootstrap routed", { destination: "confirm_email" });
    return { destination: "confirm_email", session, portalUrl };
  }

  if (route.destination === "topup") {
    logger.info("bootstrap routed", { destination: "topup" });
    return { destination: "topup", session, portalUrl };
  }

  logger.info("bootstrap routed", { destination: "app" });
  return { destination: "app", session, portalUrl };
}

export async function login(
  email: string,
  password: string,
  remember = true,
): Promise<BootstrapResult> {
  const tokens = await requestTokenPair(
    "/auth/login",
    { email, password },
    "Unable to sign in with those details.",
  );

  sessionStore.save(
    tokens,
    {
      userId: "",
      email,
      displayName: displayNameFor(email),
      lastUsedAt: Date.now(),
    },
    remember,
  );
  logger.info("user signed in");
  return bootstrapSession();
}

export async function requestGoogleAuthUrl(
  desktopPort: number,
): Promise<{ url: string; state: string }> {
  const response = await apiRequest({
    method: "GET",
    path: "/auth/google/url",
    query: { desktop_port: desktopPort },
    auth: false,
  });
  const payload = (response.data ?? {}) as { url?: unknown; state?: unknown };
  if (typeof payload.url !== "string" || typeof payload.state !== "string") {
    throw new ApiClientError(
      502,
      "INVALID_OAUTH_RESPONSE",
      "Google sign-in is not available right now.",
    );
  }
  if (!/^https:\/\//i.test(payload.url)) {
    throw new ApiClientError(
      502,
      "INVALID_OAUTH_RESPONSE",
      "Google sign-in is not available right now.",
    );
  }
  return { url: payload.url, state: payload.state };
}

export async function completeGoogleLogin(
  code: string,
  state: string,
  remember = true,
): Promise<BootstrapResult> {
  const tokens = await requestTokenPair(
    "/auth/google/callback",
    { code, state },
    "Google sign-in could not be completed. Please try again.",
  );

  sessionStore.save(tokens, undefined, remember);
  logger.info("google sign-in completed");
  return bootstrapSession();
}
