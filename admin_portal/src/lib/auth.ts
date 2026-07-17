let accessToken: string | null = null;
let refreshToken: string | null = null;

const ACCESS_KEY = 'camxora_admin_access_token';
const REFRESH_KEY = 'camxora_admin_refresh_token';

function readStored(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null): void {
  try {
    if (value) {
      sessionStorage.setItem(key, value);
    } else {
      sessionStorage.removeItem(key);
    }
  } catch {
    // Ignore storage failures (private mode, etc.)
  }
}

export function getAccessToken(): string | null {
  if (accessToken) return accessToken;
  accessToken = readStored(ACCESS_KEY);
  return accessToken;
}

export function getRefreshToken(): string | null {
  if (refreshToken) return refreshToken;
  refreshToken = readStored(REFRESH_KEY);
  return refreshToken;
}

export function setTokens(access: string, refresh: string): void {
  accessToken = access || null;
  refreshToken = refresh || null;
  writeStored(ACCESS_KEY, accessToken);
  writeStored(REFRESH_KEY, refreshToken);
}

export function clearTokens(): void {
  accessToken = null;
  refreshToken = null;
  writeStored(ACCESS_KEY, null);
  writeStored(REFRESH_KEY, null);
}

/**
 * Decode the payload portion of a JWT (base64url-encoded second segment).
 * Returns the parsed JSON payload object, or null if decoding fails.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;

    const payload = parts[1];
    if (!payload) return null;

    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const jsonStr = atob(base64);
    return JSON.parse(jsonStr) as Record<string, unknown>;
  } catch {
    return null;
  }
}
