"use client";

import Link from "next/link";
import { ArrowRight, ChevronDown, Download, LogOut } from "lucide-react";

import { getWebsiteBaseUrl, isSandboxEnvironment } from "@/lib/site-urls";

type PortalMarketingShellProps = {
  active: "login" | "register";
  badge?: string;
  title?: string;
  description?: string;
  highlights?: string[];
  compact?: boolean;
  wide?: boolean;
  hideFooter?: boolean;
  account?: {
    email: string;
    planLabel?: string | null;
    onSignOut?: () => void;
  };
  children: React.ReactNode;
};

export function PortalMarketingShell(props: PortalMarketingShellProps) {
  const websiteBaseUrl = getWebsiteBaseUrl();

  const primaryNavLinks = [
    { href: `${websiteBaseUrl}/features`, label: "Features" },
    { href: `${websiteBaseUrl}/pricing`, label: "Pricing" },
    { href: `${websiteBaseUrl}/download`, label: "Download" },
    { href: `${websiteBaseUrl}/about`, label: "About" },
  ];
  const productLinks = [
    { href: `${websiteBaseUrl}/features`, label: "Features" },
    { href: `${websiteBaseUrl}/services`, label: "Who it's for" },
    { href: `${websiteBaseUrl}/pricing`, label: "Pricing" },
    { href: `${websiteBaseUrl}/download`, label: "Download" },
  ];
  const companyLinks = [
    { href: `${websiteBaseUrl}/about`, label: "About" },
    { href: `${websiteBaseUrl}/blog`, label: "Blog" },
    { href: `${websiteBaseUrl}/changelog`, label: "Changelog" },
    { href: `${websiteBaseUrl}/contact`, label: "Contact" },
  ];
  const supportLinks = [
    { href: `${websiteBaseUrl}/support`, label: "Help Center" },
    { href: `${websiteBaseUrl}/contact`, label: "Contact" },
    { href: `${websiteBaseUrl}/data-deletion`, label: "Data deletion" },
  ];
  const legalLinks = [
    { href: `${websiteBaseUrl}/terms`, label: "Terms" },
    { href: `${websiteBaseUrl}/privacy`, label: "Privacy" },
    { href: `${websiteBaseUrl}/google-api`, label: "Google API policy" },
    { href: `${websiteBaseUrl}/cookies`, label: "Cookies" },
    { href: `${websiteBaseUrl}/copyright`, label: "Copyright" },
    { href: `${websiteBaseUrl}/acceptable-use`, label: "Acceptable use" },
  ];

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(1100px_circle_at_15%_10%,rgba(168,85,247,0.18),transparent_45%),radial-gradient(900px_circle_at_85%_85%,rgba(217,70,239,0.1),transparent_40%),linear-gradient(to_bottom,hsla(222,47%,5%,0.55),hsla(222,47%,5%,1))]" />
      </div>

      {isSandboxEnvironment() ? (
        <div className="border-b border-amber-400/25 bg-amber-500/10 px-4 py-2 text-center text-sm text-amber-100">
          Sandbox environment — test payments may apply. Not the production Camxora site.
        </div>
      ) : null}

      <header className="sticky top-0 z-40 border-b border-white/8 bg-[rgba(5,8,18,0.82)] backdrop-blur-xl">
        <div className="mx-auto w-full max-w-7xl px-6 py-4 md:px-10">
          <div className="flex items-center justify-between gap-4">
            <Link className="flex items-center gap-3" href={websiteBaseUrl}>
              <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
              <div>
                <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                  Camxora
                </div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/58">
                  Faceless desktop studio
                </div>
              </div>
            </Link>

            <nav className="hidden items-center gap-6 text-sm font-medium text-slate-200/74 xl:flex">
              {primaryNavLinks.map((item) => (
                <Link key={item.href} className="transition hover:text-white" href={item.href}>
                  {item.label}
                </Link>
              ))}
            </nav>

            {props.account ? (
              <details className="relative">
                <summary className="flex h-11 list-none items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm text-slate-100 transition hover:bg-white/[0.06] [&::-webkit-details-marker]:hidden">
                  <div className="hidden text-right sm:block">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Signed in</div>
                    <div className="max-w-[220px] truncate font-medium text-white">{props.account.email}</div>
                  </div>
                  <div className="truncate font-medium text-white sm:hidden">{props.account.email}</div>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </summary>
                <div className="absolute right-0 top-[calc(100%+10px)] z-50 w-64 rounded-2xl border border-white/10 bg-[#0b1024]/95 p-2 shadow-[0_24px_80px_rgba(10,12,34,0.45)] ring-1 ring-white/6 backdrop-blur-xl">
                  <div className="rounded-xl px-3 py-3">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Account</div>
                    <div className="mt-1 truncate text-sm font-medium text-white">{props.account.email}</div>
                    {props.account.planLabel ? (
                      <div className="mt-2 text-xs text-slate-300/72">{props.account.planLabel}</div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={props.account.onSignOut}
                    className="flex w-full items-center justify-between rounded-xl px-3 py-3 text-left text-sm font-medium text-white transition hover:bg-white/[0.06]"
                  >
                    <span>Sign out</span>
                    <LogOut className="h-4 w-4 text-slate-400" />
                  </button>
                </div>
              </details>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  className="hidden h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-slate-100 transition hover:bg-white/[0.06] sm:inline-flex"
                  href="/login"
                >
                  Sign in
                </Link>
                <Link
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                  href="/register"
                >
                  Create account
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            )}
          </div>

          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 text-sm xl:hidden">
            {primaryNavLinks.map((item) => (
              <Link
                key={item.href}
                className="whitespace-nowrap rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-slate-200/72 transition hover:bg-white/[0.06] hover:text-white"
                href={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="relative mx-auto flex w-full max-w-[1500px] flex-1 flex-col px-5 py-8 md:px-8 md:py-10">
        <section
          className={
            props.wide
              ? "mx-auto w-full max-w-[1500px]"
              : props.compact
                ? "mx-auto flex w-full max-w-md flex-1 items-center"
                : "grid items-center gap-12 md:grid-cols-2"
          }
        >
          {props.compact || props.wide ? null : (
            <div className="min-w-0">
              {props.badge ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-200/80">
                  {props.badge}
                </div>
              ) : null}
              {props.title ? (
                <h1 className="mt-5 max-w-2xl font-display text-5xl font-bold leading-[0.95] tracking-[-0.055em] text-white md:text-6xl">
                  {props.title}
                </h1>
              ) : null}
              {props.description ? (
                <p className="mt-5 max-w-xl text-[15px] leading-7 text-slate-200/80 md:text-base">
                  {props.description}
                </p>
              ) : null}

              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Link
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_0_36px_rgba(168,85,247,0.22)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                  href={props.active === "register" ? "/register" : "/login"}
                >
                  {props.active === "register" ? "Create account" : "Sign in"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white hover:bg-white/[0.06]"
                  href={`${websiteBaseUrl}/download`}
                >
                  <Download className="h-4 w-4" />
                  Download desktop app
                </Link>
              </div>

              {props.highlights?.length ? (
                <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-200/72">
                  {props.highlights.map((item) => (
                    <div key={item} className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-gradient-to-r from-violet-300 to-fuchsia-300" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          <div className={props.wide ? "w-full" : "mx-auto w-full max-w-md"}>{props.children}</div>
        </section>
      </main>

      {props.hideFooter ? null : (
        <footer className="relative mt-auto border-t border-white/8 bg-[linear-gradient(180deg,rgba(8,10,20,0.24),rgba(4,6,14,0.92))]">
          <div className="mx-auto grid w-full max-w-7xl gap-10 px-6 py-12 text-sm text-slate-200/68 md:px-10 lg:grid-cols-[1.4fr_1fr_1fr_1fr_1fr]">
            <div className="max-w-md">
              <div className="flex items-center gap-3">
                <img alt="Camxora" className="h-10 w-10" src="/camxora-logo.svg" />
                <div>
                  <div className="font-display text-lg font-semibold tracking-[-0.05em] text-white">
                    Camxora
                  </div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/54">
                    Faceless desktop studio
                  </div>
                </div>
              </div>
              <p className="mt-4 leading-7 text-slate-200/60">
                Build dual faceless YouTube music channels — lyrics to video in one Windows app.
              </p>
              <div className="mt-6 text-xs uppercase tracking-[0.2em] text-slate-400">
                Export ready today. Auto-upload coming soon.
              </div>
            </div>

            <FooterColumn title="Product" items={productLinks} />
            <FooterColumn title="Company" items={[...companyLinks, { href: "/login", label: "User Portal" }]} />
            <FooterColumn title="Support" items={supportLinks} />
            <FooterColumn title="Legal" items={legalLinks} />
          </div>

          <div className="border-t border-white/6">
            <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-6 py-4 text-xs text-slate-400 md:flex-row md:items-center md:justify-between md:px-10">
              <div>© {new Date().getFullYear()} Camxora</div>
              <div>No camera. No face. YouTube-ready music videos.</div>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}

function FooterColumn({
  title,
  items,
}: {
  title: string;
  items: Array<{ href: string; label: string }>;
}) {
  return (
    <div>
      <div className="font-medium text-white">{title}</div>
      <div className="mt-4 grid gap-2.5">
        {items.map((item) => (
          <Link key={item.href} className="transition hover:text-white" href={item.href}>
            {item.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
