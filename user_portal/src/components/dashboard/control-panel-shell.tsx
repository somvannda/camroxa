"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import {
  ChevronRight,
  ArrowRight,
  Bell,
  Coins,
  CreditCard,
  FolderKanban,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Presentation,
  UserRound,
  X,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  InlineBadge,
  formatCreditValue,
  formatDate,
  getInitials,
  titleCase,
} from "@/components/dashboard/control-panel-ui";
import { cn } from "@/lib/utils";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Profiles", href: "/dashboard/profiles", icon: FolderKanban },
  { label: "Usage", href: "/dashboard/activity", icon: Sparkles },
  { label: "Billing", href: "/dashboard/billing", icon: CreditCard },
  { label: "Account", href: "/dashboard/security", icon: ShieldCheck },
];

/** Pinned at sidebar bottom, above the Sign out separator. */
const FOOTER_NAV_ITEMS: NavItem[] = [
  { label: "Guides", href: "/dashboard/guides", icon: Presentation },
];

const ALL_NAV_ITEMS: NavItem[] = [...NAV_ITEMS, ...FOOTER_NAV_ITEMS];

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/guides": "Guides",
  "/dashboard/profiles/": "Profile",
  "/dashboard/profiles": "Profiles",
  "/dashboard/activity": "Usage",
  "/dashboard/billing/": "Payment",
  "/dashboard/billing": "Billing",
  "/dashboard/credits": "Credits",
  "/dashboard/account": "Account",
  "/dashboard/security": "Account",
};

