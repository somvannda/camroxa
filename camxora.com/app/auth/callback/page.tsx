"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  completeGoogleSignIn,
  GOOGLE_NEXT_KEY,
  GOOGLE_REFERRAL_KEY,
  GOOGLE_STATE_KEY,
  safeNextPath,
} from "@/lib/google-auth";

/**
 * Google sends the browser back here with `?code=…&state=…`. The code is
 * exchanged for a CAMXORA session by the API (`POST /auth/google/callback`),
 * which also sets the session cookies. Nothing about the Google client secret
 * exists in the browser.
 */
function GoogleCallbackInner() {
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    async function finish() {
      const code = params.get("code");
      const state = params.get("state");
      const oauthError = params.get("error");

      if (oauthError) {
        setError(
          oauthError === "access_denied"
            ? "Google sign-in was cancelled. You can try again."
            : `Google sign-in failed (${oauthError}).`
        );
        return;
      }
      if (!code || !state) {
        setError(
          "Google did not return a valid sign-in response. Please try again."
        );
        return;
      }

      const expectedState = window.localStorage.getItem(GOOGLE_STATE_KEY);
      if (expectedState && expectedState !== state) {
        setError(
          "The Google sign-in session could not be verified. Please try again."
        );
        return;
      }

      const next = safeNextPath(window.localStorage.getItem(GOOGLE_NEXT_KEY));
      const referralCode =
        window.localStorage.getItem(GOOGLE_REFERRAL_KEY) || undefined;
      window.localStorage.removeItem(GOOGLE_STATE_KEY);
      window.localStorage.removeItem(GOOGLE_NEXT_KEY);

      try {
        await completeGoogleSignIn({ code, state, referral_code: referralCode });
        window.localStorage.removeItem(GOOGLE_REFERRAL_KEY);
        await refresh();
        window.location.replace(next);
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "Google sign-in failed."
        );
      }
    }

    void finish();
  }, [params, refresh]);

  return (
    <div className="auth-page solo">
      <div className="auth-panel">
        <div className="auth-card">
          <Link className="auth-brand" href="/">
            <img src="/camxora-logo.svg" alt="" /> CAMXORA
          </Link>
          <h1>{error ? "Google sign-in" : "Signing you in…"}</h1>
          {error ? (
            <>
              <p className="sub">We could not finish signing you in with Google.</p>
              <p className="auth-error auth-callback-error" role="alert">
                {error}
              </p>
              <Link className="auth-btn primary auth-callback-back" href="/login">
                Back to sign in
              </Link>
            </>
          ) : (
            <p className="sub" role="status">
              Finishing Google sign-in. This takes a moment.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-page solo">
          <div className="auth-panel">
            <div className="auth-card">
              <p className="sub" role="status">
                Loading…
              </p>
            </div>
          </div>
        </div>
      }
    >
      <GoogleCallbackInner />
    </Suspense>
  );
}
