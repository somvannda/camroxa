"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { getCurrentUser } from "@/lib/channel-setup";

export default function Home() {
  const router = useRouter();

  React.useEffect(() => {
    let cancelled = false;

    async function resolveLanding() {
      try {
        const me = await getCurrentUser();
        if (!cancelled) {
          router.replace(me.email_confirmed ? "/dashboard" : "/onboarding");
        }
      } catch {
        if (!cancelled) {
          router.replace("/register");
        }
      }
    }

    void resolveLanding();

    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#050814] px-6">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-3 text-sm text-slate-300/72 backdrop-blur">
        Loading your account workspace...
      </div>
    </div>
  );
}
