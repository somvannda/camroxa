"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getUser, type AuthUser } from "@/lib/auth";
import { logout as endSession } from "@/lib/api";

const NAV = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/accounts", label: "Suno Accounts" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/keys", label: "API Keys" },
  { href: "/admin/logs", label: "Usage Logs" },
  { href: "/admin/audit", label: "Audit Trail" },
  { href: "/admin/pricing", label: "Pricing" },
  { href: "/admin/credit-packs", label: "Credit Packs" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/content", label: "API Updates" },
  { href: "/admin/settings", label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  // Read the cached profile after mount only: getUser() reads localStorage,
  // which is unavailable during SSR, so calling it in render caused a
  // hydration mismatch (server rendered null, client rendered the email).
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    // localStorage is unavailable during SSR, so the profile is read after
    // mount to avoid a hydration mismatch (server null vs client email).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUser(getUser());
  }, []);

  function isActive(href: string): boolean {
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  }

  function logout() {
    void endSession().finally(() => router.replace("/login"));
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-[var(--border)] bg-black/20 p-4">
      <Link href="/admin" className="mb-6 flex items-center gap-2 px-2">
        <Image src="/camxora-logo.svg" alt="Camxora" width={28} height={28} unoptimized className="h-7 w-7 rounded-lg" />
        <span className="font-bold">Camxora Admin</span>
      </Link>

      <nav className="flex-1 space-y-1 overflow-y-auto">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`block rounded-lg px-3 py-2 text-sm ${
              isActive(item.href)
                ? "bg-white/10 text-white"
                : "text-[var(--muted)] hover:bg-white/5 hover:text-white"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="space-y-1 border-t border-[var(--border)] pt-4 text-sm text-[var(--muted)]">
        <button onClick={logout} className="block w-full rounded-lg px-3 py-2 text-left text-red-300 hover:bg-white/5">
          Logout
        </button>
      </div>

      {user && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2">
          <div className="grad-bg flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white">
            {(user.email[0] ?? "?").toUpperCase()}
          </div>
          <span className="truncate text-xs text-[var(--muted)]">{user.email}</span>
        </div>
      )}
    </aside>
  );
}
