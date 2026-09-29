"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { getUser } from "@/lib/auth";
import { apiFetch, logout as endSession } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
  children?: { href: string; label: string }[];
  external?: boolean;
};

const NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>
    ),
  },
  {
    href: "/dashboard/playground",
    label: "Playground",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
    ),
    children: [
      { href: "/dashboard/playground", label: "Music Generation" },
      { href: "/dashboard/recovery-audio", label: "Recovery Audio" },
      { href: "/dashboard/separate-vocals", label: "Separate Vocals" },
      { href: "/dashboard/generate-voice", label: "Generate Voice" },
      { href: "/dashboard/check-voice", label: "Check Voice" },
      { href: "/dashboard/replace-section", label: "Replace Section" },
    ],
  },
  {
    href: "/dashboard/api-keys",
    label: "API Key",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
    ),
  },
  {
    href: "/dashboard/usage",
    label: "API Usage",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M3 3v18h18"/><path d="M7 15l4-4 4 4 5-5"/></svg>
    ),
  },
  {
    href: "/dashboard/logs",
    label: "Logs",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></svg>
    ),
  },
  {
    href: "/dashboard/updates",
    label: "API Updates",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    ),
  },
  {
    href: "/dashboard/billing",
    label: "Billing",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
    ),
  },
  {
    href: "/docs",
    label: "Document",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
    ),
    external: true,
  },
];

/** Operator-managed branding the panel reads from the public `GET /settings`. */
interface Brand {
  name: string;
  docs_url: string;
  support_telegram_url: string;
  languages: string[];
}

// Human-readable names for the operator-configured language codes. Unknown codes
// fall back to their uppercase form rather than hiding the option.
const LANGUAGE_LABELS: Record<string, string> = {
  en: "English",
  km: "ភាសាខ្មែរ",
  zh: "中文",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  ja: "日本語",
  ko: "한국어",
  vi: "Tiếng Việt",
  th: "ไทย",
};

function CollapsibleIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authed, setAuthed] = useState(false);
  const [openMenus, setOpenMenus] = useState<Record<string, boolean>>({ Playground: true });
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [language, setLanguage] = useState("");

  const user = getUser();

  useEffect(() => {
    if (!getUser()) {
      router.replace("/login");
    } else {
      setAuthed(true);
    }
  }, [router]);

  // Panel branding (support link + languages) and the user's saved language.
  useEffect(() => {
    if (!authed) return;
    apiFetch<{ brand: Brand }>("/settings")
      .then((r) => setBrand(r.brand))
      .catch(() => {});
    apiFetch<{ language?: string }>("/me/profile")
      .then((p) => setLanguage(p.language ?? ""))
      .catch(() => {});
  }, [authed]);

  if (!authed) return null;

  function toggleMenu(label: string) {
    setOpenMenus((m) => ({ ...m, [label]: !m[label] }));
  }

  function isActive(href: string, hasChildren?: boolean): boolean {
    if (href === "/dashboard") return pathname === "/dashboard";
    if (hasChildren) return pathname.startsWith(href);
    return pathname === href || pathname.startsWith(href + "/");
  }

  function logout() {
    void endSession().finally(() => router.replace("/login"));
  }

  // Persist the language choice; revert the selector if the save fails.
  async function changeLanguage(next: string) {
    const previous = language;
    setLanguage(next);
    try {
      await apiFetch("/me/profile", { method: "PUT", body: JSON.stringify({ language: next }) });
    } catch {
      setLanguage(previous);
    }
  }

  return (
    <div className="flex min-h-screen bg-[#0e0e10]">
      {/* Sidebar */}
      <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-white/5 bg-[#141416]">
        {/* Logo */}
        <div className="flex items-center justify-between px-4 py-4">
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="grad-bg flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold text-white">
              ♪
            </div>
            <span className="text-sm font-bold tracking-wide text-white">MUSIC API</span>
          </Link>
        </div>

        {/* User card at top of sidebar */}
        <div className="mx-3 mb-3 rounded-lg bg-white/[0.03] p-3">
          <div className="flex items-center gap-2.5">
            <div className="grad-bg flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ring-2 ring-white/5">
              {user?.email?.[0]?.toUpperCase() ?? "?"}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-white">{user?.name ?? "User"}</div>
              <div className="truncate text-xs text-white/40">{user?.email}</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {NAV.map((item) => {
            const hasChildren = !!item.children?.length;
            const open = !!openMenus[item.label];
            const active = isActive(item.href, hasChildren);
            const content = (
              <div
                className={`group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
                  active
                    ? "bg-white/10 text-white"
                    : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                <span className={active ? "text-white" : "text-white/40 group-hover:text-white"}>{item.icon}</span>
                <span className="flex-1 font-medium">{item.label}</span>
                {hasChildren && <CollapsibleIcon open={open} />}
              </div>
            );
            return (
              <div key={item.href}>
                <div onClick={() => hasChildren && toggleMenu(item.label)}>
                  {item.external ? (
                    <a href={item.href} target="_blank" rel="noreferrer">
                      {content}
                    </a>
                  ) : hasChildren ? (
                    <button type="button" className="w-full text-left">
                      {content}
                    </button>
                  ) : (
                    <Link href={item.href}>{content}</Link>
                  )}
                </div>

                {/* Children render inline, beneath parent, only when open */}
                {hasChildren && open && (
                  <div className="ml-4 mt-0.5 space-y-0.5">
                    {item.children!.map((child) => {
                      const childActive =
                        (child.href === "/dashboard/playground" &&
                          pathname === "/dashboard/playground") ||
                        (child.href !== "/dashboard/playground" &&
                          pathname.startsWith(child.href));
                      return (
                        <Link
                          key={child.href}
                          href={child.href}
                          className={`group relative flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs transition-all ${
                            childActive
                              ? "border border-white/15 bg-white/5 text-white shadow-sm"
                              : "text-white/45 hover:bg-white/5 hover:text-white"
                          }`}
                        >
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className={`h-3 w-3 ${
                              childActive
                                ? "text-white"
                                : "text-white/25 group-hover:text-white/50"
                            }`}
                          >
                            <circle cx="12" cy="12" r="3" />
                          </svg>
                          {child.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Bottom actions */}
        <div className="border-t border-white/5 px-2 py-3 space-y-0.5">
          <Link href="/dashboard/settings" className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-white/60 hover:bg-white/5 hover:text-white">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            Settings
          </Link>
          {brand?.support_telegram_url && (
            <a
              href={brand.support_telegram_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-white/60 hover:bg-white/5 hover:text-white"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
              Get Support
            </a>
          )}
          {brand && brand.languages.length > 0 && (
            <div className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-white/60">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              <select
                aria-label="Language"
                value={language}
                onChange={(e) => void changeLanguage(e.target.value)}
                className="w-full flex-1 cursor-pointer rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs text-white/80 outline-none hover:bg-white/5 focus:border-white/20"
              >
                {brand.languages.map((code) => (
                  <option key={code} value={code} className="bg-[#141416] text-white">
                    {LANGUAGE_LABELS[code] ?? code.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button onClick={logout} className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-red-400 hover:bg-red-500/5 hover:text-red-300">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Log Out
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-white/5 bg-[#0e0e10]/80 px-8 backdrop-blur">
          <div className="text-sm text-white/40">
            {/* breadcrumbs space */}
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/api-keys"
              className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/5"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 text-white/50"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
              API Key
            </Link>
            <Link
              href="/dashboard/billing"
              className="flex items-center gap-1.5 rounded-lg grad-bg px-3 py-1.5 text-xs font-semibold text-white shadow-lg shadow-purple-900/20"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5"><path d="M12 5v14M5 12h14"/></svg>
              Top Up
            </Link>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
    </div>
  );
}
