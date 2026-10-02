"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { setSession } from "@/lib/auth";

interface Props {
  label?: string;
  redirectTo?: string;
}

// Matches the allowlist in src/server.ts (GOOGLE_REDIRECT_URI_ADMIN default).
const REDIRECT_URI =
  (typeof window !== "undefined" &&
    `${window.location.origin}/auth/callback`) ||
  "http://localhost:4002/auth/callback";

export const GOOGLE_REDIRECT_KEY = "google_auth_redirect";

export default function GoogleSignInButton({
  label = "Continue with Google",
  redirectTo = "/admin",
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onClick() {
    setLoading(true);
    setError("");
    try {
      const { url } = await apiFetch<{ url: string; state: string }>(
        `/auth/google/url?redirect_uri=${encodeURIComponent(REDIRECT_URI)}`,
      );

      if (typeof window !== "undefined") {
        localStorage.setItem(GOOGLE_REDIRECT_KEY, redirectTo);
      }

      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google sign-in unavailable");
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={onClick}
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-white/5 px-3 py-2.5 text-sm font-medium hover:bg-white/10 disabled:opacity-60"
      >
        <svg className="h-4 w-4" viewBox="0 0 48 48">
          <path
            fill="#FFC107"
            d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
          />
          <path
            fill="#FF3D00"
            d="m6.306 14.691 6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
          />
          <path
            fill="#4CAF50"
            d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
          />
          <path
            fill="#1976D2"
            d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
          />
        </svg>
        <span>{loading ? "Opening Google…" : label}</span>
      </button>
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}
    </div>
  );
}

export async function completeGoogleCallback(code: string, state: string): Promise<{
  token: string;
  user: { id: string; email: string; role: "user" | "admin"; name?: string | null };
}> {
  const res = await apiFetch<{
    token: string;
    user: { id: string; email: string; role: "user" | "admin"; name?: string | null };
  }>("/auth/google/callback", {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
  // The API also sets an httpOnly session cookie; we only cache the profile.
  setSession(res.user);
  return res;
}
