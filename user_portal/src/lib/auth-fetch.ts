"use client"

import { clearSession, getAccessToken, saveSession } from "@/lib/auth";
import { PLATFORM_API_BASE_URL, refreshWithToken } from "@/lib/platform-api";

let refreshPromise: Promise<string | null> | null = null;

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Portal-Context": "user",
  };
  const accessToken = getAccessToken();
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  return headers;
}

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = refreshWithToken()
      .then((tokens) => {
        saveSession(tokens);
        return tokens.access_token;
      })
      .catch(() => {
        clearSession();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

export async function platformFetch(input: {
  path: string;
  method?: string;
  body?: unknown;
  auth?: boolean;
}): Promise<Response> {
  const url = `${PLATFORM_API_BASE_URL}${input.path}`;

  let response = await fetch(url, {
    method: input.method ?? "GET",
    credentials: "include",
    headers: buildHeaders(),
    body: input.body === undefined ? undefined : JSON.stringify(input.body),
  });

  if (input.auth !== false && response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await fetch(url, {
        method: input.method ?? "GET",
        credentials: "include",
        headers: buildHeaders(),
        body: input.body === undefined ? undefined : JSON.stringify(input.body),
      });
    }
  }

  return response;
}

export async function platformJson<T>(input: {
  path: string;
  method?: string;
  body?: unknown;
  auth?: boolean;
}): Promise<T> {
  const response = await platformFetch(input);

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = (await response.json()) as {
        detail?: string;
        error?: {
          message?: string;
          details?: {
            error_code?: string;
            limit?: number;
            current_usage?: number;
          };
        };
      };
      if (data?.error?.message) {
        message = data.error.message;
      } else if (data?.detail) {
        message = data.detail;
      }
    } catch {}
    throw new Error(message);
  }

  return (await response.json()) as T;
}
