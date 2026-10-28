"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "./AuthProvider";

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            container: HTMLElement,
            options: Record<string, unknown>
          ) => void;
        };
      };
    };
  }
}

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

/** Google Identity Services caps the rendered button at 400px. We keep the
 *  control compact and centred under the OR divider. */
const GIS_BUTTON_WIDTH = 280;

/**
 * Google's official multicolour "G". Kept inline so the button inherits the
 * auth card typography instead of embedding Google's fixed-size iframe chrome.
 */
function GoogleGlyph() {
  return (
    <svg
      className="auth-google-glyph"
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
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

export function GoogleSignInButton() {
  const { refresh } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleCredential = useCallback(
    async (credential: string) => {
      setBusy(true);
      setError("");
      try {
        const response = await fetch("/api/v3/auth/google", {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Portal-Context": "user",
          },
          body: JSON.stringify({ credential }),
        });
        if (!response.ok) {
          let message = `Google sign-in failed (${response.status})`;
          try {
            const data = (await response.json()) as { detail?: string };
            if (data.detail) message = data.detail;
          } catch {
            /* keep fallback */
          }
          throw new Error(message);
        }
        await refresh();
        window.location.href = "/";
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Google sign-in failed");
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  // The GIS script is only loaded once per document. Navigating between
  // /login and /signup remounts this component without re-firing onLoad, so
  // also detect an already-loaded client.
  useEffect(() => {
    if (window.google?.accounts?.id) setReady(true);
  }, []);

  useEffect(() => {
    if (!CLIENT_ID || !ready || !window.google?.accounts?.id) return;
    const container = containerRef.current;
    if (!container || initializedRef.current) return;

    initializedRef.current = true;
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: (response) => {
        if (response.credential) void handleCredential(response.credential);
      },
    });

    container.replaceChildren();
    window.google.accounts.id.renderButton(container, {
      type: "standard",
      theme: "filled_black",
      size: "large",
      text: "continue_with",
      shape: "pill",
      logo_alignment: "center",
      width: GIS_BUTTON_WIDTH,
      locale: "en",
    });
  }, [ready, handleCredential]);

  if (!CLIENT_ID) return null;

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client?hl=en"
        strategy="afterInteractive"
        onReady={() => setReady(true)}
        onError={() => setFailed(true)}
      />
      <div className="auth-google">
        {/* Visual button — the real Google iframe sits invisibly on top so
            clicks still go through Google Identity Services. */}
        <span
          className={`auth-google-btn${busy ? " is-busy" : ""}${ready ? "" : " is-loading"}`}
          aria-hidden="true"
        >
          <GoogleGlyph />
          {busy ? "Signing in…" : "Continue with Google"}
        </span>
        <div
          ref={containerRef}
          className="auth-google-gis"
          data-failed={failed || undefined}
        />
      </div>
      {failed ? (
        <p className="auth-error" role="alert">
          Google sign-in is unavailable right now. Use email instead.
        </p>
      ) : null}
      {error ? (
        <p className="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </>
  );
}
