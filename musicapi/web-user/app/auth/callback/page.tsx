"use client";

import { Suspense, useEffect, useState } from "react";
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

  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (error) {
        setBusy(false);
        setErr(`Google denied access: ${error}. Please try again.`);
        return;
      }
      if (!code) {
        setBusy(false);
        setErr("Missing authorization code. Try signing in again.");
        return;
      }
      if (!state) {
        setBusy(false);
        setErr("Missing sign-in state. Try signing in again.");
        return;
      }
      try {
        await completeGoogleCallback(code, state);
        if (cancelled) return;
        const redirectTo =
          (typeof window !== "undefined" &&
            (localStorage.getItem("google_auth_redirect") || "/dashboard")) ||
          "/dashboard";
        router.replace(redirectTo);
      } catch (e) {
        if (cancelled) return;
        setBusy(false);
        setErr(e instanceof Error ? e.message : "Google sign-in failed.");
      }
    })();

    return () => {
      cancelled = true;
    };
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