export function UserControlPanelShell(props: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading, state, signOut, websiteBaseUrl } = useControlPanel();
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("camxora.user-panel.sidebar-collapsed") === "true";
  });
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("camxora.user-panel.sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-100">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-3 text-sm text-slate-300/72 backdrop-blur">
          Loading your control panel...
        </div>
      </div>
    );
  }

  if (!state.user) {
    return null;
  }

  const currentDisplayName = state.user.display_name?.trim() || "CAMXORA user";
  const planLabel = state.user.plan_name ?? "No active subscription";
  const profileAllowance = state.user.profile_allowance ?? null;
  const quotaChannels =
    state.user.effective_quota_channels ??
    (profileAllowance != null ? profileAllowance + (state.user.profile_addon_slots ?? 0) : null);
  const profileLimit = state.user.effective_profile_allowance ?? profileAllowance;
  const walletBalance = state.wallet?.balance ?? state.user.credit_balance ?? 0;
  const activeNavItem =
    ALL_NAV_ITEMS.find((item) =>
      item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href),
    ) ?? ALL_NAV_ITEMS[0];
  const currentPageTitle =
    Object.entries(PAGE_TITLES).find(([route]) => pathname === route)?.[1] ??
    Object.entries(PAGE_TITLES).find(([route]) => pathname.startsWith(route) && route !== "/dashboard")?.[1] ??
    "Control Panel";

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
      {mobileNavOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-slate-950/72 lg:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex h-screen shrink-0 flex-col border-r border-slate-800/80 bg-[linear-gradient(180deg,rgba(5,10,28,0.96),rgba(3,7,20,0.98))] shadow-[24px_0_64px_rgba(2,6,23,0.42)] backdrop-blur-xl transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0",
          sidebarCollapsed ? "w-[88px]" : "w-72",
          mobileNavOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div
          className={cn(
            "flex h-16 items-center border-b border-white/8 bg-white/[0.02] px-4",
            sidebarCollapsed ? "justify-center lg:justify-between" : "gap-3 px-5",
          )}
        >
          <div className={cn("flex min-w-0 items-center", sidebarCollapsed ? "justify-center" : "gap-3")}>
            <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
            {!sidebarCollapsed ? (
              <div className="min-w-0">
                <div className="truncate font-display text-lg font-semibold tracking-[-0.04em] text-white">
                  CAMXORA
                </div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/54">
                  User panel
                </div>
              </div>
            ) : null}
          </div>

          <div className="hidden lg:block">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setSidebarCollapsed((current) => !current)}
              className="h-9 w-9 rounded-xl text-slate-400 hover:bg-white/[0.05] hover:text-white"
            >
              {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </Button>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => setMobileNavOpen(false)}
            className="ml-auto h-9 w-9 rounded-xl text-slate-400 hover:bg-white/[0.05] hover:text-white lg:hidden"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <Card className="rounded-[24px] border-white/10 bg-[linear-gradient(180deg,rgba(14,20,50,0.96),rgba(8,12,28,0.98))] shadow-[0_24px_80px_rgba(15,22,58,0.34)]">
            <CardHeader className="space-y-4">
              <div className={cn("flex items-center", sidebarCollapsed ? "justify-center" : "gap-3")}>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/80 via-purple-500/70 to-fuchsia-500/70 text-base font-semibold text-white shadow-[0_14px_40px_rgba(118,77,255,0.22)]">
                  {getInitials(currentDisplayName)}
                </div>
                {!sidebarCollapsed ? (
                  <div className="min-w-0">
                    <CardTitle className="truncate font-display text-xl text-white">
                      {currentDisplayName}
                    </CardTitle>
                    <CardDescription className="truncate text-slate-300/72">
                      {state.user.email}
                    </CardDescription>
                  </div>
                ) : null}
              </div>
              {!sidebarCollapsed ? (
                <div className="grid gap-2 text-xs">
                  <InlineBadge text={planLabel} tone="blue" />
                  <InlineBadge
                    text={state.user.email_confirmed ? "Email verified" : "Email pending"}
                    tone={state.user.email_confirmed ? "emerald" : "amber"}
                  />
                  <InlineBadge
                    text={state.user.status ? titleCase(state.user.status) : "Active"}
                    tone={state.user.status === "suspended" ? "rose" : "violet"}
                  />
                </div>
              ) : null}
            </CardHeader>
            <CardContent className="grid gap-3">
              {NAV_ITEMS.map((item) => {
                const active =
                  item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex rounded-2xl border text-sm transition",
                      sidebarCollapsed
                        ? "items-center justify-center px-3 py-3"
                        : "items-center justify-between px-4 py-3",
                      active
                        ? "border-violet-400/25 bg-violet-500/[0.12] text-white"
                        : "border-white/8 bg-white/[0.03] text-slate-200/78 hover:border-violet-400/25 hover:bg-violet-500/[0.08] hover:text-white",
                    )}
                    title={item.label}
                    onClick={() => setMobileNavOpen(false)}
                  >
                    <span className={cn("flex items-center", sidebarCollapsed ? "justify-center" : "gap-3")}>
                      <item.icon className="h-4 w-4 text-violet-200" />
                      {!sidebarCollapsed ? item.label : null}
                    </span>
                    {!sidebarCollapsed ? <ArrowRight className="h-4 w-4 text-slate-500" /> : null}
                  </Link>
                );
              })}

              {!sidebarCollapsed ? (
                <div className="mt-3 grid gap-2 rounded-2xl border border-white/8 bg-white/[0.02] p-4 text-xs text-slate-300/68">
                  <div className="flex items-center justify-between">
                    <span>Profiles in use</span>
                    <span className="font-medium text-white">
                      {state.profiles.length}
                      {quotaChannels ? ` / ${quotaChannels}` : profileAllowance ? ` / ${profileAllowance}` : ""}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Wallet balance</span>
                    <span className="font-medium text-emerald-300">{formatCreditValue(walletBalance)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Member since</span>
                    <span className="font-medium text-white">{formatDate(state.user.created_at)}</span>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <div className="shrink-0 space-y-3 px-4 pb-3 pt-1">
          {FOOTER_NAV_ITEMS.map((item) => {
            const active =
              item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex rounded-2xl border text-sm transition",
                  sidebarCollapsed
                    ? "items-center justify-center px-3 py-3"
                    : "items-center justify-between px-4 py-3",
                  active
                    ? "border-violet-400/25 bg-violet-500/[0.12] text-white"
                    : "border-white/8 bg-white/[0.03] text-slate-200/78 hover:border-violet-400/25 hover:bg-violet-500/[0.08] hover:text-white",
                )}
                title={item.label}
                onClick={() => setMobileNavOpen(false)}
              >
                <span className={cn("flex items-center", sidebarCollapsed ? "justify-center" : "gap-3")}>
                  <item.icon className="h-4 w-4 text-violet-200" />
                  {!sidebarCollapsed ? item.label : null}
                </span>
                {!sidebarCollapsed ? <ArrowRight className="h-4 w-4 text-slate-500" /> : null}
              </Link>
            );
          })}
        </div>

        <div className="shrink-0 border-t border-white/8 bg-white/[0.02] p-4">
          <Button
            type="button"
            variant="outline"
            onClick={signOut}
            className={cn(
              "w-full border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]",
              sidebarCollapsed ? "px-0" : "justify-between",
            )}
            title="Sign out"
          >
            <span className={cn("flex items-center", sidebarCollapsed ? "justify-center" : "gap-3")}>
              <LogOut className="h-4 w-4" />
              {!sidebarCollapsed ? "Sign out" : null}
            </span>
            {!sidebarCollapsed ? <ArrowRight className="h-4 w-4 text-slate-500" /> : null}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-30 shrink-0 border-b border-white/8 bg-[linear-gradient(180deg,rgba(7,12,28,0.92),rgba(7,12,28,0.82))] shadow-[0_12px_36px_rgba(2,6,23,0.24)] backdrop-blur-xl">
          <div className="flex flex-col gap-4 px-5 py-4 md:px-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-3">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setMobileNavOpen(true)}
                className="mt-0.5 h-10 w-10 rounded-2xl border border-white/10 bg-white/[0.03] lg:hidden"
              >
                <Menu className="h-4 w-4 text-slate-300" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setSidebarCollapsed((current) => !current)}
                className="mt-0.5 hidden h-10 w-10 rounded-2xl border border-white/10 bg-white/[0.03] lg:inline-flex"
              >
                {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4 text-slate-300" /> : <PanelLeftClose className="h-4 w-4 text-slate-300" />}
              </Button>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                  User
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                  <span>Control panel</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                  <span className="text-slate-300">{currentPageTitle}</span>
                </div>
                <div className="text-lg font-medium text-slate-100">{currentPageTitle}</div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 md:flex">
                <activeNavItem.icon className="h-3.5 w-3.5 text-violet-200" />
                {planLabel}
              </div>
              <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 md:flex">
                <Coins className="h-3.5 w-3.5 text-emerald-300" />
                {formatCreditValue(walletBalance)} credits
              </div>
              <div className="text-sm text-slate-400">{state.user.email}</div>
            </div>
          </div>

          <nav className="flex gap-2 overflow-x-auto px-5 pb-4 lg:hidden">
            {ALL_NAV_ITEMS.map((item) => {
              const active =
                item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "whitespace-nowrap rounded-full border px-3 py-2 text-sm transition",
                    active
                      ? "border-violet-400/25 bg-violet-500/[0.12] text-white"
                      : "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]",
                  )}
                  onClick={() => setMobileNavOpen(false)}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.08),transparent_28%),linear-gradient(180deg,rgba(2,6,23,0.22),rgba(2,6,23,0))] px-5 py-6 md:px-6">
          <div className="mx-auto flex min-h-full w-full max-w-[1400px] flex-col">
            <div className="flex-1">
              {props.children}
            </div>
            <footer className="mt-8 border-t border-white/8 pt-5 text-xs text-slate-500">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="grid gap-2">
                  <div>© 2026 Camxora. One workspace across account, billing, credits, and production.</div>
                  <div className="flex flex-wrap items-center gap-3 text-slate-400">
                    <Link className="transition hover:text-white" href="/dashboard/account">
                      Account
                    </Link>
                    <span className="text-slate-700">/</span>
                    <Link className="transition hover:text-white" href="/dashboard/security">
                      Security
                    </Link>
                    <span className="text-slate-700">/</span>
                    <Link className="transition hover:text-white" href="/dashboard/billing">
                      Billing
                    </Link>
                    <span className="text-slate-700">/</span>
                    <Link className="transition hover:text-white" href="/dashboard/workspace">
                      Workspace
                    </Link>
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:items-end">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Need help?</div>
                  <div className="flex flex-wrap items-center gap-2 text-slate-400">
                    <span>{currentDisplayName}</span>
                    <span className="text-slate-600">/</span>
                    <span>{planLabel}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-slate-400">
                    <a className="transition hover:text-white" href={`${websiteBaseUrl}/contact`}>
                      Contact
                    </a>
                    <span className="text-slate-700">/</span>
                    <a className="transition hover:text-white" href={`${websiteBaseUrl}/terms`}>
                      Terms
                    </a>
                    <span className="text-slate-700">/</span>
                    <a className="transition hover:text-white" href={`${websiteBaseUrl}/privacy`}>
                      Privacy
                    </a>
                    <span className="text-slate-700">/</span>
                    <a className="transition hover:text-white" href={`${websiteBaseUrl}/download`}>
                      Download
                    </a>
                  </div>
                </div>
              </div>
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}
