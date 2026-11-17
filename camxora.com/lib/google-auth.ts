import { musicAuthFetch } from "@/lib/auth-fetch";

/**
 * Google sign-in for the web app.
 *
 * The browser never holds a Google client secret and never talks to Google
 * directly: the API builds the consent URL, signs the OAuth `state`, and
 * exchanges the code (platform_api `GET /auth/google/url`,
 * `POST /auth/google/callback`). The web app only remembers the returned
 * `state` so the callback page can prove it started the round-trip.
 */

export const GOOGLE_CALLBACK_PATH = "/auth/callback";

/** Keys are scoped to the Google round-trip so a cancelled flow cannot leak
 *  into a later email sign-in. */
export const GOOGLE_STATE_KEY = "camxora_google_state";
export const GOOGLE_NEXT_KEY = "camxora_google_next";
export const GOOGLE_REFERRAL_KEY = "camxora_google_referral";

export type GoogleUnavailableReason =
  | "not-configured"
  | "origin-not-allowed"
  | "unreachable";

/**
 * Raised when the API cannot start a Google round-trip. The reason is carried
 * separately from the message so the button can say what is actually wrong
 * instead of looking live and failing on click.
 */
export class GoogleUnavailableError extends Error {
  readonly reason: GoogleUnavailableReason;

  constructor(message: string, reason: GoogleUnavailableReason) {
    super(message);
    this.name = "GoogleUnavailableError";
    this.reason = reason;
  }
}

/** Browser origin the API must have allowlisted for this app. */
export function googleRedirectUri(origin?: string): string {
  const configured = (process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI ?? "").trim();
  if (configured) return configured;
  const base =
    origin ?? (typeof window === "undefined" ? "" : window.location.origin);
  return `${base}${GOOGLE_CALLBACK_PATH}`;
}

/** Only same-origin absolute paths may be used as a post-sign-in target. */
export function safeNextPath(raw: string | null | undefined): string {
  const value = (raw ?? "").trim();
  return value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: unknown;
      error?: { message?: string };
    };
    if (typeof data.detail === "string" && data.detail.trim()) return data.detail;
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore non-JSON error bodies */
  }
  return fallback;
}

/** Ask the API for a signed consent URL. */
export async function requestGoogleAuthUrl(
  redirectUri: string = googleRedirectUri()
): Promise<{ url: string; state: string }> {
  let response: Response;
  try {
    response = await musicAuthFetch(
      `/api/v3/auth/google/url?redirect_uri=${encodeURIComponent(redirectUri)}`,
      { method: "GET" }
    );
  } catch {
    throw new GoogleUnavailableError(
      "Google sign-in is unavailable right now.",
      "unreachable"
    );
  }

  if (!response.ok) {
    const message = await readError(
      response,
      `Google sign-in is unavailable (${response.status}).`
    );
    if (response.status === 503) {
      throw new GoogleUnavailableError(
        message || "Google sign-in is not configured.",
        "not-configured"
      );
    }
    // 422 = the API rejected `redirect_uri` because this origin is not in
    // GOOGLE_REDIRECT_URIS. It is a configuration gap, not a transient error.
    if (response.status === 400 || response.status === 422) {
      throw new GoogleUnavailableError(
        message || "Google sign-in is not enabled for this address.",
        "origin-not-allowed"
      );
    }
    throw new GoogleUnavailableError(message, "unreachable");
  }

  const data = (await response.json()) as { url?: string; state?: string };
  if (!data.url || !data.state) {
    throw new GoogleUnavailableError(
      "Google sign-in is unavailable right now.",
      "unreachable"
    );
  }
  return { url: data.url, state: data.state };
}

/** Finish the round-trip. The API sets the session cookies on the response. */
export async function completeGoogleSignIn(input: {
  code: string;
  state: string;
  referral_code?: string;
}): Promise<void> {
  const response = await musicAuthFetch("/api/v3/auth/google/callback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(
      await readError(response, `Google sign-in failed (${response.status}).`)
    );
  }
}
