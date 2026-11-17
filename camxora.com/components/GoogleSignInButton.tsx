"use client";

import { useEffect, useState } from "react";
import {
  GOOGLE_NEXT_KEY,
  GOOGLE_REFERRAL_KEY,
  GOOGLE_STATE_KEY,
  GoogleUnavailableError,
  googleRedirectUri,
  requestGoogleAuthUrl,
  safeNextPath,
  type GoogleUnavailableReason,
} from "@/lib/google-auth";

/**
 * Google's official multicolour "G". Inline so the button matches the other
 * auth controls instead of embedding Google's fixed-size iframe chrome.
 */
export function GoogleGlyph({ className = "auth-provider-glyph" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
    >
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59A14.5 14.5 0 0 1 9.77 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.94 23.94 0 0 0 0 24c0 3.86.92 7.51 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.31-8.16 2.31-6.26 0-11.57-4.22-13.46-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

type Availability = "checking" | "ready" | GoogleUnavailableReason;

function unavailableTitle(reason: GoogleUnavailableReason): string {
  switch (reason) {
    case "not-configured":
      return "Google sign-in is not configured in this build";
    case "origin-not-allowed":
      return "Google sign-in is not enabled for this address";
    default:
      return "Google sign-in is unavailable right now";
  }
}

function unavailableMessage(reason: GoogleUnavailableReason, detail: string): string {
  switch (reason) {
    case "not-configured":
      return "Google sign-in is not configured in this build. Use email and password below.";
    case "origin-not-allowed":
      return "Google sign-in is not enabled for this address. Use email and password below.";
    default:
      return detail || "Google sign-in is unavailable right now. Use email and password below.";
  }
}

/**
 * "Continue with Google" — real round-trip through the API.
 *
 * The API decides whether Google is configured. This button asks it up front
 * (so it can be honestly disabled with a reason) and again on click (so the
 * signed state is fresh).
 */
export function GoogleSignInButton() {
  const [availability, setAvailability] = useState<Availability>("checking");
  const [detail, setDetail] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    requestGoogleAuthUrl(googleRedirectUri())
      .then(() => {
        if (!cancelled) setAvailability("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof GoogleUnavailableError) {
          setAvailability(error.reason);
          setDetail(error.message);
        } else {
          setAvailability("unreachable");
          setDetail("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function signIn() {
    setBusy(true);
    try {
      const { url, state } = await requestGoogleAuthUrl(googleRedirectUri());
      const params = new URLSearchParams(window.location.search);
      const ref = (params.get("ref") ?? params.get("invite") ?? "")
        .trim()
        .toUpperCase();

      window.localStorage.setItem(GOOGLE_STATE_KEY, state);
      window.localStorage.setItem(
        GOOGLE_NEXT_KEY,
        safeNextPath(params.get("next"))
      );
      if (ref) {
        window.localStorage.setItem(
          GOOGLE_REFERRAL_KEY,
          ref.replace(/[^A-Z0-9]/g, "").slice(0, 32)
        );
      } else {
        window.localStorage.removeItem(GOOGLE_REFERRAL_KEY);
      }

      window.location.assign(url);
    } catch (error) {
      if (error instanceof GoogleUnavailableError) {
        setAvailability(error.reason);
        setDetail(error.message);
      } else {
        setAvailability("unreachable");
        setDetail("");
      }
    } finally {
      setBusy(false);
    }
  }

  const ready = availability === "ready";
  const unavailable =
    availability === "checking" ? null : (availability as GoogleUnavailableReason);

  return (
    <>
      <button
        type="button"
        className="auth-btn google auth-provider"
        onClick={signIn}
        disabled={!ready || busy}
        aria-disabled={!ready || undefined}
        aria-busy={busy || undefined}
        title={unavailable ? unavailableTitle(unavailable) : undefined}
      >
        <GoogleGlyph />
        {busy ? "Opening Google…" : "Continue with Google"}
      </button>
      {unavailable ? (
        <p className="auth-provider-note is-error" role="status">
          {unavailableMessage(unavailable, detail)}
        </p>
      ) : null}
    </>
  );
}
