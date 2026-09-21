"use client";

import { useState } from "react";
import Link from "next/link";
import GoogleSignInButton from "@/components/google-signin-button";

export default function LoginPage() {
  const [error, setError] = useState("");

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="glass w-full max-w-sm rounded-2xl p-8 space-y-6">
        <div className="text-center">
          <div className="grad-bg mx-auto mb-4 h-11 w-11 rounded-xl" />
          <h1 className="text-2xl font-bold">Sign in</h1>
          <p className="text-sm text-[var(--muted)]">Camxora Music API workspace</p>
        </div>

        <GoogleSignInButton
          label="Continue with Google"
          redirectTo="/dashboard"
        />

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <p className="text-center text-xs text-[var(--muted)]">
          By continuing, you agree to our Terms and acknowledge our Privacy Policy.
        </p>

        <div className="flex justify-center">
          <Link href="/" className="text-xs text-[var(--muted)] hover:text-white">
            ← Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
