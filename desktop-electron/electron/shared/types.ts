export type ApiMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface ApiRequest {
  method: ApiMethod;
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  auth?: boolean;
  timeoutMs?: number;
}

export interface ApiError {
  code: string;
  message: string;
  detail?: unknown;
  requestId?: string;
  retryable?: boolean;
}

export type IpcResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

export interface ApiResponse {
  status: number;
  data: unknown;
  headers: Record<string, string>;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export interface SessionSummary {
  userId: string;
  email: string;
  displayName: string;
  accessExpiresAt: number;
}

export interface SavedAccount {
  userId: string;
  email: string;
  displayName: string;
  lastUsedAt: number;
}

export type BootstrapDestination = "login" | "confirm_email" | "onboarding" | "app";

export interface BootstrapResult {
  destination: BootstrapDestination;
  session: SessionSummary | null;
  message?: string;
  code?: string;
  portalUrl?: string;
}

export interface UserMe {
  id: string;
  email: string;
  email_confirmed: boolean;
  display_name: string;
  credit_balance: number;
  plan_name?: string | null;
  role?: string | null;
  onboarding_paid?: boolean;
  desktop_access?: boolean | null;
  channel_profile_count?: number;
}

export interface AppInfo {
  name: string;
  version: string;
  env: string;
  platform: string;
  electron: string;
  chrome: string;
  node: string;
  devBypass: boolean;
  portalUrl: string;
}

export interface PickFileRequest {
  kind: "file" | "directory";
  title?: string;
  filters?: Array<{ name: string; extensions: string[] }>;
  multiple?: boolean;
}

export function ok<T>(data: T): IpcResult<T> {
  return { ok: true, data };
}

export function fail(
  code: string,
  message: string,
  detail?: unknown,
  retryable = false,
): { ok: false; error: ApiError } {
  return { ok: false, error: { code, message, detail, retryable } };
}
