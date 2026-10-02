"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getUser } from "@/lib/auth";

export default function AppLegacyLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!getUser()) {
      router.replace("/login");
      return;
    }
    const target = pathname.replace(/^\/app/, "/dashboard");
    router.replace(target);
  }, [router, pathname]);

  return <div className="flex min-h-screen items-center justify-center p-8 text-sm text-white/40">Redirecting…</div>;
}
