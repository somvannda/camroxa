"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
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

export function GoogleSignInButton() {
  const { refresh } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleCredential(credential: string) {
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
  }

  useEffect(() => {
    if (
      !CLIENT_ID ||
      !ready ||
      !window.google?.accounts?.id ||
      !containerRef.current ||
      initializedRef.current
    ) {
      return;
    }

    initializedRef.current = true;
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: (response) => {
        if (response.credential) void handleCredential(response.credential);
      },
    });
    window.google.accounts.id.renderButton(containerRef.current, {
      theme: "filled_black",
      size: "large",
      text: "continue_with",
      shape: "pill",
      width: 320,
      locale: "en",
    });
  }, [ready]);

  if (!CLIENT_ID) return null;

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client?hl=en"
        strategy="afterInteractive"
        onLoad={() => setReady(true)}
      />
      <div ref={containerRef} className="google-button" aria-busy={busy} />
      {error ? (
        <p className="fine" style={{ color: "#f87171", textAlign: "left" }} role="alert">
          {error}
        </p>
      ) : null}
    </>
  );
}
