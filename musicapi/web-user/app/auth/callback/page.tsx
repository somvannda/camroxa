"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { completeGoogleCallback } from "@/components/google-signin-button";

// useSearchParams() requires a Suspense boundary during prerender; the default
// export below provides it (see GoogleCallbackInner).
function GoogleCallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const code = params.get("code") ?? "";
  const state = params.get("state") ?? "";
  const error = params.get("error") ?? "";

  const [busy, setBusy] = useState(true);
  const [msg, setMsg] = useState<string>(code ? "Completing Google sign-in…" : "Preparing…");
  const [err, setErr] = useState<string>("");

  // React StrictMode mounts effects twice in development. The authorization
  // code is single-use, so a second exchange fails with invalid_grant and
  // replaces the success path with an error. Guard on a ref (not the effect's
  // cleanup) so exactly one exchange happens and its redirect still lands.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    (async () => {
      if (error) {
        setBusy(false);
        setErr(`Google denied access: ${error}. Please try again.`);
        return;
      }
      const storedState =
        typeof window !== "undefined" ? localStorage.getItem("google_auth_state") || "" : "";
      const effectiveState = state || storedState;
      if (!code || !effectiveState) {
        setBusy(false);
        setErr("Missing authorization details. Try signing in again.");
        return;
      }
      try {
        await completeGoogleCallback(effectiveState, code);
        const redirectTo =
          (typeof window !== "undefined" &&
            (localStorage.getItem("google_auth_redirect") || "/dashboard")) ||
          "/dashboard";
        if (typeof window !== "undefined") {
          localStorage.removeItem("google_auth_redirect");
          localStorage.removeItem("google_auth_state");
          localStorage.removeItem("camxora_invite_code");
        }
        router.replace(redirectTo);
      } catch (e) {
        setBusy(false);
        setErr(e instanceof Error ? e.message : "Google sign-in failed.");
      }
    })();
  }, [code, state, error, router]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="glass w-full max-w-md rounded-2xl p-8 text-center space-y-4">
        <div className="grad-bg mx-auto h-12 w-12 rounded-xl" />
        <h1 className="text-xl font-bold">
          {busy ? "Signing you in…" : err ? "Sign-in incomplete" : "Redirecting…"}
        </h1>
        <p className="text-sm text-[var(--muted)]">{err || msg}</p>
        {!busy && err && (
          <div className="flex flex-col items-center gap-3">
            <a
              href="/login"
              className="grad-bg inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold text-white"
            >
              Back to sign in
            </a>
            <a
              href="/"
              className="text-xs text-[var(--muted)] hover:underline"
            >
              Back to home
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center p-6">
          <div className="glass w-full max-w-md rounded-2xl p-8 text-center space-y-4">
            <div className="grad-bg mx-auto h-12 w-12 rounded-xl" />
            <h1 className="text-xl font-bold">Signing you in…</h1>
            <p className="text-sm text-[var(--muted)]">Preparing…</p>
          </div>
        </div>
      }
    >
      <GoogleCallbackInner />
    </Suspense>
  );
}
