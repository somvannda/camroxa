import type { TokenResponse } from "@/lib/platform-api";

const ACCESS_TOKEN_KEY = "camxora_access_token";
const REFRESH_TOKEN_KEY = "camxora_refresh_token";
const EXPIRES_AT_KEY = "camxora_expires_at";

/** In-memory access token for Authorization header (httpOnly cookies remain primary). */
let memoryAccessToken: string | null = null;

export function saveSession(tokens: TokenResponse) {
  memoryAccessToken = tokens.access_token;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(EXPIRES_AT_KEY);
}

export function clearSession() {
  memoryAccessToken = null;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(EXPIRES_AT_KEY);
}

export function getAccessToken(): string | null {
  return memoryAccessToken;
}

export function getRefreshToken(): string | null {
  return null;
}

export function getExpiresAt(): number | null {
  return null;
}
