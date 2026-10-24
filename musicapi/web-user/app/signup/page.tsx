"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SignupPage() {
  const router = useRouter();

  useEffect(() => {
    // Keep an invite code attached when forwarding legacy /signup links.
    const search = typeof window !== "undefined" ? window.location.search : "";
    router.replace(`/login${search}`);
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="glass w-full max-w-sm rounded-2xl p-8 text-center space-y-4">
        <div className="grad-bg mx-auto h-11 w-11 rounded-xl" />
        <h1 className="text-xl font-bold">Redirecting…</h1>
        <p className="text-sm text-[var(--muted)]">
          Self-registration is disabled. Please sign in with Google.
        </p>
      </div>
    </div>
  );
}
